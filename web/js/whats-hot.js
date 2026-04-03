/**
 * What's Hot Panel
 *
 * Surfaces top trending entities as a ranked list with LLM-generated
 * "WHY" narratives. Pure rendering functions are separated from DOM
 * wiring for testability.
 *
 * See docs/ux/delight-backlog.md §DL-1 for specification.
 */

// ---------------------------------------------------------------------------
// Pure functions (testable with mock cy / plain objects)
// ---------------------------------------------------------------------------

/**
 * Extract the top trending entities from the Cytoscape graph.
 * @param {object} cy - Cytoscape instance (or mock with .nodes())
 * @param {number} limit - Max items to return
 * @returns {Array<object>} Sorted list of plain entity objects
 */
function getHotList(cy, limit = 10) {
  if (!cy || typeof cy.nodes !== 'function') return [];

  const items = [];
  cy.nodes().forEach(node => {
    const d = node.data();
    const velocity = d.velocity ?? 0;
    const trendScore = d.trend_score ?? 0;
    if (velocity <= 0 && trendScore <= 0) return;

    // Collect up to 3 unique source domains from connected Document nodes
    const seenDomains = new Set();
    const topSources = [];
    node.neighborhood('node[type = "Document"]').forEach(dn => {
      const domain = (typeof extractDomain === 'function' && dn.data('url'))
        ? extractDomain(dn.data('url'))
        : dn.data('source');
      if (domain && !seenDomains.has(domain) && topSources.length < 3) {
        seenDomains.add(domain);
        topSources.push(domain);
      }
    });

    items.push({
      id: d.id,
      label: d.label || d.id,
      type: d.type || 'Unknown',
      velocity: velocity,
      trend_score: trendScore,
      mention_count_7d: d.mention_count_7d ?? 0,
      narrative: d.narrative || null,
      isNew: isNewNode(d.firstSeen),
      sources: topSources
    });
  });

  items.sort((a, b) => b.trend_score - a.trend_score);
  return items.slice(0, limit);
}

/**
 * Render a single hot-list item as HTML.
 * @param {object} item - Entity object from getHotList()
 * @param {number} index - 0-based position
 * @returns {string} HTML string
 */
function renderHotItem(item, index) {
  const rank = index + 1;
  const typeLower = (item.type || '').toLowerCase();
  const vel = formatVelocity(item.velocity);
  const velClass = item.velocity >= 1 ? 'hot-spark-up' : 'hot-spark-down';
  const label = escapeHtml(item.label);
  const newBadge = item.isNew ? '<span class="hot-new">NEW</span>' : '';

  let narrativeHtml = '';
  if (item.narrative) {
    const truncated = item.narrative.length > 120
      ? item.narrative.substring(0, 117) + '...'
      : item.narrative;
    narrativeHtml = `<p class="hot-narrative">${escapeHtml(truncated)}</p>`;
  }

  const sourceIcons = item.sources && item.sources.length > 0
    ? `<div class="hot-sources">${item.sources.map(s =>
        `<img class="source-favicon" src="https://www.google.com/s2/favicons?domain=${escapeHtml(s)}&sz=14" onerror="this.style.display='none'" loading="lazy" title="${escapeHtml(s)}">`
      ).join('')}</div>`
    : '';

  return `
    <li class="hot-item" data-node-id="${escapeHtml(item.id)}" role="button" tabindex="0">
      <span class="hot-rank">${rank}</span>
      <div class="hot-body">
        <div class="hot-meta">
          <span class="badge badge-type-${typeLower}">${escapeHtml(item.type)}</span>
          ${newBadge}
          <span class="hot-spark ${velClass}">${vel}</span>
        </div>
        ${sourceIcons}
        <span class="hot-label">${label}</span>
        ${narrativeHtml}
      </div>
    </li>`;
}

/**
 * Render the full hot-list panel content.
 * @param {Array<object>} items - From getHotList()
 * @returns {string} HTML string for #hot-content
 */
function renderHotList(items) {
  if (!items || items.length === 0) {
    return `
      <div class="hot-header">
        <h2 class="hot-title">What's Hot</h2>
      </div>
      <div class="hot-empty">
        <p>No trending entities yet.</p>
        <p class="text-xs text-gray-400">Entities appear here when they gain velocity across sources.</p>
      </div>`;
  }

  const listItems = items.map((item, i) => renderHotItem(item, i)).join('');
  return `
    <div class="hot-header">
      <h2 class="hot-title">What's Hot</h2>
      <span class="hot-count">${items.length} trending</span>
    </div>
    <ol class="hot-list">
      ${listItems}
    </ol>`;
}

// ---------------------------------------------------------------------------
// DOM wiring (thin shell — not unit-tested)
// ---------------------------------------------------------------------------

/**
 * Initialize the What's Hot panel. Call after Cytoscape is ready.
 * @param {object} cy - Cytoscape instance
 */
function initWhatsHot(cy) {
  const panel = document.getElementById('hot-panel');
  if (!panel) return;

  // Close button
  panel.querySelector('.panel-close')?.addEventListener('click', () => {
    panel.classList.add('hidden');
    document.getElementById('cy')?.classList.remove('panel-left-open');
  });

  // Delegate click/keyboard on list items
  const content = document.getElementById('hot-content');
  if (content) {
    content.addEventListener('click', (e) => {
      const item = e.target.closest('.hot-item');
      if (item) flyToHotNode(item.dataset.nodeId);
    });
    content.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        const item = e.target.closest('.hot-item');
        if (item) {
          e.preventDefault();
          flyToHotNode(item.dataset.nodeId);
        }
      }
    });
  }
}

/**
 * Toggle the hot panel open/closed.
 */
function toggleHotPanel() {
  const panel = document.getElementById('hot-panel');
  if (!panel) return;

  const isHidden = panel.classList.contains('hidden');

  if (isHidden) {
    closeLeftPanels('hot-panel');

    // Populate and show
    const cy = window.cy || AppState?.cy;
    const items = getHotList(cy);
    const content = document.getElementById('hot-content');
    if (content) content.innerHTML = renderHotList(items);

    panel.classList.remove('hidden');
    updateCyContainer();
    announceToScreenReader(`What's Hot panel open. ${items.length} trending entities.`);
  } else {
    panel.classList.add('hidden');
    updateCyContainer();
    announceToScreenReader("What's Hot panel closed.");
  }
}

/**
 * Refresh hot panel content if it's currently open.
 * Call after view switch or data reload.
 * @param {object} cy - Cytoscape instance
 */
function refreshHotPanel(cy) {
  const panel = document.getElementById('hot-panel');
  if (!panel || panel.classList.contains('hidden')) return;

  const items = getHotList(cy);
  const content = document.getElementById('hot-content');
  if (content) content.innerHTML = renderHotList(items);
}

/**
 * Fly to a node from the hot list: select, zoom, open detail.
 * Delegates to the shared navigateToNode codepath.
 * @param {string} nodeId - Cytoscape node ID
 */
function flyToHotNode(nodeId) {
  navigateToNode(nodeId, { zoom: true, updatePanel: true });
}
