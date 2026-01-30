/**
 * Panel Management
 *
 * Handles detail and evidence panels.
 * See docs/ux/progressive-disclosure.md for specification.
 */

/**
 * Initialize panel functionality
 */
function initializePanels(cy) {
  // Close buttons
  document.querySelectorAll('.panel-close').forEach(btn => {
    btn.addEventListener('click', () => {
      const panel = btn.closest('.panel');
      if (panel) {
        panel.classList.add('hidden');
        updateCyContainer();
      }
    });
  });

  // Error dismiss
  document.getElementById('error-dismiss')?.addEventListener('click', hideError);
}

/**
 * Open node detail panel
 */
function openNodeDetailPanel(node) {
  const data = node.data();
  const panel = document.getElementById('detail-panel');
  const content = document.getElementById('detail-content');

  if (!panel || !content) return;

  content.innerHTML = `
    <header class="detail-header">
      <span class="badge badge-type-${data.type.toLowerCase()}">${data.type}</span>
      <h2 class="detail-title">${escapeHtml(data.label)}</h2>
      ${data.aliases && data.aliases.length > 0 ? `
        <p class="detail-aliases text-sm text-gray-500">
          Also known as: ${data.aliases.map(a => escapeHtml(a)).join(', ')}
        </p>
      ` : ''}
    </header>

    <section class="detail-section mt-4">
      <h3 class="text-xs font-semibold text-gray-500 mb-2">TIMELINE</h3>
      <div class="flex justify-between text-sm mb-1">
        <span class="text-gray-500">First seen</span>
        <span class="font-medium">${formatDate(data.firstSeen)}</span>
      </div>
      <div class="flex justify-between text-sm">
        <span class="text-gray-500">Last seen</span>
        <span class="font-medium">${formatDate(data.lastSeen)}</span>
      </div>
    </section>

    <section class="detail-section mt-4">
      <h3 class="text-xs font-semibold text-gray-500 mb-2">ACTIVITY</h3>
      <div class="grid gap-2" style="grid-template-columns: repeat(2, 1fr);">
        <div class="p-2 bg-gray-50 rounded">
          <div class="text-lg font-semibold">${data.mentionCount7d || 0}</div>
          <div class="text-xs text-gray-500">Mentions (7d)</div>
        </div>
        <div class="p-2 bg-gray-50 rounded">
          <div class="text-lg font-semibold">${data.mentionCount30d || 0}</div>
          <div class="text-xs text-gray-500">Mentions (30d)</div>
        </div>
        <div class="p-2 bg-gray-50 rounded">
          <div class="text-lg font-semibold">${node.degree()}</div>
          <div class="text-xs text-gray-500">Connections</div>
        </div>
        <div class="p-2 bg-gray-50 rounded ${data.velocity > 0.5 ? 'bg-yellow-50' : ''}">
          <div class="text-lg font-semibold">${formatVelocity(data.velocity)}</div>
          <div class="text-xs text-gray-500">Velocity</div>
        </div>
      </div>
    </section>

    <section class="detail-section mt-4">
      <h3 class="text-xs font-semibold text-gray-500 mb-2">
        RELATIONSHIPS (${node.connectedEdges().length})
      </h3>
      <div class="detail-relationships">
        ${renderRelationshipList(node)}
      </div>
    </section>

    <div class="mt-4 flex gap-2">
      <button class="btn btn-sm flex-1" onclick="expandNeighbors(window.cy.getElementById('${data.id}'))">
        Expand
      </button>
      <button class="btn btn-sm flex-1" onclick="zoomToNode(window.cy.getElementById('${data.id}'))">
        Center
      </button>
    </div>
  `;

  panel.classList.remove('hidden');
  document.getElementById('cy')?.classList.add('panel-left-open');
}

/**
 * Render relationship list for detail panel
 */
function renderRelationshipList(node) {
  const edges = node.connectedEdges();

  if (edges.length === 0) {
    return '<p class="text-sm text-gray-400">No relationships</p>';
  }

  // Group by relationship type
  const grouped = {};
  edges.forEach(edge => {
    const rel = edge.data('rel');
    if (!grouped[rel]) grouped[rel] = [];
    grouped[rel].push(edge);
  });

  let html = '';
  for (const [rel, relEdges] of Object.entries(grouped)) {
    html += `
      <div class="mb-3">
        <div class="text-xs font-medium text-gray-600 mb-1">${formatRelation(rel)}</div>
        <ul class="text-sm">
          ${relEdges.slice(0, 5).map(edge => {
            const other = edge.source().id() === node.id()
              ? edge.target()
              : edge.source();
            const direction = edge.source().id() === node.id() ? '→' : '←';
            return `
              <li class="flex items-center gap-2 py-1 cursor-pointer hover:bg-gray-50 rounded px-1"
                  onclick="selectNode('${other.id()}')">
                <span class="text-gray-400">${direction}</span>
                <span class="truncate flex-1">${escapeHtml(other.data('label'))}</span>
                <span class="badge badge-kind-${edge.data('kind')} text-xs">${edge.data('kind')}</span>
              </li>
            `;
          }).join('')}
          ${relEdges.length > 5 ? `
            <li class="text-xs text-gray-400 py-1">+${relEdges.length - 5} more</li>
          ` : ''}
        </ul>
      </div>
    `;
  }

  return html;
}

