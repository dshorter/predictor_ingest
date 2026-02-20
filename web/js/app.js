/**
 * Main Application Entry Point
 *
 * Initializes all components and manages application state.
 */

// Default date window (days). Matches DEFAULT_DATE_WINDOW_DAYS in src/config/.
// Exposed here so the UI can set an initial filter without a server round-trip.
const DEFAULT_DATE_WINDOW_DAYS = 30;

// Application state
const AppState = {
  currentView: 'trending',
  dataSource: 'live',       // 'live' | 'sample'
  currentTier: 'medium',    // sample tier (only used when dataSource === 'sample')
  anchorDate: null,          // ISO date string — the "as of" anchor for filtering
  activePresetDays: 30,      // which preset is active (7, 30, 90, or null for All)
  dateRange: null,           // { start, end } from meta — article publication dates
  isLoading: false,
  cy: null,
  navigator: null,
  navigatorVisible: true,
  filter: null               // GraphFilter instance, set during init
};

/**
 * Initialize theme from OS preference or saved preference.
 * Saved preference (localStorage) overrides OS detection.
 */
function initTheme() {
  const saved = localStorage.getItem('theme');
  if (saved) {
    document.documentElement.setAttribute('data-theme', saved);
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
  // else: no attribute = light mode (default)

  // Listen for OS theme changes (only if no saved preference)
  window.matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', (e) => {
      if (!localStorage.getItem('theme')) {
        document.documentElement.setAttribute(
          'data-theme', e.matches ? 'dark' : 'light'
        );
        reapplyGraphStyles();
      }
    });
}

/**
 * Toggle theme between light and dark. Saves to localStorage.
 */
function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  reapplyGraphStyles();
}

/**
 * Re-read CSS variables and reapply Cytoscape styles.
 * Must be called after any theme change.
 */
function reapplyGraphStyles() {
  if (AppState.cy) {
    AppState.cy.style(getCytoscapeStyles());
    AppState.cy.style().update();
  }
}

/**
 * Initialize the navigator minimap.
 * Must be called after Cytoscape is initialized.
 */
function initNavigator(cy) {
  // Destroy existing navigator if present
  if (AppState.navigator) {
    AppState.navigator.destroy();
    AppState.navigator = null;
  }

  const container = document.getElementById('cy-navigator');
  if (!container || !cy) return;

  // Check if navigator extension is available
  if (typeof cy.navigator !== 'function') {
    console.warn('Cytoscape navigator extension not loaded');
    container.classList.add('hidden');
    return;
  }

  try {
    // Clear container and let extension create fresh content
    container.innerHTML = '';

    AppState.navigator = cy.navigator({
      container: '#cy-navigator',
      viewLiveFramerate: 60,
      thumbnailEventFramerate: 30,
      thumbnailLiveFramerate: false,
      dblClickDelay: 200,
      removeCustomContainer: false,
      rerenderDelay: 100
    });

    // Force resize and update after initialization
    setTimeout(() => {
      if (AppState.navigator) {
        cy.resize();
        cy.fit();
      }
    }, 200);

    // Apply visibility state
    if (!AppState.navigatorVisible) {
      container.classList.add('hidden');
    } else {
      container.classList.remove('hidden');
    }

    console.log('Navigator minimap initialized');
  } catch (error) {
    console.error('Failed to initialize navigator:', error);
    container.classList.add('hidden');
  }
}

/**
 * Toggle navigator minimap visibility.
 */
function toggleNavigator() {
  const container = document.getElementById('cy-navigator');
  const btn = document.getElementById('btn-minimap');

  AppState.navigatorVisible = !AppState.navigatorVisible;

  if (container) {
    container.classList.toggle('hidden', !AppState.navigatorVisible);
  }

  if (btn) {
    btn.classList.toggle('active', AppState.navigatorVisible);
  }
}

/**
 * Get data URL for a view, based on current data source.
 * Live → data/graphs/live/{view}.json
 * Sample → data/graphs/{tier}/{view}.json
 */
function getDataUrl(view) {
  const basePath = 'data/graphs';
  const folder = AppState.dataSource === 'sample'
    ? (AppState.currentTier || 'medium')
    : 'live';
  return `${basePath}/${folder}/${view}.json`;
}

/**
 * Switch to a different data source or tier. Reloads graph data.
 */
async function switchDataSource(source, tier) {
  AppState.dataSource = source;
  if (tier) AppState.currentTier = tier;
  await switchView(AppState.currentView);
}

/**
 * Initialize the application
 */
