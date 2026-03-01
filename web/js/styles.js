/**
 * Cytoscape Visual Styles
 *
 * Defines node and edge styling for the graph visualization.
 * See docs/ux/visual-encoding.md for specification.
 */

/**
 * Darken a hex color by a fraction (0–1).
 * Example: darkenColor('#4A90D9', 0.2) → 20% darker.
 * Returns an rgb() string Cytoscape accepts.
 */
function darkenColor(hex, fraction) {
  const h = hex.replace('#', '');
  const r = parseInt(h.length === 3 ? h[0] + h[0] : h.slice(0, 2), 16);
  const g = parseInt(h.length === 3 ? h[1] + h[1] : h.slice(2, 4), 16);
  const b = parseInt(h.length === 3 ? h[2] + h[2] : h.slice(4, 6), 16);
  return `rgb(${Math.round(r*(1-fraction))},${Math.round(g*(1-fraction))},${Math.round(b*(1-fraction))})`;
}

/**
 * Read a CSS custom property value from :root.
 * Returns the trimmed string value or the fallback if not found.
 */
function getCSSVar(name, fallback) {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name).trim();
  return value || fallback;
}

// Node type colors (from design tokens)
function getNodeTypeColors() {
  return {
    'Org': getCSSVar('--color-org', '#4A90D9'),
    'Person': getCSSVar('--color-person', '#50B4A8'),
    'Program': getCSSVar('--color-program', '#6366F1'),
    'Tool': getCSSVar('--color-tool', '#8B5CF6'),
    'Model': getCSSVar('--color-model', '#7C3AED'),
    'Dataset': getCSSVar('--color-dataset', '#F59E0B'),
    'Benchmark': getCSSVar('--color-benchmark', '#D97706'),
    'Paper': getCSSVar('--color-paper', '#10B981'),
    'Repo': getCSSVar('--color-repo', '#059669'),
    'Tech': getCSSVar('--color-tech', '#EAB308'),
    'Topic': getCSSVar('--color-topic', '#64748B'),
    'Document': getCSSVar('--color-document', '#9CA3AF'),
    'Event': getCSSVar('--color-event', '#F43F5E'),
    'Location': getCSSVar('--color-location', '#0EA5E9'),
    'Other': getCSSVar('--color-other', '#A1A1AA')
  };
}

// Edge colors
function getEdgeColors() {
  return {
    default: getCSSVar('--edge-default', '#6B7280'),
    new: getCSSVar('--edge-new', '#22C55E'),
    hover: getCSSVar('--edge-hover', '#3B82F6'),
    selected: getCSSVar('--edge-selected', '#2563EB'),
    dimmed: getCSSVar('--edge-dimmed', '#D1D5DB')
  };
}

// Node sizing constants
const MIN_NODE_SIZE = 20;
const MAX_NODE_SIZE = 80;
const BASE_SIZE = 30;

/**
 * Calculate node size based on velocity, novelty, and degree
 */
function calculateNodeSize(ele) {
  const velocity = ele.data('velocity') || 0;
  const novelty = ele.data('novelty') || 0;
  const degree = ele.data('degree') || ele.degree() || 1;

  // Velocity contributes (0-3 maps to 1x-2.5x)
  const velocityMultiplier = 1 + (Math.min(velocity, 3) * 0.5);

  // Recency boost for new nodes
  const recencyBoost = calculateRecencyBoost(ele.data('firstSeen'));

  // Degree is a strong size driver — hub nodes should be visibly larger
  // degree 1 → 1.0x, degree 3 → 1.55x, degree 6 → 1.90x, degree 10 → 2.15x
  const degreeMultiplier = 1 + (Math.log2(degree) * 0.5);

  let size = BASE_SIZE * velocityMultiplier * recencyBoost * degreeMultiplier;

  return Math.max(MIN_NODE_SIZE, Math.min(MAX_NODE_SIZE, size));
}

/**
 * Calculate recency boost based on firstSeen date
 */
