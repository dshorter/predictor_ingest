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

  // Parse as text first, then JSON — Safari throws a cryptic
  // "The string did not match the expected pattern" when .json()
  // is called on a non-JSON body (e.g., HTML error pages).
  const text = await response.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch (e) {
    throw new Error(`Invalid JSON from ${url}: ${text.substring(0, 100)}`);
  }

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

  // Expose meta globally for tour and other cross-module checks
  window._graphMeta = meta;

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

  // Handle empty graph
  const emptyState = document.getElementById('empty-state');
  if (nodeCount === 0) {
    if (emptyState) {
      const note = meta.note || '';
      const isPlaceholder = note.toLowerCase().includes('placeholder');
      const msg = document.getElementById('empty-state-message');
      if (msg) {
        msg.textContent = isPlaceholder
          ? 'No data yet. Run the ingestion pipeline to populate this graph.'
          : 'This view has no data. Try switching to a different view or data source.';
      }
      emptyState.classList.remove('hidden');
    }
    return true;
  }

  // Hide empty state if previously shown
  if (emptyState) {
    emptyState.classList.add('hidden');
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
 * Strip edges whose source or target node is missing.
 * Prevents Cytoscape.js from throwing on orphan edges.
 */
function stripOrphanEdges(elements) {
  if (!elements.nodes || !elements.edges) return elements;
  const nodeIds = new Set(elements.nodes.map(n => n.data.id));
  const validEdges = elements.edges.filter(e =>
    nodeIds.has(e.data.source) && nodeIds.has(e.data.target)
  );
  const dropped = elements.edges.length - validEdges.length;
  if (dropped > 0) {
    console.warn(`Stripped ${dropped} orphan edge(s) referencing missing nodes`);
  }
  return { nodes: elements.nodes, edges: validEdges };
}

/**
 * Initialize Cytoscape with data
 */
function initializeGraph(container, data, styles) {
  const cleanElements = stripOrphanEdges(data.elements);
  const cy = cytoscape({
    container: container,

    elements: cleanElements,

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
  const clean = stripOrphanEdges(elements);
  if (clean.nodes) {
    cy.add(clean.nodes.map(n => ({ group: 'nodes', data: n.data })));
  }
  if (clean.edges) {
    cy.add(clean.edges.map(e => ({ group: 'edges', data: e.data })));
  }
}

const TRANSPARENT_PIXEL = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';

/**
 * Stamp a faviconUrl onto every Document node for use as a Cytoscape
 * background-image. Uses Google's favicon service keyed on the node's
 * source domain; nodes without a source get a transparent 1×1 pixel.
 * Call after initializeGraph() / addElements().
 */
function stampFavicons(cy) {
  cy.nodes('[type = "Document"]').forEach(node => {
    const source = node.data('source');
    node.data('faviconUrl', source
      ? `https://www.google.com/s2/favicons?domain=${encodeURIComponent(source)}&sz=32`
      : TRANSPARENT_PIXEL);
  });
}

/**
 * Apply .new CSS class to nodes first seen within the last 7 days.
 * Call after addElements() or initializeGraph() to activate the green
 * double-border style defined in styles.js.
 */
function applyNewClass(cy) {
  cy.nodes().forEach(node => {
    if (isNewNode(node.data('firstSeen'))) {
      node.addClass('new');
    }
  });
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