async function initializeApp() {
  console.log('Initializing AI Trend Graph...');

  // Initialize theme BEFORE any rendering
  initTheme();

  try {
    // Show loading state
    showLoading('Initializing...');

    // Get container
    const container = document.getElementById('cy');
    if (!container) {
      throw new Error('Graph container not found');
    }

    // Set anchor date to today
    AppState.anchorDate = today();
    const dateInput = document.getElementById('date-anchor');
    if (dateInput) {
      dateInput.value = AppState.anchorDate;
    }

    // Default to live data — pipeline produces live graphs daily.
    // Users can switch to sample data via the filter panel if needed.
    AppState.dataSource = 'live';

    // Sync the radio buttons to match
    const liveRadio = document.querySelector('input[name="data-source"][value="live"]');
    if (liveRadio) liveRadio.checked = true;
    const sampleList = document.getElementById('sample-tier-list');
    if (sampleList) sampleList.classList.add('hidden');

    // Load default data
    const dataUrl = getDataUrl(AppState.currentView);
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
    AppState.filter = initializeFilters(AppState.cy);

    // Apply default 30-day filter based on anchor date
    applyDateFilterFromAnchor();

    initializeHelp();
    initializeToolbar(AppState.cy);

    // Wire theme toggle button
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', () => {
        toggleTheme();
        const icon = document.getElementById('theme-icon');
        if (icon) {
          const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
          icon.textContent = isDark ? '☀' : '☾';
        }
      });

      // Set initial icon state
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      const themeIcon = document.getElementById('theme-icon');
      if (themeIcon) {
        themeIcon.textContent = isDark ? '☀' : '☾';
      }
    }

    // Run initial layout and initialize navigator after it completes
    const layout = runLayout(AppState.cy);
    layout.on('layoutstop', () => {
      // Initialize navigator minimap after layout is done
      initNavigator(AppState.cy);
    });

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
 * Highlight the neighborhood of a node (connected edges + neighbor nodes).
 * Dims everything else. Skips if a search is active to avoid conflicts.
 */
function highlightNeighborhood(cy, node) {
  // Don't override active search dimming
  if (cy.nodes('.search-match').length > 0) return;

  const neighborhood = node.closedNeighborhood();

  cy.elements().addClass('neighborhood-dimmed');
  neighborhood.removeClass('neighborhood-dimmed');
  neighborhood.edges().removeClass('neighborhood-dimmed');
}

/**
 * Clear neighborhood highlighting.
 */
function clearNeighborhoodHighlight(cy) {
  cy.elements().removeClass('neighborhood-dimmed');
}

/**
 * Initialize event handlers for the graph
 */
