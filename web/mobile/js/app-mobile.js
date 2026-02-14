/**
 * Mobile Application Entry Point
 *
 * Simplified init for mobile: no minimap, no navigator, no hover tooltips.
 * Tap = select + detail sheet. Long-press = context actions.
 *
 * MINIMAP NOTE: The desktop minimap (cytoscape-navigator) has known issues:
 *   - Default transparent background makes it hard to read on large graphs
 *   - Opaque background causes other visual issues
 *   - The selection rectangle is not draggable
 * On mobile we skip the minimap entirely. Pinch-zoom + fit-to-screen
 * covers the same use case. If the desktop minimap issues get fixed
 * (e.g. a semi-opaque background + draggable viewport rect), it could
 * potentially be added to tablet layouts in the future.
 */

// Default date window (matches desktop)
var DEFAULT_DATE_WINDOW_DAYS = 30;

// Mobile-specific scale thresholds (lower than desktop)
var MOBILE_SCALE_THRESHOLDS = {
  OPTIMAL: 50,
  ACCEPTABLE: 200,
  WARNING: 500,
  DANGER: 2000
};

// Application state (mirrors desktop AppState, no navigator)
var AppState = {
  currentView: 'trending',
  dataSource: 'live',
  currentTier: 'medium',
  anchorDate: null,
  activePresetDays: 30,
  dateRange: null,
  isLoading: false,
  cy: null,
  filter: null
};

// Global reference for mobile app subsystems
window.MobileApp = {
  sheetTouch: null,
  longPress: null
};

/* ============================================================
   Theme
   ============================================================ */

function initTheme() {
  var saved = localStorage.getItem('theme');
  if (saved) {
    document.documentElement.setAttribute('data-theme', saved);
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }

  window.matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', function(e) {
      if (!localStorage.getItem('theme')) {
        document.documentElement.setAttribute(
          'data-theme', e.matches ? 'dark' : 'light'
        );
        reapplyGraphStyles();
      }
    });
}

function toggleTheme() {
  var current = document.documentElement.getAttribute('data-theme');
  var next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  reapplyGraphStyles();
}

function reapplyGraphStyles() {
  if (AppState.cy) {
    AppState.cy.style(getCytoscapeStyles());
    AppState.cy.style().update();
  }
}

/* ============================================================
   Data URL
   ============================================================ */

function getDataUrl(view) {
  var basePath = '../data/graphs';
  var folder = AppState.dataSource === 'sample'
    ? (AppState.currentTier || 'medium')
    : 'live';
  return basePath + '/' + folder + '/' + view + '.json';
}

async function switchDataSource(source, tier) {
  AppState.dataSource = source;
  if (tier) AppState.currentTier = tier;
  await switchView(AppState.currentView);
}

/* ============================================================
   Neighborhood highlight (same as desktop)
   ============================================================ */

function highlightNeighborhood(cy, node) {
  if (cy.nodes('.search-match').length > 0) return;
  var neighborhood = node.closedNeighborhood();
  cy.elements().addClass('neighborhood-dimmed');
  neighborhood.removeClass('neighborhood-dimmed');
  neighborhood.edges().removeClass('neighborhood-dimmed');
}

function clearNeighborhoodHighlight(cy) {
  cy.elements().removeClass('neighborhood-dimmed');
}

/* ============================================================
   Event Handlers (mobile-specific)
   ============================================================ */

function initializeMobileEventHandlers(cy) {
  // Node tap → select + open detail bottom sheet
  cy.on('tap', 'node', function(e) {
    var node = e.target;
    cy.elements().unselect();
    node.select();
    clearNeighborhoodHighlight(cy);
    highlightNeighborhood(cy, node);
    openNodeDetailSheet(node);
  });

  // Edge tap → open evidence bottom sheet
  cy.on('tap', 'edge', function(e) {
    var edge = e.target;
    cy.elements().unselect();
    edge.select();
    clearNeighborhoodHighlight(cy);
    openEdgeEvidenceSheet(edge);
  });

  // Background tap → dismiss sheet + clear highlight
  cy.on('tap', function(e) {
    if (e.target === cy) {
      dismissBottomSheet();
      cy.elements().unselect();
      clearNeighborhoodHighlight(cy);
    }
  });

  // Double-tap node → zoom to neighborhood
  cy.on('dbltap', 'node', function(e) {
    var node = e.target;
    var neighborhood = node.closedNeighborhood();
    cy.animate({
      fit: { eles: neighborhood, padding: 50 },
      duration: 300
    });
  });

  // Double-tap background → fit all
  cy.on('dbltap', function(e) {
    if (e.target === cy) {
      cy.animate({
        fit: { padding: 30 },
        duration: 300
      });
    }
  });

  // Zoom change → update labels
  cy.on('zoom', function() {
    updateLabelVisibility(cy);
  });

  // Long-press → context menu (expand neighbors + center)
  window.MobileApp.longPress = new LongPressDetector(cy, {
    duration: 500,
    onLongPress: function(node) {
      // On long-press, expand neighbors immediately
      var neighborhood = node.closedNeighborhood();
      neighborhood.removeClass('filtered-out').show();
      cy.animate({
        fit: { eles: neighborhood, padding: 50 },
        duration: 300
      });
      if (typeof updateLabelVisibility === 'function') {
        updateLabelVisibility(cy);
      }
    }
  });
}

