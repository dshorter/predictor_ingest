/**
 * Main Application Entry Point
 *
 * Initializes all components and manages application state.
 */

// Application state
const AppState = {
  currentView: 'trending',
  currentDate: null,
  isLoading: false,
  cy: null
};

/**
 * Initialize the application
 */
async function initializeApp() {
  console.log('Initializing AI Trend Graph...');

  try {
    // Show loading state
    showLoading('Initializing...');

    // Get container
    const container = document.getElementById('cy');
    if (!container) {
      throw new Error('Graph container not found');
    }

    // Load default data
    const dataUrl = getDataUrl(AppState.currentView, AppState.currentDate);
    const data = await loadGraphData(dataUrl);

    // Initialize Cytoscape
    AppState.cy = initializeGraph(container, data, getCytoscapeStyles());

    // Expose cy globally for panel functions
    window.cy = AppState.cy;

    // Initialize all components
    initializeEventHandlers(AppState.cy);
    initializePanels(AppState.cy);
    initializeTooltips(AppState.cy);
    initializeSearch(AppState.cy);
    initializeFilters(AppState.cy);
    initializeToolbar(AppState.cy);

    // Run initial layout
    runLayout(AppState.cy);

    // Update stats display
    updateStatsDisplay(AppState.cy);

    // Hide loading
    hideLoading();

    // Announce to screen readers
    const stats = getGraphStats(AppState.cy);
    announceToScreenReader(
      `Graph loaded with ${stats.nodeCount} nodes and ${stats.edgeCount} edges.`
    );

    console.log('Application initialized successfully');

  } catch (error) {
    console.error('Failed to initialize application:', error);
    hideLoading();
    showError(`Failed to initialize: ${error.message}`);
  }
}

/**
 * Initialize event handlers for the graph
 */
function initializeEventHandlers(cy) {
  // Node click - open detail panel
  cy.on('tap', 'node', (e) => {
    const node = e.target;
    cy.elements().unselect();
    node.select();
    openNodeDetailPanel(node);
  });

  // Edge click - open evidence panel
  cy.on('tap', 'edge', (e) => {
    const edge = e.target;
    cy.elements().unselect();
    edge.select();
    openEvidencePanel(edge);
  });

  // Background click - close panels
  cy.on('tap', (e) => {
    if (e.target === cy) {
      closeAllPanels();
      cy.elements().unselect();
    }
  });

  // Zoom change - update label visibility
  cy.on('zoom', () => {
    updateLabelVisibility(cy);
  });

  // Keyboard navigation
  document.addEventListener('keydown', (e) => {
    handleKeyboardNavigation(e, cy);
  });
}

/**
 * Initialize toolbar controls
 */
function initializeToolbar(cy) {
  // Zoom controls
  document.getElementById('btn-zoom-in')?.addEventListener('click', () => {
    cy.zoom(cy.zoom() * 1.2);
  });

  document.getElementById('btn-zoom-out')?.addEventListener('click', () => {
    cy.zoom(cy.zoom() / 1.2);
  });

  // Fit button
  document.getElementById('btn-fit')?.addEventListener('click', () => {
    fitGraph(cy);
  });

  // Layout button
  document.getElementById('btn-layout')?.addEventListener('click', () => {
    runLayout(cy);
  });

  // Filter toggle
  document.getElementById('btn-filter')?.addEventListener('click', () => {
    toggleFilterPanel();
  });

  // View selector
  document.getElementById('view-selector')?.addEventListener('change', async (e) => {
    await switchView(e.target.value);
  });

  // Date selector
  document.getElementById('date-selector')?.addEventListener('change', async (e) => {
    await switchDate(e.target.value);
  });
}

/**
 * Handle keyboard navigation
 */
function handleKeyboardNavigation(e, cy) {
  // Only handle when graph container is focused
  if (document.activeElement?.id !== 'cy') return;

  switch (e.key) {
    case '+':
    case '=':
      cy.zoom(cy.zoom() * 1.1);
      e.preventDefault();
      break;
    case '-':
      cy.zoom(cy.zoom() / 1.1);
      e.preventDefault();
      break;
    case '0':
      fitGraph(cy);
      e.preventDefault();
      break;
    case 'Escape':
      closeAllPanels();
      cy.elements().unselect();
      e.preventDefault();
      break;
    case '/':
      // Focus search
      document.getElementById('search-input')?.focus();
      e.preventDefault();
      break;
    case 'ArrowUp':
    case 'ArrowDown':
    case 'ArrowLeft':
    case 'ArrowRight':
      handleArrowNavigation(e, cy);
      break;
  }
}

/**
 * Handle arrow key navigation between nodes
 */
function handleArrowNavigation(e, cy) {
  const selected = cy.$(':selected');
  if (selected.length === 0) return;

  const current = selected[0];
  if (!current.isNode()) return;

  const neighbors = current.neighborhood('node');
  if (neighbors.length === 0) return;

  // Find nearest neighbor in arrow direction
  const currentPos = current.position();
  let best = null;
  let bestScore = -Infinity;

  neighbors.forEach(neighbor => {
    const pos = neighbor.position();
    const dx = pos.x - currentPos.x;
    const dy = pos.y - currentPos.y;

    let score = 0;
    switch (e.key) {
      case 'ArrowUp': score = -dy; break;
      case 'ArrowDown': score = dy; break;
      case 'ArrowLeft': score = -dx; break;
      case 'ArrowRight': score = dx; break;
    }

    if (score > 0 && score > bestScore) {
      bestScore = score;
      best = neighbor;
    }
  });

  if (best) {
    cy.elements().unselect();
    best.select();
    openNodeDetailPanel(best);
    e.preventDefault();
  }
}

/**
 * Switch to a different view
 */
async function switchView(view) {
  AppState.currentView = view;
  const dataUrl = getDataUrl(view, AppState.currentDate);

  try {
    const data = await loadGraphData(dataUrl);

    // Clear and reload
    AppState.cy.elements().remove();
    addElements(AppState.cy, data.elements);

    // Re-run layout
    runLayout(AppState.cy);

    // Update stats
    updateStatsDisplay(AppState.cy);

    // Announce
    const stats = getGraphStats(AppState.cy);
    announceToScreenReader(`Switched to ${view} view. ${stats.nodeCount} nodes.`);

  } catch (error) {
    console.error('Failed to switch view:', error);
  }
}

/**
 * Switch to a different date
 */
async function switchDate(date) {
  AppState.currentDate = date;
  await switchView(AppState.currentView);
}

/**
 * Get data URL for a view and date
 */
function getDataUrl(view, date) {
  const basePath = 'data/graphs';
  const datePart = date || 'latest';
  return `${basePath}/${datePart}/${view}.json`;
}

/**
 * Update statistics display
 */
function updateStatsDisplay(cy) {
  const stats = getGraphStats(cy);
  // Could update a stats element in the toolbar if we add one
  console.log('Graph stats:', stats);
}

/**
 * Toggle filter panel
 */
function toggleFilterPanel() {
  const panel = document.getElementById('filter-panel');
  if (panel) {
    panel.classList.toggle('collapsed');
    updateCyContainer();
  }
}

// updateCyContainer and closeAllPanels are defined in panels.js

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', initializeApp);
