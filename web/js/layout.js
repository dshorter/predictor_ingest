/**
 * Layout Management
 *
 * Force-directed layout using fcose algorithm.
 * fcose = fast compound spring embedder - optimized for larger graphs.
 *
 * Parameter Hunt Status: IN PROGRESS
 * Key insight: nodeSeparation controls spectral phase spacing
 *
 * See docs/ux/layout-temporal.md for specification.
 * See docs/fix-details/FCOSE_LAYOUT_ANALYSIS.md for research.
 */

/**
 * Register fcose extension with Cytoscape
 */
function registerFcose() {
  if (typeof cytoscape === 'undefined') {
    console.error('Cytoscape not loaded');
    return false;
  }

  if (typeof cytoscapeFcose !== 'undefined') {
    cytoscape.use(cytoscapeFcose);
    console.log('fcose registered successfully');
    return true;
  }

  console.warn('fcose extension not found - will fall back to cose');
  return false;
}

/**
 * Default layout options for fcose
 *
 * PARAMETER HUNT - adjust these values to find optimal spread:
 * - nodeSeparation: spacing in spectral phase (THE KEY PARAM)
 * - nodeRepulsion: force pushing nodes apart
 * - idealEdgeLength: target edge length
 * - gravity: pull toward center (lower = more spread)
 */
const LAYOUT_OPTIONS = {
  name: 'fcose',

  // Quality vs speed: 'draft', 'default', or 'proof'
  quality: 'default',

  // Animation
  animate: true,
  animationDuration: 500,
  animationEasing: 'ease-out',

  // Fit to viewport
  fit: true,
  padding: 50,

  // Randomize starting positions
  randomize: true,

  // === KEY SPECTRAL PHASE PARAMETERS ===
  // nodeSeparation: THE FIX - controls spacing in spectral layout phase
  nodeSeparation: 75,

  // === FORCE-DIRECTED PHASE PARAMETERS ===
  // Node repulsion force
  nodeRepulsion: 4500,

  // Ideal edge length
  idealEdgeLength: 50,

  // Edge elasticity
  edgeElasticity: 0.45,

  // Gravity - pulls nodes toward center
  gravity: 0.25,

  // Gravity range - affects gravity falloff
  gravityRange: 3.8,

  // === ITERATION SETTINGS ===
  numIter: 2500,

  // === TILING (for disconnected components) ===
  tile: true,
  tilingPaddingVertical: 10,
  tilingPaddingHorizontal: 10,

  // === NESTING (for compound nodes) ===
  nestingFactor: 0.1,
};

/**
 * Fallback cose options if fcose fails
 */
const COSE_FALLBACK = {
  name: 'cose',
  animate: true,
  animationDuration: 500,
  fit: true,
  padding: 50,
  nodeRepulsion: 4500,
  idealEdgeLength: 100,
  edgeElasticity: 0.45,
  gravity: 0.25,
  numIter: 1000,
  randomize: true,
};

/**
 * Run layout on the graph
 */
function runLayout(cy, options = {}) {
  // Try to register fcose
  const fcoseAvailable = registerFcose();

  let layoutOptions;
  let layoutName;

  if (fcoseAvailable) {
    layoutOptions = { ...LAYOUT_OPTIONS, ...options };
    layoutName = 'fcose';
  } else {
    layoutOptions = { ...COSE_FALLBACK, ...options };
    layoutName = 'cose (fallback)';
  }

  const nodeCount = cy.nodes().length;

  // Show loading state for large graphs
  if (nodeCount > 200) {
    showLoading('Running layout...');
  }

  console.log(`Running ${layoutName} layout on ${nodeCount} nodes...`);
  console.log('Layout params:', layoutOptions);

  const layout = cy.layout(layoutOptions);

  layout.on('layoutstop', () => {
    hideLoading();
    updateLabelVisibility(cy);
    announceToScreenReader(`Layout complete. ${nodeCount} nodes arranged.`);
    console.log('Layout complete');
  });

  layout.run();

  return layout;
}

/**
 * Run layout on a subset of nodes (for expand operations)
 */
function runPartialLayout(cy, nodes, options = {}) {
  const layoutOptions = {
    ...LAYOUT_OPTIONS,
    ...options,
    fit: false,
    randomize: false,
    animate: true,
    animationDuration: 300,
  };

  const layout = nodes.layout(layoutOptions);
  layout.run();

  return layout;
}

/**
 * Update label visibility based on zoom level
 */
function updateLabelVisibility(cy) {
  const zoom = cy.zoom();
  const threshold = 0.8;

  cy.nodes().forEach(node => {
    if (zoom >= threshold) {
      node.style('label', node.data('label'));
    } else {
      const degree = node.degree();
      const velocity = node.data('velocity') || 0;

      if (degree > 5 || velocity > 0.7) {
        node.style('label', node.data('label'));
      } else {
        node.style('label', '');
      }
    }
  });
}

/**
 * Center and fit the graph to the viewport
 */
function fitGraph(cy, padding = 50) {
  cy.animate({
    fit: {
      eles: cy.elements(),
      padding: padding
    },
    duration: 300
  });
}

/**
 * Center on specific elements
 */
function centerOn(cy, elements, zoom = null) {
  const options = {
    center: { eles: elements },
    duration: 300
  };

  if (zoom !== null) {
    options.zoom = zoom;
  }

  cy.animate(options);
}

/**
 * Store current node positions (for V2 preset layout)
 */
function getNodePositions(cy) {
  const positions = {};

  cy.nodes().forEach(node => {
    const pos = node.position();
    positions[node.id()] = {
      x: pos.x,
      y: pos.y
    };
  });

  return positions;
}

/**
 * Apply stored positions (for V2 preset layout)
 */
function applyNodePositions(cy, positions) {
  cy.nodes().forEach(node => {
    const pos = positions[node.id()];
    if (pos) {
      node.position(pos);
    }
  });
}

/**
 * Export positions to JSON format (for server storage)
 */
function exportPositions(cy, viewName) {
  return {
    view: viewName,
    exportedAt: new Date().toISOString(),
    positions: getNodePositions(cy)
  };
}

/**
 * Debug helper - call from browser console: debugLayout()
 */
window.debugLayout = function() {
  console.log('=== LAYOUT DEBUG INFO ===');
  console.log('fcose available:', typeof cytoscapeFcose !== 'undefined');
  console.log('cytoscape available:', typeof cytoscape !== 'undefined');

  if (typeof cy !== 'undefined') {
    console.log('Node count:', cy.nodes().length);
    console.log('Edge count:', cy.edges().length);
    console.log('Current zoom:', cy.zoom().toFixed(2));
  } else {
    console.log('Graph not initialized yet');
  }

  console.log('LAYOUT_OPTIONS:', LAYOUT_OPTIONS);
};

/**
 * Quick param adjuster - call from console to test values
 * Example: adjustLayout({ nodeSeparation: 100, gravity: 0.1 })
 */
window.adjustLayout = function(params) {
  if (typeof cy === 'undefined') {
    console.error('Graph not initialized');
    return;
  }

  console.log('Re-running layout with params:', params);
  runLayout(cy, params);
};
