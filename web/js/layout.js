/**
 * Layout Management
 *
 * Force-directed layout using fcose algorithm.
 * See docs/ux/layout-temporal.md for specification.
 */

// Register fcose extension with Cytoscape
// The unpkg version should auto-register, but we'll ensure it's registered
if (typeof cytoscape !== 'undefined') {
  // Try different possible global variable names
  if (typeof cytoscapeFcose !== 'undefined') {
    cytoscape.use(cytoscapeFcose);
  } else if (typeof fcose !== 'undefined') {
    cytoscape.use(fcose);
  }
  // If neither exists, the CDN version should have auto-registered
}

/**
 * Default layout options for fcose
 */
const LAYOUT_OPTIONS = {
  name: 'fcose',

  // Animation
  animate: true,
  animationDuration: 500,
  animationEasing: 'ease-out',

  // Fit
  fit: true,
  padding: 50,

  // Node repulsion
  nodeRepulsion: 4500,

  // Ideal edge length
  idealEdgeLength: 100,

  // Edge elasticity
  edgeElasticity: 0.45,

  // Nesting factor for compound nodes
  nestingFactor: 0.1,

  // Gravity
  gravity: 0.25,

  // Number of iterations
  numIter: 2500,

  // Tile disconnected components
  tile: true,
  tilingPaddingVertical: 40,
  tilingPaddingHorizontal: 40,

  // Randomize initial positions
  randomize: true,

  // Quality vs speed
  quality: 'default', // 'draft', 'default', or 'proof'
};

/**
 * Run layout on the graph
 */
function runLayout(cy, options = {}) {
  let layoutOptions = { ...LAYOUT_OPTIONS, ...options };

  // Fallback to 'cose' if fcose isn't available
  try {
    // Test if fcose is available
    cy.layout({ name: 'fcose' });
  } catch (e) {
    console.warn('fcose layout not available, falling back to cose');
    // Use built-in cose layout instead
    layoutOptions = {
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
  }

  // Show loading state for large graphs
  const nodeCount = cy.nodes().length;
  if (nodeCount > 200) {
    showLoading('Running layout...');
  }

  const layout = cy.layout(layoutOptions);

  layout.on('layoutstop', () => {
    hideLoading();
    updateLabelVisibility(cy);
    announceToScreenReader(`Layout complete. ${nodeCount} nodes arranged.`);
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
    randomize: false,
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
