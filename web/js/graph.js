/**
 * Graph Data Management
 *
 * Loading, processing, and managing graph data.
 * See docs/ux/README.md for data format specification.
 */

// Scale thresholds for client behavior
const SCALE_THRESHOLDS = {
  OPTIMAL: 100,
  ACCEPTABLE: 500,
  WARNING: 2000,
  DANGER: 5000
};

/**
 * Load graph data from JSON file
 */
async function loadGraphData(url) {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`HTTP ${response.status} loading ${url}`);
  }

  const data = await response.json();

  // Validate required structure
  if (!data.elements) {
    throw new Error('Invalid graph format: missing elements');
  }

  // Process meta information if present
  if (data.meta) {
    handleGraphMeta(data.meta);
  }

  return data;
}

/**
 * Handle meta information for scale decisions and date range display.
 * Stores dateRange in AppState so filters can use it.
 */
function handleGraphMeta(meta) {
  const { nodeCount, view, dateRange } = meta;

  // Store date range so filter panel and other UI can reference it
  if (dateRange) {
    AppState.dateRange = dateRange;
  }

  // Update date range display in toolbar if present
  const dateInfo = document.getElementById('date-range-info');
  if (dateInfo && dateRange && dateRange.start) {
    dateInfo.textContent = `${formatDate(dateRange.start)} – ${formatDate(dateRange.end)}`;
    dateInfo.title = `Articles published ${dateRange.start} to ${dateRange.end}`;
  }

  if (nodeCount > SCALE_THRESHOLDS.DANGER) {
    showError(
      `Graph too large for client rendering (${nodeCount} nodes). ` +
      `Please apply filters on the server.`
    );
    return false;
  }

  if (nodeCount > SCALE_THRESHOLDS.WARNING) {
    showWarning(
      `Large graph (${nodeCount} nodes). Showing trending subset. `,
      'Load all nodes anyway',
      () => {
        // Callback to load full graph
        console.log('User requested full graph load');
      }
    );
  } else if (nodeCount > SCALE_THRESHOLDS.ACCEPTABLE) {
    showInfo(`${nodeCount} nodes loaded. Use filters to focus exploration.`);
  }

  return true;
}

/**
 * Initialize Cytoscape with data
 */
function initializeGraph(container, data, styles) {
  const cy = cytoscape({
    container: container,

    elements: data.elements,

    style: styles,

    // Interaction options
    minZoom: 0.1,
    maxZoom: 4,
    wheelSensitivity: 0.3,

    // Selection
    boxSelectionEnabled: true,
    selectionType: 'single',

    // Performance
    textureOnViewport: true,
    hideEdgesOnViewport: false,
    hideLabelsOnViewport: false,
  });

  // Store reference globally for debugging and panel access
  window.cy = cy;

  return cy;
}

/**
 * Add elements to existing graph
 */
function addElements(cy, elements) {
  if (elements.nodes) {
    cy.add(elements.nodes.map(n => ({ group: 'nodes', data: n.data })));
  }
  if (elements.edges) {
    cy.add(elements.edges.map(e => ({ group: 'edges', data: e.data })));
  }
}

/**
 * Remove elements from graph
 */
function removeElements(cy, elementIds) {
  elementIds.forEach(id => {
    const ele = cy.getElementById(id);
    if (ele.length > 0) {
      ele.remove();
    }
  });
}

/**
 * Get graph statistics
 */
function getGraphStats(cy) {
  const nodes = cy.nodes();
  const edges = cy.edges();

  // Count by type
  const typeCount = {};
  nodes.forEach(node => {
    const type = node.data('type');
    typeCount[type] = (typeCount[type] || 0) + 1;
  });

  // Count by kind
  const kindCount = {};
  edges.forEach(edge => {
    const kind = edge.data('kind');
    kindCount[kind] = (kindCount[kind] || 0) + 1;
  });

  return {
    nodeCount: nodes.length,
    edgeCount: edges.length,
    typeCount,
    kindCount,
    averageDegree: edges.length * 2 / Math.max(nodes.length, 1)
  };
}

/**
 * Get available entity types from current graph
 */
function getEntityTypes(cy) {
  const types = new Set();
  cy.nodes().forEach(node => {
    types.add(node.data('type'));
  });
  return Array.from(types).sort();
}

/**
 * Get date range from graph data
 */
function getDateRange(cy) {
  let minDate = null;
  let maxDate = null;

  cy.nodes().forEach(node => {
    const firstSeen = node.data('firstSeen');
    const lastSeen = node.data('lastSeen');

    if (firstSeen) {
      const date = new Date(firstSeen);
      if (!minDate || date < minDate) minDate = date;
    }
    if (lastSeen) {
      const date = new Date(lastSeen);
      if (!maxDate || date > maxDate) maxDate = date;
    }
  });

  return { minDate, maxDate };
}

/**
 * Export current graph state
 */
function exportGraphState(cy) {
  return {
    elements: cy.json().elements,
    zoom: cy.zoom(),
    pan: cy.pan(),
    positions: getNodePositions(cy)
  };
}
