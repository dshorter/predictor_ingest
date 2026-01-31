# Visual Encoding

Node sizing, colors, edge styles, and label visibility rules.

---

## Node Visual Encoding

### Node Data Structure

Each node in the Cytoscape export must include these data fields:

```json
{
  "data": {
    "id": "org:openai",
    "label": "OpenAI",
    "type": "Org",
    "aliases": ["OpenAI Inc", "OpenAI LP"],
    "firstSeen": "2025-06-15",
    "lastSeen": "2026-01-24",
    "mentionCount7d": 23,
    "mentionCount30d": 87,
    "velocity": 1.4,
    "novelty": 0.2,
    "degree": 45
  },
  "position": {
    "x": 342.7,
    "y": -156.2
  }
}
```

### Sizing Strategy (Velocity-Weighted with Recency Boost)

Node size should primarily reflect **velocity** (acceleration of mentions) with a boost for **novelty** (new nodes).

**Base Size Calculation:**

```javascript
// Constants
const MIN_NODE_SIZE = 20;   // pixels
const MAX_NODE_SIZE = 80;   // pixels
const BASE_SIZE = 30;       // pixels

function calculateNodeSize(node) {
  const velocity = node.data('velocity') || 0;      // typically 0-3 range
  const novelty = node.data('novelty') || 0;        // 0-1 range
  const degree = node.data('degree') || 1;          // connection count

  // Velocity is primary driver (0-3 maps to 1x-2.5x)
  const velocityMultiplier = 1 + (Math.min(velocity, 3) * 0.5);

  // Recency boost for new nodes
  const recencyBoost = calculateRecencyBoost(node.data('firstSeen'));

  // Degree provides subtle secondary scaling (logarithmic to prevent mega-nodes)
  const degreeMultiplier = 1 + (Math.log10(degree + 1) * 0.15);

  let size = BASE_SIZE * velocityMultiplier * recencyBoost * degreeMultiplier;

  return Math.max(MIN_NODE_SIZE, Math.min(MAX_NODE_SIZE, size));
}

function calculateRecencyBoost(firstSeenDate) {
  const daysSinceFirstSeen = daysBetween(firstSeenDate, today());

  if (daysSinceFirstSeen <= 7) return 1.5;          // Brand new: 50% boost
  if (daysSinceFirstSeen <= 14) return 1.3;         // Recent: 30% boost
  if (daysSinceFirstSeen <= 30) return 1.15;        // Somewhat recent: 15% boost
  return 1.0;                                        // Established: no boost
}
```

### Color Palette (by Entity Type)

Primary palette designed for distinguishability and colorblind accessibility:

| Type | Color Name | Hex Code | RGB | Usage Notes |
|------|------------|----------|-----|-------------|
| Org | Blue | `#4A90D9` | rgb(74, 144, 217) | Companies, agencies, institutions |
| Person | Teal | `#50B4A8` | rgb(80, 180, 168) | Individuals |
| Program | Indigo | `#6366F1` | rgb(99, 102, 241) | Government/corporate programs |
| Tool | Purple | `#8B5CF6` | rgb(139, 92, 246) | Software tools, platforms |
| Model | Violet | `#7C3AED` | rgb(124, 58, 237) | ML/AI models |
| Dataset | Orange | `#F59E0B` | rgb(245, 158, 11) | Training/eval datasets |
| Benchmark | Amber | `#D97706` | rgb(217, 119, 6) | Evaluation benchmarks |
| Paper | Green | `#10B981` | rgb(16, 185, 129) | Research papers |
| Repo | Emerald | `#059669` | rgb(5, 150, 105) | Code repositories |
| Tech | Gold | `#EAB308` | rgb(234, 179, 8) | Technologies, techniques |
| Topic | Slate | `#64748B` | rgb(100, 116, 139) | Abstract topics, themes |
| Document | Gray | `#9CA3AF` | rgb(156, 163, 175) | Source documents (de-emphasized) |
| Event | Rose | `#F43F5E` | rgb(244, 63, 94) | Conferences, launches, incidents |
| Location | Sky | `#0EA5E9` | rgb(14, 165, 233) | Geographic locations |
| Other | Neutral | `#A1A1AA` | rgb(161, 161, 170) | Uncategorized entities |

**Cytoscape.js Style Implementation:**

