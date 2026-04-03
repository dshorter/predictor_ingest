/**
 * Guided Tour — Driver.js + Cytoscape orchestration
 *
 * Two-layer model:
 *   1. Driver.js handles spotlight/popover/dimming (DOM only)
 *   2. This script operates the app between steps (fly-to, select, open panels)
 *
 * See docs/ux/guided-tour-spec.md for the full design spec.
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TOUR_VERSION = 1;
const TOUR_STORAGE_KEY = `tour-completed-v${TOUR_VERSION}`;
const SPOTLIGHT_NODE_ID = 'org:apex-studios';
const EVIDENCE_EDGE_ID = 'e:nova-forge'; // PARTNERED_WITH — good evidence

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Check if tour has been completed (respects versioning). */
function isTourCompleted() {
  try {
    return localStorage.getItem(TOUR_STORAGE_KEY) === 'true';
  } catch { return false; }
}

/** Mark tour as completed. */
function markTourCompleted() {
  try { localStorage.setItem(TOUR_STORAGE_KEY, 'true'); } catch {}
}

/** Reset tour state so it replays on next sample-data load. */
function resetTour() {
  try { localStorage.removeItem(TOUR_STORAGE_KEY); } catch {}
}

/** Detect if the currently loaded graph data is sample data. */
function isSampleData() {
  return window._graphMeta?.isSample === true;
}

/** Small delay helper. */
function tourDelay(ms) {
  if (window.prefersReducedMotion) return Promise.resolve();
  return new Promise(r => setTimeout(r, ms));
}

// ---------------------------------------------------------------------------
// Tour steps
// ---------------------------------------------------------------------------

function buildTourSteps() {
  return [
    // --- Stop 1: Welcome ---
    {
      element: '#cy',
      popover: {
        title: 'Welcome — This is a knowledge graph',
        description:
          'You\'re looking at a live knowledge graph — entities connected by ' +
          'relationships extracted from real sources. Nodes are sized by how ' +
          'fast they\'re trending.',
        side: 'top',
        align: 'center'
      }
    },

    // --- Stop 2: Entities ---
    {
      element: '#cy',
      popover: {
        title: 'Entities are the building blocks',
        description:
          'Each node is an entity — an organization, person, tool, or concept. ' +
          'The color tells you the type. The size tells you how fast it\'s trending. ' +
          'We just flew to <strong>Apex Studios</strong> — it\'s connected to many other entities.',
        side: 'top',
        align: 'center'
      },
      onHighlightStarted: () => {
        if (typeof navigateToNode === 'function') {
          navigateToNode(SPOTLIGHT_NODE_ID, { zoom: true, updatePanel: false });
        }
      }
    },

    // --- Stop 3: Detail panel ---
    {
      element: '#detail-panel',
      popover: {
        title: 'Click a node to see its story',
        description:
          'The detail panel shows everything we know: when it first appeared, ' +
          'how active it is, and why it\'s trending. The narrative is generated ' +
          'by AI from the underlying evidence.',
        side: 'right',
        align: 'start'
      },
      onHighlightStarted: () => {
        if (typeof navigateToNode === 'function') {
          navigateToNode(SPOTLIGHT_NODE_ID, { zoom: false, updatePanel: true });
        }
      }
    },

    // --- Stop 4: Evidence panel ---
    {
      element: '#evidence-panel',
      popover: {
        title: 'Relationships link back to real sources',
        description:
          'Every relationship links back to the source document where it was found. ' +
          'You can see the exact snippet, the publication date, and a link to the ' +
          'original article. Nothing is asserted without evidence.',
        side: 'right',
        align: 'start'
      },
      onHighlightStarted: () => {
        const cy = window.cy;
        if (!cy) return;
        const edge = cy.getElementById(EVIDENCE_EDGE_ID);
        if (edge && edge.length) {
          cy.elements().unselect();
          if (typeof clearNeighborhoodHighlight === 'function') {
            clearNeighborhoodHighlight(cy);
          }
          edge.select();
          if (typeof openEvidencePanel === 'function') {
            openEvidencePanel(edge);
          }
        }
      }
    },

    // --- Stop 5: What's Hot ---
    {
      element: '#hot-panel',
      popover: {
        title: 'What\'s Hot tells you where to look',
        description:
          'The What\'s Hot list ranks entities by velocity — how quickly they\'re ' +
          'gaining attention. Each entry includes a narrative explaining WHY it\'s ' +
          'trending. Click any item to fly to it on the graph.',
        side: 'right',
        align: 'start'
      },
      onHighlightStarted: () => {
        if (typeof toggleHotPanel === 'function') {
          toggleHotPanel();
        }
      }
    },

    // --- Stop 6: Filter panel ---
    {
      element: '#filter-panel',
      popover: {
        title: 'Filter to focus',
        description:
          'Use filters to narrow the graph by entity type, date range, or ' +
          'confidence level. Uncheck a type to hide those nodes. Drag the ' +
          'confidence slider to show only high-certainty relationships.',
        side: 'left',
        align: 'start'
      },
      onHighlightStarted: () => {
        // Close hot panel, open filter panel
        const hotPanel = document.getElementById('hot-panel');
        if (hotPanel && !hotPanel.classList.contains('hidden')) {
          if (typeof toggleHotPanel === 'function') toggleHotPanel();
        }
        const filterPanel = document.getElementById('filter-panel');
        if (filterPanel && filterPanel.classList.contains('collapsed')) {
          if (typeof toggleFilterPanel === 'function') {
            toggleFilterPanel();
          } else {
            filterPanel.classList.remove('collapsed');
          }
        }
      }
    },

    // --- Stop 7: View switcher ---
    {
      element: '#view-selector',
      popover: {
        title: 'Switch views to change the lens',
        description:
          'Four views show different slices of the same data. ' +
          '<strong>Trending</strong> is your home base. ' +
          '<strong>Claims</strong> shows asserted relationships. ' +
          '<strong>Mentions</strong> shows co-occurrence. ' +
          '<strong>Dependencies</strong> shows tech stacks.',
        side: 'bottom',
        align: 'start'
      },
      onHighlightStarted: () => {
        // Close filter panel
        const filterPanel = document.getElementById('filter-panel');
        if (filterPanel && !filterPanel.classList.contains('collapsed')) {
          if (typeof toggleFilterPanel === 'function') {
            toggleFilterPanel();
          } else {
            filterPanel.classList.add('collapsed');
          }
        }
      }
    },

    // --- Stop 8: Go explore ---
    {
      element: '#cy',
      popover: {
        title: 'You\'re ready — start exploring',
        description:
          'That\'s it! You\'re viewing sample data — click around and experiment. ' +
          'When you\'re ready for real data, use the banner at the top.' +
          '<br><br>' +
          '<button class="tour-btn tour-btn-primary" onclick="switchToLiveData()">Switch to Live Data</button> ' +
          '<button class="tour-btn tour-btn-secondary" onclick="window._tourDriver?.destroy()">Keep Exploring</button>',
        side: 'top',
        align: 'center'
      },
      onHighlightStarted: () => {
        const cy = window.cy;
        if (!cy) return;
        // Close all panels, fit graph
        if (typeof closeAllPanels === 'function') {
          closeAllPanels();
        } else {
          if (typeof closeLeftPanels === 'function') closeLeftPanels();
          const fp = document.getElementById('filter-panel');
          if (fp && !fp.classList.contains('collapsed')) fp.classList.add('collapsed');
        }
        cy.fit(undefined, 40);
        if (typeof clearNeighborhoodHighlight === 'function') {
          clearNeighborhoodHighlight(cy);
        }
        cy.elements().unselect();
      }
    }
  ];
}