/* ============================================================
   Menu, Search, Toolbar
   ============================================================ */

function initializeMobileToolbar(cy) {
  // Hamburger menu
  var menuBtn = document.getElementById('btn-menu');
  var menuOverlay = document.getElementById('menu-overlay');

  if (menuBtn && menuOverlay) {
    menuBtn.addEventListener('click', function() {
      var isVisible = menuOverlay.classList.contains('visible');
      if (isVisible) {
        menuOverlay.classList.remove('visible');
        setTimeout(function() { menuOverlay.classList.add('hidden'); }, 300);
      } else {
        menuOverlay.classList.remove('hidden');
        menuOverlay.offsetHeight; // force reflow
        menuOverlay.classList.add('visible');
      }
    });

    // Tap outside menu content to close
    menuOverlay.addEventListener('click', function(e) {
      if (e.target === menuOverlay) {
        menuOverlay.classList.remove('visible');
        setTimeout(function() { menuOverlay.classList.add('hidden'); }, 300);
      }
    });
  }

  // View selector (in menu)
  var viewOptions = document.querySelectorAll('.menu-option[data-view]');
  viewOptions.forEach(function(btn) {
    btn.addEventListener('click', function() {
      viewOptions.forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      switchView(btn.dataset.view);
      // Close menu
      if (menuOverlay) {
        menuOverlay.classList.remove('visible');
        setTimeout(function() { menuOverlay.classList.add('hidden'); }, 300);
      }
    });
  });

  // Date presets (in menu)
  var menuPresets = document.querySelectorAll('.menu-content .date-presets button');
  menuPresets.forEach(function(btn) {
    btn.addEventListener('click', function() {
      var days = btn.dataset.days;
      AppState.activePresetDays = (days === 'all') ? null : parseInt(days);
      menuPresets.forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      applyDateFilterFromAnchor();
    });
  });

  // Date anchor (in menu)
  var dateAnchor = document.getElementById('date-anchor');
  if (dateAnchor) {
    dateAnchor.addEventListener('change', function(e) {
      AppState.anchorDate = e.target.value || today();
      applyDateFilterFromAnchor();
    });
  }

  // Layout button
  var layoutBtn = document.getElementById('btn-layout-menu');
  if (layoutBtn) {
    layoutBtn.addEventListener('click', function() {
      runLayout(cy);
      if (menuOverlay) {
        menuOverlay.classList.remove('visible');
        setTimeout(function() { menuOverlay.classList.add('hidden'); }, 300);
      }
    });
  }

  // Fit button
  var fitBtn = document.getElementById('btn-fit-menu');
  if (fitBtn) {
    fitBtn.addEventListener('click', function() {
      fitGraph(cy);
      if (menuOverlay) {
        menuOverlay.classList.remove('visible');
        setTimeout(function() { menuOverlay.classList.add('hidden'); }, 300);
      }
    });
  }

  // Theme toggle (in menu)
  var themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', function() {
      toggleTheme();
      var icon = document.getElementById('theme-icon');
      if (icon) {
        var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        icon.innerHTML = isDark ? '&#x2600;' : '&#x263E;';
      }
    });
  }

  // Search button → open search overlay
  var searchBtn = document.getElementById('btn-search');
  var searchOverlay = document.getElementById('search-overlay');
  var searchInput = document.getElementById('search-input');
  var searchClose = document.getElementById('search-close');

  if (searchBtn && searchOverlay) {
    searchBtn.addEventListener('click', function() {
      searchOverlay.classList.remove('hidden');
      searchOverlay.offsetHeight;
      searchOverlay.classList.add('visible');
      if (searchInput) searchInput.focus();
    });
  }

  if (searchClose && searchOverlay) {
    searchClose.addEventListener('click', function() {
      searchOverlay.classList.remove('visible');
      setTimeout(function() { searchOverlay.classList.add('hidden'); }, 200);
      // Clear search
      if (searchInput) searchInput.value = '';
      performSearch(cy, '');
    });
  }

  // Initialize search on the input (reuse shared search.js)
  initializeSearch(cy);

  // Filter button → open filter modal
  var filterBtn = document.getElementById('btn-filter');
  if (filterBtn) {
    filterBtn.addEventListener('click', openMobileFilterModal);
  }
}