```javascript
const nodeTypeColors = {
  'Org': '#4A90D9',
  'Person': '#50B4A8',
  'Program': '#6366F1',
  'Tool': '#8B5CF6',
  'Model': '#7C3AED',
  'Dataset': '#F59E0B',
  'Benchmark': '#D97706',
  'Paper': '#10B981',
  'Repo': '#059669',
  'Tech': '#EAB308',
  'Topic': '#64748B',
  'Document': '#9CA3AF',
  'Event': '#F43F5E',
  'Location': '#0EA5E9',
  'Other': '#A1A1AA'
};

// Cytoscape style selector
const nodeStyle = {
  selector: 'node',
  style: {
    'background-color': function(ele) {
      return nodeTypeColors[ele.data('type')] || nodeTypeColors['Other'];
    },
    'width': function(ele) { return calculateNodeSize(ele); },
    'height': function(ele) { return calculateNodeSize(ele); },
    'label': function(ele) { return truncateLabel(ele.data('label'), 20); }
  }
};
```

### Recency Overlay (Saturation/Opacity Based on lastSeen)

Nodes fade as they become stale, creating a visual "heat map" of recent activity:

```javascript
function calculateRecencyOpacity(lastSeenDate) {
  const daysSinceLastSeen = daysBetween(lastSeenDate, today());

  if (daysSinceLastSeen <= 7) return 1.0;           // Active: full opacity
  if (daysSinceLastSeen <= 14) return 0.85;         // Recent
  if (daysSinceLastSeen <= 30) return 0.7;          // Fading
  if (daysSinceLastSeen <= 60) return 0.55;         // Stale
  if (daysSinceLastSeen <= 90) return 0.4;          // Old
  return 0.25;                                       // Ghost node
}

// Alternative: use saturation instead of opacity
function calculateRecencySaturation(lastSeenDate) {
  const daysSinceLastSeen = daysBetween(lastSeenDate, today());

  if (daysSinceLastSeen <= 7) return 100;           // Full saturation
  if (daysSinceLastSeen <= 30) return 70;
  if (daysSinceLastSeen <= 90) return 50;
  return 30;                                         // Desaturated "ghost"
}
```

**Cytoscape Style for Recency:**

```javascript
{
  selector: 'node',
  style: {
    'opacity': function(ele) {
      return calculateRecencyOpacity(ele.data('lastSeen'));
    },
    // OR use background-opacity to preserve border visibility:
    'background-opacity': function(ele) {
      return calculateRecencyOpacity(ele.data('lastSeen'));
    }
  }
}
```

### Node Border (Selection and Hover States)

```javascript
const nodeStates = [
  {
    selector: 'node',
    style: {
      'border-width': 2,
      'border-color': '#E5E7EB',  // Light gray default border
      'border-opacity': 0.5
    }
  },
  {
    selector: 'node:hover',
    style: {
      'border-width': 3,
      'border-color': '#3B82F6',  // Blue highlight
      'border-opacity': 1
    }
  },
  {
    selector: 'node:selected',
    style: {
      'border-width': 4,
      'border-color': '#2563EB',  // Darker blue
      'border-opacity': 1,
      'overlay-color': '#3B82F6',
      'overlay-opacity': 0.15
    }
  },
  {
    selector: 'node.highlighted',  // For search results, neighbors, etc.
    style: {
      'border-width': 3,
      'border-color': '#F59E0B',  // Amber highlight
      'border-opacity': 1
    }
  },
  {
    selector: 'node.dimmed',  // Non-matching nodes during search
    style: {
      'opacity': 0.25
    }
  },
  {
    selector: 'node.neighborhood-dimmed',  // Click-to-highlight: non-neighbor nodes
    style: {
      'opacity': 0.15,
      'label': ''  // Hide labels for dimmed nodes to reduce clutter
    }
  },
  {
    selector: 'node.new',  // Nodes added in last 7 days
    style: {
      'border-width': 3,
      'border-color': '#22C55E',  // Green "new" indicator
      'border-style': 'double'
    }
  }
];
```

---

## Edge Visual Encoding

### Edge Data Structure

Each edge in the Cytoscape export must include these data fields:

```json
{
  "data": {
    "id": "e:org:openai->model:gpt5:LAUNCHED",
    "source": "org:openai",
    "target": "model:gpt5",
    "rel": "LAUNCHED",
    "kind": "asserted",
    "confidence": 0.95,
    "evidenceCount": 3,
    "firstSeen": "2026-01-15",
    "lastSeen": "2026-01-20"
  }
}
```