function initializeEventHandlers(cy) {
  // Node click - highlight neighborhood + open detail panel
  cy.on('tap', 'node', (e) => {
    const node = e.target;
    cy.elements().unselect();
    node.select();
    clearNeighborhoodHighlight(cy);
    highlightNeighborhood(cy, node);
    openNodeDetailPanel(node);
  });

  // Edge click - open evidence panel
  cy.on('tap', 'edge', (e) => {
    const edge = e.target;
    cy.elements().unselect();
    edge.select();
    clearNeighborhoodHighlight(cy);
    openEvidencePanel(edge);
  });

  // Background click - close panels and clear highlight
  cy.on('tap', (e) => {
    if (e.target === cy) {
      closeAllPanels();
      cy.elements().unselect();
      clearNeighborhoodHighlight(cy);
    }
  });

  // Double-click node: zoom to neighborhood
  cy.on('dbltap', 'node', (e) => {
    const node = e.target;
    const neighborhood = node.closedNeighborhood();
    cy.animate({
      fit: { eles: neighborhood, padding: 50 },
      duration: 300
    });
  });

  // Double-click background: fit all
  cy.on('dbltap', (e) => {
    if (e.target === cy) {
      cy.animate({
        fit: { padding: 30 },
        duration: 300
      });
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

  // Global keyboard shortcuts (? for help)
  document.addEventListener('keydown', (e) => {
    handleGlobalKeyboard(e);
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

  // Minimap toggle
  document.getElementById('btn-minimap')?.addEventListener('click', () => {
    toggleNavigator();
  });

  // Filter toggle
  const filterBtn = document.getElementById('btn-filter');
  if (filterBtn) {
    filterBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      toggleFilterPanel();
    });
  }

  // Help button
  document.getElementById('btn-help')?.addEventListener('click', () => {
    toggleHelpPanel();
  });

  // View selector
  document.getElementById('view-selector')?.addEventListener('change', async (e) => {
    await switchView(e.target.value);
  });

  // Anchor date picker
  document.getElementById('date-anchor')?.addEventListener('change', (e) => {
    AppState.anchorDate = e.target.value || today();
    applyDateFilterFromAnchor();
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
      clearNeighborhoodHighlight(cy);
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
 * Handle global keyboard shortcuts
 */
function handleGlobalKeyboard(e) {
  // Don't handle if typing in an input field
  const activeElement = document.activeElement;
  if (activeElement && (
    activeElement.tagName === 'INPUT' ||
    activeElement.tagName === 'TEXTAREA' ||
    activeElement.isContentEditable
  )) {
    return;
  }

  switch (e.key) {
    case '?':
      // Toggle help panel
      toggleHelpPanel();
      e.preventDefault();
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
    clearNeighborhoodHighlight(cy);
    highlightNeighborhood(cy, best);
    openNodeDetailPanel(best);
    e.preventDefault();
  }
}

/**
 * Switch to a different view
 */
async function switchView(view) {
  AppState.currentView = view;
  const dataUrl = getDataUrl(view);

  try {
    showLoading('Switching view...');
    const data = await loadGraphData(dataUrl);

    // Clear and reload
    AppState.cy.elements().remove();
    addElements(AppState.cy, data.elements);

    // Re-run layout and re-initialize navigator after it completes
    const layout = runLayout(AppState.cy);
    layout.on('layoutstop', () => {
      initNavigator(AppState.cy);
    });

    // Refresh filter panel counts and re-bind event handlers for new data
    if (AppState.filter) {
      // Sync viewPreset to match the active view — the trending
      // velocity filter should only apply in the trending view;
      // claims/mentions/dependencies should show all matching nodes.
      AppState.filter.setViewPreset(view === 'trending' ? 'trending' : 'all');
      populateTypeFilters(AppState.cy, AppState.filter);
      syncFilterUI(AppState.filter);
      applyDateFilterFromAnchor();
    }

    // Update stats
    updateStatsDisplay(AppState.cy);

    hideLoading();

    // Announce
    const stats = getGraphStats(AppState.cy);
    announceToScreenReader(`Switched to ${view} view. ${stats.nodeCount} nodes.`);

  } catch (error) {
    console.error('Failed to switch view:', error);
    hideLoading();
    // Show a non-fatal warning — don't crash the UI
    showWarning(
      `Could not load "${view}" view. The data may not exist for this selection.`
    );
  }
}

/**
 * Update statistics display in toolbar
 */
function updateStatsDisplay(cy) {
  const stats = getGraphStats(cy);
  const el = document.getElementById('graph-stats');
  if (el) {
    el.textContent = `${stats.nodeCount} nodes \u00B7 ${stats.edgeCount} edges`;
  }
  console.log('Graph stats:', stats);
}

/**
 * Toggle filter panel
 */
function toggleFilterPanel() {
  const panel = document.getElementById('filter-panel');
  if (panel) {
    const wasCollapsed = panel.classList.contains('collapsed');
    panel.classList.toggle('collapsed');

    // Update cy container if function exists
    if (typeof updateCyContainer === 'function') {
      updateCyContainer();
    } else {
      // Fallback: directly toggle the cy class
      const cyEl = document.getElementById('cy');
      if (cyEl) {
        cyEl.classList.toggle('panel-right-open', wasCollapsed);
        if (window.cy) {
          setTimeout(() => window.cy.resize(), 50);
        }
      }
    }
  }
}

/**
 * Apply date filter computed from the anchor date and active preset.
 * Called when anchor date changes or when a preset button is clicked.
 */
function applyDateFilterFromAnchor() {
  const filter = AppState.filter;
  if (!filter) return;

  const anchor = AppState.anchorDate || today();
  const days = AppState.activePresetDays;

  if (days === null) {
    // "All" preset — no date filtering
    filter.setDateRange(null, null);
  } else {
    const endDate = anchor;
    const startMs = new Date(anchor).getTime() - days * 86400000;
    const startDate = new Date(startMs).toISOString().split('T')[0];
    filter.setDateRange(startDate, endDate);
  }

  filter.apply();

  // Update the date range info display
  updateDateRangeDisplay();

  // Sync preset button active states
  const presetBtns = document.querySelectorAll('.date-presets button');
  presetBtns.forEach(btn => {
    const btnDays = btn.dataset.days;
    const isActive = (days === null && btnDays === 'all') ||
                     (days !== null && btnDays === String(days));
    btn.classList.toggle('active', isActive);
  });

  console.log(`Date filter applied: anchor=${anchor}, preset=${days}d`);
}

/**
 * Update the date range info text next to the anchor date picker.
 */
function updateDateRangeDisplay() {
  const dateInfo = document.getElementById('date-range-info');
  if (!dateInfo) return;

  const anchor = AppState.anchorDate || today();
  const days = AppState.activePresetDays;

  if (days === null) {
    dateInfo.textContent = 'All dates';
    dateInfo.title = 'Showing all dates';
  } else {
    const startMs = new Date(anchor).getTime() - days * 86400000;
    const startDate = new Date(startMs).toISOString().split('T')[0];
    dateInfo.textContent = `${formatDate(startDate)} – ${formatDate(anchor)}`;
    dateInfo.title = `Showing ${days} days ending ${anchor}`;
  }
}

// updateCyContainer and closeAllPanels are defined in panels.js

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', initializeApp);
