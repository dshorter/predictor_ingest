/**
 * Lens — Client-side geographic focus filter.
 *
 * Reads `region[]` arrays on graph nodes (set at export time by Sprint 7B)
 * and dims nodes that don't match the active lens. Zero server calls.
 *
 * Usage:
 *   initLens(cy, domainConfig);  // called from app.js after graph loads
 *   applyLens(cy);               // re-apply after view switch or data reload
 *
 * Per ADR-005: regional focus is demand-side (user preference), not supply-side.
 */

/** Currently active lens slug. 'all' means no filtering. */
let _currentLens = 'all';

/** Cached lens config from domain JSON. */
let _lensOptions = [];

/**
 * Initialize the lens dropdown in the toolbar.
 * Only renders if the domain config includes a `lenses` array with > 1 entry.
 *
 * @param {object} cy - Cytoscape instance
 * @param {object} domainConfig - Parsed domain JSON (from web/data/domains/<slug>.json)
 */
function initLens(cy, domainConfig) {
  _currentLens = 'all';
  _lensOptions = [];

  // Clean up any previous lens dropdown
  const existing = document.getElementById('lens-group');
  if (existing) existing.remove();

  // Only show if domain defines lenses
  const lenses = domainConfig && domainConfig.lenses;
  if (!Array.isArray(lenses) || lenses.length < 2) return;

  _lensOptions = lenses;

  // Build toolbar group: <label> + <select>
  const group = document.createElement('div');
  group.className = 'toolbar-group';
  group.id = 'lens-group';

  const label = document.createElement('label');
  label.setAttribute('for', 'lens-selector');
  label.textContent = 'Lens:';

  const select = document.createElement('select');
  select.id = 'lens-selector';
  select.title = 'Geographic focus lens';

  for (const lens of lenses) {
    const opt = document.createElement('option');
    opt.value = lens.slug;
    opt.textContent = lens.label;
    if (lens.slug === 'all') opt.selected = true;
    select.appendChild(opt);
  }

  select.addEventListener('change', () => {
    _currentLens = select.value;
    applyLens(cy);
  });

  group.appendChild(label);
  group.appendChild(select);

  // Insert after the view selector toolbar-group
  const viewGroup = document.getElementById('view-selector')?.closest('.toolbar-group');
  if (viewGroup && viewGroup.parentNode) {
    // Add a divider before the lens
    const divider = document.createElement('div');
    divider.className = 'toolbar-divider';
    divider.setAttribute('aria-hidden', 'true');
    viewGroup.after(divider);
    divider.after(group);
  }
}

/**
 * Apply the current lens to the graph.
 * Adds `.region-dimmed` to nodes/edges that don't match the active lens.
 *
 * @param {object} cy - Cytoscape instance
 */
function applyLens(cy) {
  if (!cy) return;

  // Remove existing lens dimming
  cy.elements().removeClass('region-dimmed');

  // 'all' means show everything
  if (_currentLens === 'all') {
    _updateLensStats(cy, null);
    return;
  }

  // Find nodes that have the matching region tag
  const matching = cy.nodes().filter(node => {
    const regions = node.data('region');
    return Array.isArray(regions) && regions.includes(_currentLens);
  });

  // Dim everything, then un-dim matches + their edges
  if (matching.length > 0) {
    cy.elements().addClass('region-dimmed');
    matching.removeClass('region-dimmed');
    // Un-dim edges between matching nodes
    matching.edgesWith(matching).removeClass('region-dimmed');
  }

  _updateLensStats(cy, matching);
}

/**
 * Get the current lens slug (for external consumers).
 * @returns {string}
 */
function getCurrentLens() {
  return _currentLens;
}

/**
 * Update stats display to reflect lens filtering.
 * @param {object} cy
 * @param {object|null} matching - matching node collection, or null if no lens
 */
function _updateLensStats(cy, matching) {
  const statsEl = document.getElementById('graph-stats');
  if (!statsEl) return;

  const totalNodes = cy.nodes().length;
  const totalEdges = cy.edges().length;

  if (!matching) {
    statsEl.textContent = `${totalNodes} nodes \u00B7 ${totalEdges} edges`;
  } else {
    const matchEdges = matching.edgesWith(matching).length;
    statsEl.textContent =
      `${matching.length}/${totalNodes} nodes \u00B7 ${matchEdges}/${totalEdges} edges`;
  }
}