// ---------------------------------------------------------------------------
// Sample data banner
// ---------------------------------------------------------------------------

/** Create and insert the sample data indicator banner. */
function showSampleBanner() {
  if (document.getElementById('sample-banner')) return;

  const banner = document.createElement('div');
  banner.id = 'sample-banner';
  banner.className = 'sample-banner';
  banner.innerHTML =
    '<span class="sample-banner-icon">\u{1F9EA}</span>' +
    '<span class="sample-banner-text">' +
      'You\'re viewing sample data' +
    '</span>' +
    '<span style="color:var(--color-text-tertiary);">\u00B7</span>' +
    '<a href="javascript:void(0)" class="sample-banner-link" onclick="switchToLiveData()">' +
      'Switch to live data \u2192' +
    '</a>' +
    '<span style="color:var(--color-text-tertiary);">\u00B7</span>' +
    '<a href="javascript:void(0)" class="sample-banner-link" onclick="retakeTour()">' +
      'Retake tour' +
    '</a>';

  // Insert after toolbar, before the graph container
  const toolbar = document.getElementById('toolbar');
  if (toolbar && toolbar.nextElementSibling) {
    toolbar.parentNode.insertBefore(banner, toolbar.nextElementSibling);
  }
}

/** Remove the sample data banner. */
function hideSampleBanner() {
  const banner = document.getElementById('sample-banner');
  if (banner) banner.remove();
}

// ---------------------------------------------------------------------------
// Navigation actions (called from tour buttons and banner)
// ---------------------------------------------------------------------------

/** Switch from sample data to live data. */
function switchToLiveData() {
  markTourCompleted();
  // Navigate to clean URL — let app.js load with default live domain
  const url = new URL(window.location.href);
  url.searchParams.delete('sample');
  url.searchParams.delete('tour');
  window.location.href = url.toString();
}

/** Reset tour and restart with sample data. */
function retakeTour() {
  resetTour();
  const url = new URL(window.location.href);
  url.searchParams.set('sample', '1');
  url.searchParams.set('tour', '1');
  window.location.href = url.toString();
}

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

/**
 * Start the guided tour. Called from app.js after graph loads.
 * Requires Driver.js to be loaded globally (`window.driver`).
 */
function startTour() {
  // Guard: Driver.js must be available
  if (typeof window.driver === 'undefined' || !window.driver.js) {
    console.warn('Tour: Driver.js not loaded, skipping tour');
    return;
  }

  const { driver } = window.driver.js;

  const driverInstance = driver({
    showProgress: true,
    animate: !window.prefersReducedMotion,
    smoothScroll: true,
    stagePadding: 8,
    stageRadius: 8,
    allowClose: true,
    overlayColor: 'rgba(0, 0, 0, 0.6)',
    popoverClass: 'tour-popover',
    onDestroyed: () => {
      markTourCompleted();
      window._tourDriver = null;
    },
    steps: buildTourSteps()
  });

  // Expose for the "Keep Exploring" button
  window._tourDriver = driverInstance;

  driverInstance.drive();
}

/**
 * Initialize tour system. Called from app.js after graph + components are ready.
 * Decides whether to show banner, auto-start tour, or do nothing.
 */
function initTour() {
  const urlParams = new URLSearchParams(window.location.search);
  const forceSample = urlParams.has('sample');
  const forceTour = urlParams.has('tour');

  if (isSampleData() || forceSample) {
    showSampleBanner();

    if (forceTour || !isTourCompleted()) {
      // Brief delay so the graph settles before tour starts
      setTimeout(() => startTour(), 600);
    }
  }
}
