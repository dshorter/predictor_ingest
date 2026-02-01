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
 * Reference calibration from trending view (medium tier: 37 nodes, 31 edges).
 * These base params produce a good layout at this scale. We compute per-node
 * and per-edge ratios, then apply them to any graph size.
 *
 * Key insight: even with fit:true, the RATIO between repulsion and gravity
 * determines cluster tightness. Higher repulsion/gravity ratio = more even
 * spacing. The force simulation topology is preserved after fit-scaling.
 */
const REFERENCE = {
  nodes: 37,
  edges: 31,
  density: 31 / 37,  // ~0.84 edges per node
  // Base params that look good at this scale:
  nodeSeparation: 75,
  nodeRepulsion: 4500,
  idealEdgeLength: 50,
  gravity: 0.25,
  gravityRange: 3.8,
};

/**
 * Compute scaled fcose layout options using ratio-based scaling.
 *
 * Uses the trending view (37n/31e) as a golden reference where base params
 * produce good results. Computes ratios from that reference and applies
 * them to the current graph size and density.
 *
 * Linear scaling (not log) because fit:true normalizes absolute positions —
 * what matters is the force RATIOS, and those need proportional scaling.
 *
 * @param {number} nodeCount - Number of nodes in the graph
 * @param {number} edgeCount - Number of edges in the graph
 * @returns {object} fcose layout options with scaled parameters
 */
function getScaledLayoutOptions(nodeCount, edgeCount) {
  const opts = { ...LAYOUT_OPTIONS_BASE };

  // Small graphs (≤ reference size): use base params as-is
  if (nodeCount <= REFERENCE.nodes) {
    console.log(`Layout: ${nodeCount}n ≤ ref(${REFERENCE.nodes}), using base params`);
    return opts;
  }

  const nodeRatio = nodeCount / REFERENCE.nodes;
  const density = edgeCount / Math.max(nodeCount, 1);
  const densityRatio = density / REFERENCE.density;

  // --- Ratio-based scaling from reference ---

  // nodeSeparation: sqrt(nodeRatio) — spectral phase spacing
  opts.nodeSeparation = Math.round(
    REFERENCE.nodeSeparation * Math.sqrt(nodeRatio)
  );

  // nodeRepulsion: linear with nodeRatio, boosted by density
  // This is THE key param — each node needs proportional repulsion force,
  // and denser graphs need extra push to avoid overlap
  opts.nodeRepulsion = Math.round(
    REFERENCE.nodeRepulsion * nodeRatio * Math.max(1, densityRatio)
  );

  // idealEdgeLength: sqrt(nodeRatio) * density boost
  // Longer edges in bigger/denser graphs reduce visual overlap
  opts.idealEdgeLength = Math.round(
    REFERENCE.idealEdgeLength * Math.sqrt(nodeRatio) * Math.max(1, Math.sqrt(densityRatio))
  );

  // gravity: INVERSE of nodeRatio — this is the critical ratio
  // Weaker gravity = less central pull = more even distribution
  // With fit:true, the repulsion/gravity RATIO drives visual spread
  opts.gravity = Math.max(0.005, REFERENCE.gravity / nodeRatio);

  // gravityRange: increase so falloff covers the larger layout
  opts.gravityRange = Math.min(15, REFERENCE.gravityRange * Math.sqrt(nodeRatio));

  // Iteration scaling — bigger graphs need more convergence steps
  if (nodeCount > 100) opts.numIter = 3000;
  if (nodeCount > 500) opts.numIter = 3500;
  if (nodeCount > 1000) opts.numIter = 4000;

  // Tiling padding for disconnected components
  if (nodeCount > 50) {
    opts.tilingPaddingVertical = Math.round(10 * Math.sqrt(nodeRatio));
    opts.tilingPaddingHorizontal = Math.round(10 * Math.sqrt(nodeRatio));
  }

  console.log(
    `Layout ratio-scale: ${nodeCount}n/${edgeCount}e | ` +
    `nodeRatio=${nodeRatio.toFixed(1)}x, density=${density.toFixed(2)}, ` +
    `densityRatio=${densityRatio.toFixed(2)}x`
  );
  console.log(
    `Scaled → nodeSep=${opts.nodeSeparation}, repulsion=${opts.nodeRepulsion}, ` +
    `edgeLen=${opts.idealEdgeLength}, gravity=${opts.gravity.toFixed(4)}, ` +
    `gravRange=${opts.gravityRange.toFixed(1)}, iters=${opts.numIter}`
  );

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

  // For larger graphs, disable fit during layout computation.
  // fit:true constrains the simulation to the viewport, crushing nodes together.
  // Instead: let fcose decide natural spacing, then zoom out to show everything.
  const usePostLayoutFit = nodeCount > REFERENCE.nodes;
  if (usePostLayoutFit) {
    layoutOptions.fit = false;
    console.log(`Layout: ${nodeCount} nodes > ref(${REFERENCE.nodes}), using post-layout fit`);
  }

  // Show loading state for large graphs
  if (nodeCount > 200) {
    showLoading('Running layout...');
  }

  console.log(`Running ${layoutName} layout on ${nodeCount} nodes...`);
  console.log('Layout params:', layoutOptions);

  const layout = cy.layout(layoutOptions);

  layout.on('layoutstop', () => {
    if (usePostLayoutFit) {
      // Zoom out to show the full extent — nodes keep their natural spacing
      cy.fit(cy.elements(), 30);
      console.log(`Post-layout fit: zoom=${cy.zoom().toFixed(3)}`);
    }
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
