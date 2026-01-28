/**
 * Layout Management
 *
 * Force-directed layout using built-in cose algorithm.
 *
 * Decision: Using cose instead of fcose for V1.
 * - cose "worked the first time" with excellent visual results
 * - Simpler algorithm, fewer parameters to tune
 * - No external dependencies (built into Cytoscape)
 * - fcose can be revisited in V2 for larger graphs (500+ nodes)
 *
 * See docs/ux/layout-temporal.md for specification.
 * See docs/fix-details/FCOSE_LAYOUT_ANALYSIS.md for fcose research.
 */

/**
 * Default layout options for cose (built-in force-directed)
 *
 * IMPORTANT: This exact configuration produced excellent results
 * in the original fallback. Do not add extra parameters without testing.
 */
const LAYOUT_OPTIONS = {
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
  const layoutOptions = { ...LAYOUT_OPTIONS, ...options };

  // Show loading state for large graphs
  const nodeCount = cy.nodes().length;
  if (nodeCount > 200) {
    showLoading('Running layout...');
  }

  console.log(`Running cose layout on ${nodeCount} nodes...`);

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
    fit: false, // Don't fit the entire graph
    randomize: false, // Keep existing positions as starting point
    animate: true,
    animationDuration: 300,
  };

  // Only layout the specified nodes
  const layout = nodes.layout(layoutOptions);
  layout.run();

  return layout;
}

/**
 * Update label visibility based on zoom level
 * Labels shown when zoomed in, hidden when zoomed out
 */
function updateLabelVisibility(cy) {
  const zoom = cy.zoom();
  const threshold = 0.8;

  cy.nodes().forEach(node => {
    if (zoom >= threshold) {
      node.style('label', node.data('label'));
    } else {
      // Show labels only for high-degree or high-velocity nodes when zoomed out
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
 * Debug helper - can be called from browser console
 */
window.debugLayout = function() {
  console.log('=== LAYOUT DEBUG INFO ===');
  console.log('Layout algorithm: cose (built-in)');
  console.log('cytoscape available:', typeof cytoscape !== 'undefined');

  if (typeof cy !== 'undefined') {
    console.log('Node count:', cy.nodes().length);
    console.log('Edge count:', cy.edges().length);
    console.log('Current zoom:', cy.zoom().toFixed(2));
  } else {
    console.log('Graph not initialized yet');
  }

  console.log('Layout options:', LAYOUT_OPTIONS);
};