/* ============================================================
   Date filter (same logic as desktop)
   ============================================================ */

function applyDateFilterFromAnchor() {
  var filter = AppState.filter;
  if (!filter) return;

  var anchor = AppState.anchorDate || today();
  var days = AppState.activePresetDays;

  if (days === null) {
    filter.setDateRange(null, null);
  } else {
    var endDate = anchor;
    var startMs = new Date(anchor).getTime() - days * 86400000;
    var startDate = new Date(startMs).toISOString().split('T')[0];
    filter.setDateRange(startDate, endDate);
  }

  filter.apply();
}

/* ============================================================
   Stats display
   ============================================================ */

function updateStatsDisplay(cy) {
  var stats = getGraphStats(cy);
  var el = document.getElementById('graph-stats');
  if (el) {
    el.textContent = stats.nodeCount + ' nodes \u00B7 ' + stats.edgeCount + ' edges';
  }
}

/* ============================================================
   Switch View
   ============================================================ */

async function switchView(view) {
  AppState.currentView = view;
  var dataUrl = getDataUrl(view);

  try {
    showLoading('Switching view...');
    var data = await loadGraphData(dataUrl);

    AppState.cy.elements().remove();
    addElements(AppState.cy, data.elements);

    runLayout(AppState.cy);

    if (AppState.filter) {
      applyDateFilterFromAnchor();
    }

    updateStatsDisplay(AppState.cy);
    hideLoading();

    var stats = getGraphStats(AppState.cy);
    announceToScreenReader('Switched to ' + view + ' view. ' + stats.nodeCount + ' nodes.');

  } catch (error) {
    console.error('Failed to switch view:', error);
    hideLoading();
    showWarning('Could not load "' + view + '" view.');
  }
}

/* ============================================================
   Initialize
   ============================================================ */

async function initializeApp() {
  console.log('Initializing AI Trend Graph (mobile)...');

  initTheme();

  try {
    showLoading('Initializing...');

    var container = document.getElementById('cy');
    if (!container) throw new Error('Graph container not found');

    // Set anchor date
    AppState.anchorDate = today();
    var dateInput = document.getElementById('date-anchor');
    if (dateInput) dateInput.value = AppState.anchorDate;

    // Default to sample data
    AppState.dataSource = 'sample';
    AppState.currentTier = 'medium';
    var sampleRadio = document.querySelector('input[name="data-source"][value="sample"]');
    if (sampleRadio) sampleRadio.checked = true;
    var sampleList = document.getElementById('sample-tier-list');
    if (sampleList) sampleList.classList.remove('hidden');

    // Load data
    var dataUrl = getDataUrl(AppState.currentView);
    var data = await loadGraphData(dataUrl);

    // Initialize Cytoscape (no minimap, no navigator)
    AppState.cy = initializeGraph(container, data, getCytoscapeStyles());
    window.cy = AppState.cy;

    // Initialize mobile-specific handlers
    initializeMobileEventHandlers(AppState.cy);
    initializeMobileToolbar(AppState.cy);

    // Initialize filter (reuse shared GraphFilter class)
    AppState.filter = new GraphFilter(AppState.cy);
    initializeMobileFilterPanel(AppState.filter);

    // Apply default date filter
    applyDateFilterFromAnchor();

    // Initialize bottom sheet touch controller
    var sheet = document.getElementById('bottom-sheet');
    if (sheet) {
      window.MobileApp.sheetTouch = new BottomSheetTouch(sheet, {
        onStateChange: function(state) {
          console.log('Bottom sheet state:', state);
        }
      });
    }

    // Set initial theme icon
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    var themeIcon = document.getElementById('theme-icon');
    if (themeIcon) {
      themeIcon.innerHTML = isDark ? '&#x2600;' : '&#x263E;';
    }

    // Run layout
    runLayout(AppState.cy);

    updateStatsDisplay(AppState.cy);
    hideLoading();

    var stats = getGraphStats(AppState.cy);
    announceToScreenReader(
      'Graph loaded with ' + stats.nodeCount + ' nodes and ' + stats.edgeCount + ' edges.'
    );

    console.log('Mobile app initialized successfully');

  } catch (error) {
    console.error('Failed to initialize mobile app:', error);
    hideLoading();
    showError('Failed to initialize: ' + error.message);
  }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', initializeApp);
