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
 * Check if fcose layout is available.
 * The CDN script auto-registers with cytoscape when both are loaded,
 * so we just need to test if the layout works.
 */
function isFcoseAvailable() {
  try {
    const testCy = cytoscape({ headless: true, elements: [] });
    testCy.layout({ name: 'fcose' });
    testCy.destroy();
    console.log('fcose layout is available');
    return true;
  } catch (e) {
    console.warn('fcose layout not available - will fall back to cose');
    return false;
  }
}

/**
 * Base layout options for fcose (small graphs, < 50 nodes)
 *
 * These are tuned for ~15 node graphs. For larger graphs,
 * getScaledLayoutOptions() returns adjusted parameters.
 */
const LAYOUT_OPTIONS_BASE = {
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
  nodeSeparation: 75,

  // === FORCE-DIRECTED PHASE PARAMETERS ===
  nodeRepulsion: 4500,
  idealEdgeLength: 50,
  edgeElasticity: 0.45,
  gravity: 0.25,
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
 * Compute scaled fcose layout options based on graph size and density.
 *
 * Problem: fixed params tuned for 15 nodes produce hairballs at 100+ nodes,
 * especially in dense views like claims (2-3 edges per node).
 *
 * Solution: scale separation, repulsion, edge length up and gravity down
 * as node count and edge density increase.
 *
 * @param {number} nodeCount - Number of nodes in the graph
 * @param {number} edgeCount - Number of edges in the graph
 * @returns {object} fcose layout options with scaled parameters
 */
function getScaledLayoutOptions(nodeCount, edgeCount) {
  const opts = { ...LAYOUT_OPTIONS_BASE };
  const density = edgeCount / Math.max(nodeCount, 1);

  // Small graphs (< 50 nodes): use base params
  if (nodeCount < 50) {
    return opts;
  }

  // Scale factor: logarithmic growth so we don't over-separate huge graphs
  // At 150 nodes → ~1.5x, at 500 → ~2.1x, at 2000 → ~2.8x
  const scaleFactor = 1 + Math.log10(nodeCount / 50) * 1.05;

  // Density factor: denser graphs need more spacing
  // At density 1 → 1.0x, at density 2.5 → ~1.3x, at density 4 → ~1.5x
  const densityFactor = 1 + Math.max(0, density - 1) * 0.15;

  const combined = scaleFactor * densityFactor;

  // Scale key parameters
  opts.nodeSeparation = Math.round(75 * combined);
  opts.nodeRepulsion = Math.round(4500 * combined * combined);
  opts.idealEdgeLength = Math.round(50 * combined);
  opts.gravity = Math.max(0.02, 0.25 / combined);
  opts.gravityRange = Math.min(10, 3.8 * combined);

  // For large graphs, increase iterations for better convergence
  if (nodeCount > 500) {
    opts.numIter = 3500;
  }
  if (nodeCount > 1000) {
    opts.numIter = 4000;
    opts.quality = 'default'; // keep default; 'proof' too slow at this scale
  }

  // Increase tiling padding for graphs with many disconnected components
  if (nodeCount > 200) {
    opts.tilingPaddingVertical = 20;
    opts.tilingPaddingHorizontal = 20;
  }

  console.log(`Layout auto-scale: ${nodeCount} nodes, ${edgeCount} edges, ` +
    `density=${density.toFixed(2)}, scale=${scaleFactor.toFixed(2)}, ` +
    `densityFactor=${densityFactor.toFixed(2)}, combined=${combined.toFixed(2)}`);
  console.log(`Scaled params: nodeSep=${opts.nodeSeparation}, ` +
    `repulsion=${opts.nodeRepulsion}, edgeLen=${opts.idealEdgeLength}, ` +
    `gravity=${opts.gravity.toFixed(3)}`);

  return opts;
}

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
  // Check if fcose is available
  const fcoseAvailable = isFcoseAvailable();

  let layoutOptions;
  let layoutName;

  const nodeCount = cy.nodes().length;
  const edgeCount = cy.edges().length;

  if (fcoseAvailable) {
    layoutOptions = { ...getScaledLayoutOptions(nodeCount, edgeCount), ...options };
    layoutName = 'fcose';
  } else {
    layoutOptions = { ...COSE_FALLBACK, ...options };
    layoutName = 'cose (fallback)';
  }

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
  const nodeCount = cy.nodes().length;
  const edgeCount = cy.edges().length;
  const layoutOptions = {
    ...getScaledLayoutOptions(nodeCount, edgeCount),
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
  console.log('fcose available:', isFcoseAvailable());
  console.log('cytoscape available:', typeof cytoscape !== 'undefined');

  if (typeof cy !== 'undefined') {
    console.log('Node count:', cy.nodes().length);
    console.log('Edge count:', cy.edges().length);
    console.log('Current zoom:', cy.zoom().toFixed(2));
  } else {
    console.log('Graph not initialized yet');
  }

  console.log('LAYOUT_OPTIONS_BASE:', LAYOUT_OPTIONS_BASE);
  if (typeof cy !== 'undefined') {
    console.log('Scaled options:', getScaledLayoutOptions(cy.nodes().length, cy.edges().length));
  }
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