### Line Style (by Kind)

The `kind` field indicates the epistemic status of the relationship:

| Kind | Line Style | Dash Pattern | Interpretation |
|------|------------|--------------|----------------|
| `asserted` | Solid | none | Directly stated in source documents |
| `inferred` | Dashed | `[6, 3]` | Derived from multiple sources or reasoning |
| `hypothesis` | Dotted | `[2, 4]` | Speculative; needs verification |

```javascript
{
  selector: 'edge[kind = "asserted"]',
  style: {
    'line-style': 'solid'
  }
},
{
  selector: 'edge[kind = "inferred"]',
  style: {
    'line-style': 'dashed',
    'line-dash-pattern': [6, 3]
  }
},
{
  selector: 'edge[kind = "hypothesis"]',
  style: {
    'line-style': 'dotted',
    'line-dash-pattern': [2, 4]
  }
}
```

### Thickness (by Confidence)

Edge thickness scales linearly with confidence score:

```javascript
function calculateEdgeWidth(confidence) {
  const MIN_WIDTH = 0.5;
  const MAX_WIDTH = 4;
  const conf = Math.max(0, Math.min(1, confidence || 0.5));
  return MIN_WIDTH + (conf * (MAX_WIDTH - MIN_WIDTH));
}

// Result mapping:
// confidence 0.0  → 0.5px
// confidence 0.5  → 2.25px
// confidence 1.0  → 4px
```

```javascript
{
  selector: 'edge',
  style: {
    'width': function(ele) {
      return calculateEdgeWidth(ele.data('confidence'));
    }
  }
}
```

### Edge Color

```javascript
const edgeColors = {
  default: '#6B7280',      // Gray
  new: '#22C55E',          // Green for edges < 7 days old
  hover: '#3B82F6',        // Blue on hover
  selected: '#2563EB',     // Darker blue when selected
  dimmed: '#D1D5DB'        // Light gray when dimmed
};

function getEdgeColor(ele, isNew) {
  if (ele.hasClass('dimmed')) return edgeColors.dimmed;
  if (isNew) return edgeColors.new;
  return edgeColors.default;
}

// Check if edge is new (first evidence within 7 days)
function isNewEdge(ele) {
  const firstSeen = ele.data('firstSeen');
  if (!firstSeen) return false;
  return daysBetween(firstSeen, today()) <= 7;
}
```

```javascript
{
  selector: 'edge',
  style: {
    'line-color': function(ele) {
      return isNewEdge(ele) ? edgeColors.new : edgeColors.default;
    },
    'target-arrow-color': function(ele) {
      return isNewEdge(ele) ? edgeColors.new : edgeColors.default;
    }
  }
},
{
  selector: 'edge:hover',
  style: {
    'line-color': edgeColors.hover,
    'target-arrow-color': edgeColors.hover,
    'z-index': 999
  }
},
{
  selector: 'edge:selected',
  style: {
    'line-color': edgeColors.selected,
    'target-arrow-color': edgeColors.selected,
    'width': function(ele) {
      return calculateEdgeWidth(ele.data('confidence')) + 1;  // Slightly thicker
    }
  }
},
{
  selector: 'edge.neighborhood-dimmed',  // Click-to-highlight: non-neighbor edges
  style: {
    'line-color': edgeColors.dimmed,
    'target-arrow-color': edgeColors.dimmed,
    'opacity': 0.1
  }
}
```

### Arrow Style

All edges are directed; use target arrows:

```javascript
{
  selector: 'edge',
  style: {
    'curve-style': 'bezier',
    'target-arrow-shape': 'triangle',
    'target-arrow-fill': 'filled',
    'arrow-scale': 0.8
  }
}
```

### Edge Bundling (V2 Feature)

Enable edge bundling when edge count exceeds threshold:

```javascript
// V2: Edge bundling configuration
const EDGE_BUNDLING_THRESHOLD = 200;

function shouldBundleEdges(cy) {
  return cy.edges().length > EDGE_BUNDLING_THRESHOLD;
}

// Using cytoscape-edge-bundling extension
function enableEdgeBundling(cy) {
  if (!shouldBundleEdges(cy)) return;

  cy.edgeBundling({
    bundleThreshold: 0.6,
    K: 0.1
  });
}

// Unbundle on hover for specific node
function unbundleForNode(cy, node) {
  const connectedEdges = node.connectedEdges();
  connectedEdges.removeClass('bundled');
  connectedEdges.style('curve-style', 'bezier');
}
```