function calculateRecencyBoost(firstSeenDate) {
  const days = daysBetween(firstSeenDate);

  if (days <= 7) return 1.5;    // Brand new: 50% boost
  if (days <= 14) return 1.3;   // Recent: 30% boost
  if (days <= 30) return 1.15;  // Somewhat recent: 15% boost
  return 1.0;                    // Established: no boost
}

/**
 * Calculate opacity based on lastSeen date
 */
function calculateRecencyOpacity(lastSeenDate) {
  const days = daysBetween(lastSeenDate);

  if (days <= 7) return 1.0;    // Active: full opacity
  if (days <= 14) return 0.9;   // Recent
  if (days <= 30) return 0.8;   // Fading
  if (days <= 60) return 0.7;   // Stale
  if (days <= 90) return 0.6;   // Old
  return 0.5;                    // Oldest nodes still clearly visible
}

/**
 * Calculate edge width based on confidence
 */
function calculateEdgeWidth(confidence) {
  const MIN_WIDTH = 0.5;
  const MAX_WIDTH = 4;
  const conf = Math.max(0, Math.min(1, confidence || 0.5));
  return MIN_WIDTH + (conf * (MAX_WIDTH - MIN_WIDTH));
}

/**
 * Check if edge is new (< 7 days old)
 */
function isNewEdge(ele) {
  const firstSeen = ele.data('firstSeen');
  if (!firstSeen) return false;
  return daysBetween(firstSeen) <= 7;
}

/**
 * Get Cytoscape stylesheet
 */