/**
 * Open evidence panel for an edge
 */
function openEvidencePanel(edge) {
  const data = edge.data();
  const sourceNode = edge.source();
  const targetNode = edge.target();
  const panel = document.getElementById('evidence-panel');
  const content = document.getElementById('evidence-content');

  if (!panel || !content) return;

  const evidence = data.evidence || [];

  content.innerHTML = `
    <header class="mb-4">
      <div class="flex items-center gap-2 text-lg font-semibold">
        <span>${escapeHtml(sourceNode.data('label'))}</span>
        <span class="text-gray-400">→</span>
        <span>${escapeHtml(targetNode.data('label'))}</span>
      </div>
      <div class="flex items-center gap-3 mt-2 text-sm">
        <span class="badge badge-kind-${data.kind}">${capitalize(data.kind)}</span>
        <span class="text-gray-500">${formatRelation(data.rel)}</span>
        <span class="text-gray-500">${(data.confidence * 100).toFixed(0)}% confidence</span>
      </div>
    </header>

    <section>
      <h3 class="text-xs font-semibold text-gray-500 mb-3">
        EVIDENCE (${evidence.length} source${evidence.length === 1 ? '' : 's'})
      </h3>

      ${evidence.length > 0 ? `
        <ul class="space-y-4">
          ${evidence.map(ev => {
            const title = ev.title || formatDocId(ev.docId) || 'Untitled';
            const source = ev.source || extractDomain(ev.url) || 'Unknown source';
            return `
            <li class="border-l-2 border-gray-200 pl-3">
              <div class="font-medium text-sm">${escapeHtml(title)}</div>
              <div class="text-xs text-gray-500 mt-1">
                ${escapeHtml(source)} · ${formatDate(ev.published)}
              </div>
              <blockquote class="text-sm text-gray-600 mt-2 italic">
                "${escapeHtml(ev.snippet)}"
              </blockquote>
              ${ev.url ? `
                <a href="${ev.url}" target="_blank" rel="noopener" class="text-xs text-blue-600 mt-1 inline-block">
                  View document →
                </a>
              ` : ''}
            </li>`;
          }).join('')}
        </ul>
      ` : `
        <p class="text-sm text-gray-400">
          No evidence snippets available. This may be an inferred or hypothesis edge.
        </p>
      `}
    </section>

    <div class="mt-4 flex gap-2">
      <button class="btn btn-sm" onclick="selectNode('${sourceNode.id()}')">
        View ${truncateLabel(sourceNode.data('label'), 15)}
      </button>
      <button class="btn btn-sm" onclick="selectNode('${targetNode.id()}')">
        View ${truncateLabel(targetNode.data('label'), 15)}
      </button>
    </div>
  `;

  panel.classList.remove('hidden');
  updateCyContainer();
}

/**
 * Close all panels
 */
function closeAllPanels() {
  document.getElementById('detail-panel')?.classList.add('hidden');
  document.getElementById('evidence-panel')?.classList.add('hidden');
  updateCyContainer();
}

/**
 * Update cy container classes based on panel state
 */
function updateCyContainer() {
  const cyEl = document.getElementById('cy');
  if (!cyEl) return;

  const detailOpen = !document.getElementById('detail-panel')?.classList.contains('hidden');
  const filterOpen = !document.getElementById('filter-panel')?.classList.contains('collapsed');
  const evidenceOpen = !document.getElementById('evidence-panel')?.classList.contains('hidden');

  cyEl.classList.toggle('panel-left-open', detailOpen);
  cyEl.classList.toggle('panel-right-open', filterOpen);
  cyEl.classList.toggle('panel-bottom-open', evidenceOpen);

  // Tell Cytoscape to recalculate after container resize
  if (window.cy) {
    setTimeout(() => window.cy.resize(), 50);
  }
}

/**
 * Select a node by ID
 */
function selectNode(nodeId) {
  if (!window.cy) return;
  const node = window.cy.getElementById(nodeId);
  if (node.length > 0) {
    window.cy.elements().unselect();
    node.select();
    openNodeDetailPanel(node);
  }
}

/**
 * Zoom to a node
 */
function zoomToNode(node) {
  if (!node || !window.cy) return;
  window.cy.animate({
    center: { eles: node },
    zoom: 2,
    duration: 300
  });
}

/**
 * Expand neighbors of a node
 */
function expandNeighbors(node, depth = 1) {
  if (!node || !window.cy) return;

  const cy = window.cy;

  // Get neighbors up to specified depth
  let toExpand = node;
  for (let i = 0; i < depth; i++) {
    toExpand = toExpand.closedNeighborhood();
  }

  // Show hidden neighbors
  toExpand.removeClass('filtered-out').show();

  // Fit to show expanded neighborhood
  cy.animate({
    fit: {
      eles: toExpand,
      padding: 50
    },
    duration: 300
  });

  // Update label visibility
  if (typeof updateLabelVisibility === 'function') {
    updateLabelVisibility(cy);
  }
}