---

## Label Visibility

Labels are the primary source of visual clutter. Implement a tiered visibility system:

### Visibility Tiers

| Tier | Criteria | Label Behavior |
|------|----------|----------------|
| 1 | Top 20 nodes by size | Always visible |
| 2 | Nodes 21–50 by size | Visible if space allows (collision detection) |
| 3 | All other nodes | Show on hover only |
| 4 | Search matches | Always visible (override tiers) |
| 5 | Selected node + neighbors | Always visible (override tiers) |

### Implementation

```javascript
// Calculate which nodes should show labels
function updateLabelVisibility(cy) {
  const nodes = cy.nodes();

  // Sort by size (which correlates with importance)
  const sortedNodes = nodes.sort((a, b) => {
    return calculateNodeSize(b) - calculateNodeSize(a);
  });

  // Top 20 always visible
  const tier1 = sortedNodes.slice(0, 20);

  // Next 30 visible if not overlapping
  const tier2 = sortedNodes.slice(20, 50);

  // Rest hidden by default
  const tier3 = sortedNodes.slice(50);

  // Apply classes
  tier1.addClass('label-visible');
  tier2.addClass('label-conditional');
  tier3.addClass('label-hidden');

  // Run collision detection for tier 2
  updateConditionalLabels(cy, tier2);
}

function updateConditionalLabels(cy, nodes) {
  const visibleLabels = [];

  nodes.forEach(node => {
    const pos = node.renderedPosition();
    const label = node.data('label');
    const labelWidth = measureLabelWidth(label);

    // Check if this label would overlap with existing visible labels
    const overlaps = visibleLabels.some(existing => {
      return rectanglesOverlap(
        { x: pos.x, y: pos.y, width: labelWidth, height: 16 },
        existing
      );
    });

    if (!overlaps) {
      node.addClass('label-visible');
      node.removeClass('label-hidden');
      visibleLabels.push({ x: pos.x, y: pos.y, width: labelWidth, height: 16 });
    } else {
      node.addClass('label-hidden');
      node.removeClass('label-visible');
    }
  });
}
```

### Cytoscape Styles for Label Visibility

```javascript
{
  selector: 'node',
  style: {
    'label': function(ele) {
      return truncateLabel(ele.data('label'), 20);
    },
    'font-size': function(ele) {
      // Scale font with node size, within bounds
      const nodeSize = calculateNodeSize(ele);
      const fontSize = Math.max(10, Math.min(16, nodeSize * 0.4));
      return fontSize;
    },
    'text-valign': 'bottom',
    'text-halign': 'center',
    'text-margin-y': 5,
    'color': '#1F2937',
    'text-outline-color': '#FFFFFF',
    'text-outline-width': 2,
    'text-outline-opacity': 0.8
  }
},
{
  selector: 'node.label-hidden',
  style: {
    'label': ''  // Hide label
  }
},
{
  selector: 'node.label-visible',
  style: {
    'label': function(ele) {
      return truncateLabel(ele.data('label'), 20);
    }
  }
},
{
  selector: 'node:hover',
  style: {
    'label': function(ele) {
      return ele.data('label');  // Show full label on hover
    },
    'z-index': 9999,
    'font-size': 14,
    'font-weight': 'bold'
  }
},
{
  selector: 'node:selected',
  style: {
    'label': function(ele) {
      return ele.data('label');  // Show full label when selected
    },
    'font-weight': 'bold'
  }
}
```

### Progressive Label Reveal on Zoom

Show more labels as user zooms in:

```javascript
function updateLabelsOnZoom(cy) {
  const zoom = cy.zoom();

  if (zoom > 2.0) {
    // Zoomed in: show most labels
    cy.nodes().removeClass('label-hidden');
  } else if (zoom > 1.5) {
    // Moderately zoomed: show top 50
    updateLabelVisibility(cy);  // Re-run with expanded threshold
  } else {
    // Default zoom: standard visibility
    updateLabelVisibility(cy);
  }
}

// Attach to zoom event
cy.on('zoom', debounce(function() {
  updateLabelsOnZoom(cy);
}, 100));
```

### Label Truncation Helper

```javascript
function truncateLabel(label, maxLength) {
  if (!label) return '';
  if (label.length <= maxLength) return label;
  return label.substring(0, maxLength - 1) + '…';
}
```