function getCytoscapeStyles() {
  const nodeTypeColors = getNodeTypeColors();
  const edgeColors = getEdgeColors();

  return [
    // Base node style
    {
      selector: 'node',
      style: {
        'background-color': function(ele) {
          return nodeTypeColors[ele.data('type')] || nodeTypeColors['Other'];
        },
        'width': function(ele) { return calculateNodeSize(ele); },
        'height': function(ele) { return calculateNodeSize(ele); },
        'opacity': function(ele) {
          // Fall back through lastSeen → firstSeen → publishedAt → full opacity
          const dateField = ele.data('lastSeen') || ele.data('firstSeen') || ele.data('publishedAt');
          return calculateRecencyOpacity(dateField);
        },
        'label': function(ele) {
          return truncateLabel(ele.data('label'), 20);
        },
        'font-size': function(ele) {
          const nodeSize = calculateNodeSize(ele);
          return Math.max(10, Math.min(16, nodeSize * 0.4));
        },
        'text-valign': 'bottom',
        'text-halign': 'center',
        'text-margin-y': 5,
        'color': getCSSVar('--cy-text-color', '#1F2937'),
        'text-outline-color': getCSSVar('--cy-text-outline', '#FFFFFF'),
        'text-outline-width': 2,
        'text-outline-opacity': 1,
        // Depth cues: slightly thicker border in the node's own type color (20% darker)
        'border-width': 2.5,
        'border-color': function(ele) {
          const fill = nodeTypeColors[ele.data('type')] || nodeTypeColors['Other'];
          return darkenColor(fill, 0.2);
        },
        'border-opacity': 1,
        // Subtle drop shadow via underlay
        'underlay-color': '#000000',
        'underlay-opacity': 0.06,
        'underlay-padding': 4
      }
    },

    // Node hover state (applied via events, not CSS pseudo-selector)
    {
      selector: 'node.hover',
      style: {
        'border-width': 3,
        'border-color': getCSSVar('--cy-node-border-hover', '#3B82F6'),
        'border-opacity': 1,
        'label': function(ele) { return ele.data('label'); },
        'z-index': 9999,
        'font-size': 14,
        'font-weight': 'bold'
      }
    },

    // Node selected state
    {
      selector: 'node:selected',
      style: {
        'border-width': 4,
        'border-color': getCSSVar('--cy-node-border-selected', '#2563EB'),
        'border-opacity': 1,
        'overlay-color': getCSSVar('--cy-node-overlay-selected', '#3B82F6'),
        'overlay-opacity': 0.15,
        'overlay-padding': 8,
        'label': function(ele) { return ele.data('label'); },
        'font-weight': 'bold'
      }
    },

    // Highlighted nodes (search results, neighbors)
    {
      selector: 'node.highlighted',
      style: {
        'border-width': 3,
        'border-color': getCSSVar('--cy-node-border-highlighted', '#F59E0B'),
        'border-opacity': 1
      }
    },

    // Dimmed nodes (during search/filter)
    {
      selector: 'node.dimmed',
      style: {
        'opacity': 0.25
      }
    },

    // Neighborhood-dimmed nodes (click-to-highlight)
    {
      selector: 'node.neighborhood-dimmed',
      style: {
        'opacity': 0.15,
        'label': ''
      }
    },

    // New nodes (added in last 7 days)
    {
      selector: 'node.new',
      style: {
        'border-width': 3,
        'border-color': getCSSVar('--cy-node-border-new', '#22C55E'),
        'border-style': 'double'
      }
    },

    // High-velocity halo: nodes with velocity > 2 get a colored glow (type color, 15% opacity)
    {
      selector: 'node[velocity > 2]',
      style: {
        'underlay-color': function(ele) {
          return nodeTypeColors[ele.data('type')] || nodeTypeColors['Other'];
        },
        'underlay-opacity': 0.15,
        'underlay-padding': 8
      }
    },

    // Hidden label
    {
      selector: 'node.label-hidden',
      style: {
        'label': ''
      }
    },

    // Base edge style
    {
      selector: 'edge',
      style: {
        'width': function(ele) {
          return calculateEdgeWidth(ele.data('confidence'));
        },
        'line-color': function(ele) {
          return isNewEdge(ele) ? edgeColors.new : edgeColors.default;
        },
        'target-arrow-color': function(ele) {
          return isNewEdge(ele) ? edgeColors.new : edgeColors.default;
        },
        'curve-style': 'bezier',
        'target-arrow-shape': 'triangle',
        'target-arrow-fill': 'filled',
        // Low-confidence edges get a smaller arrowhead (less visual weight)
        'arrow-scale': function(ele) {
          return (ele.data('confidence') || 0.5) < 0.5 ? 0.6 : 0.8;
        }
      }
    },

    // Asserted edges (solid)
    {
      selector: 'edge[kind = "asserted"]',
      style: {
        'line-style': 'solid'
      }
    },

    // Inferred edges (dashed)
    {
      selector: 'edge[kind = "inferred"]',
      style: {
        'line-style': 'dashed',
        'line-dash-pattern': [6, 3]
      }
    },

    // Hypothesis edges (dotted)
    {
      selector: 'edge[kind = "hypothesis"]',
      style: {
        'line-style': 'dotted',
        'line-dash-pattern': [2, 4]
      }
    },

    // Edge hover state (applied via events, not CSS pseudo-selector)
    {
      selector: 'edge.hover',
      style: {
        'line-color': edgeColors.hover,
        'target-arrow-color': edgeColors.hover,
        'z-index': 999,
        // Show relation type label on hover
        'label': function(ele) { return ele.data('rel') || ''; },
        'font-size': 10,
        'color': getCSSVar('--cy-text-color', '#1F2937'),
        'text-outline-color': getCSSVar('--cy-text-outline', '#FFFFFF'),
        'text-outline-width': 2,
        'text-background-color': getCSSVar('--color-bg-primary', '#FFFFFF'),
        'text-background-opacity': 0.85,
        'text-background-padding': 3,
        'text-rotation': 'autorotate'
      }
    },

    // Edge selected state
    {
      selector: 'edge:selected',
      style: {
        'line-color': edgeColors.selected,
        'target-arrow-color': edgeColors.selected,
        'width': function(ele) {
          return calculateEdgeWidth(ele.data('confidence')) + 1;
        }
      }
    },

    // Dimmed edges
    {
      selector: 'edge.dimmed',
      style: {
        'line-color': edgeColors.dimmed,
        'target-arrow-color': edgeColors.dimmed,
        'opacity': 0.3
      }
    },

    // Neighborhood-dimmed edges (click-to-highlight)
    {
      selector: 'edge.neighborhood-dimmed',
      style: {
        'line-color': edgeColors.dimmed,
        'target-arrow-color': edgeColors.dimmed,
        'opacity': 0.1
      }
    }
  ];
}
