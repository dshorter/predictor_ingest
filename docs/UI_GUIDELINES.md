## Cytoscape Client UI Guidelines

This section provides comprehensive specifications for the Cytoscape.js visualization client. These guidelines are designed to be implementation-ready for code generation.

---

### Design Philosophy

The graph is a **living map with geographic memory**. Nodes maintain stable positions over time so that:

1. Emerging clusters appear in new regions of the map
2. Declining topics fade in place (visible through color/size changes, not disappearance)
3. Bridges between previously separate domains create visible long-distance edges
4. Users build spatial intuition ("AI safety discussions are always in the upper-right")

This spatial continuity is what makes trend detection visually intuitive. A user watching the graph over weeks should be able to see conceptual drift—new topics emerging in empty space, old topics fading but remaining in place, and unexpected connections spanning previously separate clusters.

---

### Information Density and Scale Management

#### Target Thresholds

| Node Count | Experience Level | Required Strategy |
|------------|------------------|-------------------|
| < 100 | Optimal comprehension | No intervention needed |
| 100–500 | Acceptable with good filtering | Provide filter controls |
| 500–2,000 | Requires active filtering | Warn user; suggest filtered view |
| 2,000–5,000 | Sluggish without optimization | Auto-filter to trending; offer "load all" with warning |
| > 5,000 | Unusable without server-side help | Refuse full client render; require pre-filtering |

#### Default View Strategy

Always default to `trending.json`, not the full graph. The trending view is pre-filtered to high-signal nodes and provides the best entry point for exploration.

#### Meta Object Requirement

Every exported JSON file MUST include a `meta` object at the top level for client-side decision making:

```json
{
  "meta": {
    "view": "trending",
    "nodeCount": 847,
    "edgeCount": 1392,
    "exportedAt": "2026-01-24T12:00:00Z",
    "dateRange": {
      "start": "2025-10-24",
      "end": "2026-01-24"
    },
    "filters": {
      "minVelocity": 0.1,
      "minConfidence": 0.3
    }
  },
  "elements": {
    "nodes": [...],
    "edges": [...]
  }
}
```

#### Client Behavior Based on Meta

```javascript
// Pseudocode for client-side scale handling
function handleGraphLoad(data) {
  const { nodeCount } = data.meta;
  
  if (nodeCount > 5000) {
    showError("Graph too large for client rendering. Please apply filters.");
    return;
  }
  
  if (nodeCount > 2000) {
    showWarning(`Large graph (${nodeCount} nodes). Showing trending subset.`);
    applyFilter({ showOnly: 'trending', limit: 500 });
    offerOption("Load all nodes anyway");
    return;
  }
  
  if (nodeCount > 500) {
    showInfo(`${nodeCount} nodes loaded. Use filters to focus exploration.`);
  }
  
  renderGraph(data);
}
```

---

### Node Visual Encoding

#### Node Data Structure

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

#### Sizing Strategy (Velocity-Weighted with Recency Boost)

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

#### Color Palette (by Entity Type)

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

#### Recency Overlay (Saturation/Opacity Based on lastSeen)

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

#### Node Border (Selection and Hover States)

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

### Edge Visual Encoding

#### Edge Data Structure

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

#### Line Style (by Kind)

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

#### Thickness (by Confidence)

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

#### Edge Color

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
}
```

#### Arrow Style

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

#### Edge Bundling (V2 Feature)

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

### Label Visibility

Labels are the primary source of visual clutter. Implement a tiered visibility system:

#### Visibility Tiers

| Tier | Criteria | Label Behavior |
|------|----------|----------------|
| 1 | Top 20 nodes by size | Always visible |
| 2 | Nodes 21–50 by size | Visible if space allows (collision detection) |
| 3 | All other nodes | Show on hover only |
| 4 | Search matches | Always visible (override tiers) |
| 5 | Selected node + neighbors | Always visible (override tiers) |

#### Implementation

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

#### Cytoscape Styles for Label Visibility

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

#### Progressive Label Reveal on Zoom

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

#### Label Truncation Helper

```javascript
function truncateLabel(label, maxLength) {
  if (!label) return '';
  if (label.length <= maxLength) return label;
  return label.substring(0, maxLength - 1) + '…';
}
```

---

### Interaction Patterns

#### Pan and Zoom

| Input | Action | Notes |
|-------|--------|-------|
| Mouse wheel | Zoom centered on cursor | Not viewport center |
| Drag on background | Pan | Standard behavior |
| Drag on node | Move node | Updates position in memory |
| Double-click background | Fit graph to viewport | Animated transition |
| Double-click node | Zoom to node + neighborhood | Show 1-hop neighbors |
| Pinch gesture (touch) | Zoom | Mobile support |
| Two-finger drag (touch) | Pan | Mobile support |

```javascript
// Cytoscape initialization options
const cyOptions = {
  container: document.getElementById('cy'),
  
  // Interaction settings
  zoomingEnabled: true,
  userZoomingEnabled: true,
  panningEnabled: true,
  userPanningEnabled: true,
  boxSelectionEnabled: true,
  selectionType: 'single',  // or 'additive' for multi-select
  
  // Touch settings
  touchTapThreshold: 8,
  desktopTapThreshold: 4,
  autoungrabifyNodes: false,
  
  // Zoom limits
  minZoom: 0.1,
  maxZoom: 5,
  
  // Wheel sensitivity
  wheelSensitivity: 0.2
};
```

#### Click vs Hover Behaviors

```javascript
// Hover: Preview mode
cy.on('mouseover', 'node', function(event) {
  const node = event.target;
  
  // Highlight node and immediate neighbors
  const neighborhood = node.closedNeighborhood();
  neighborhood.addClass('highlighted');
  
  // Dim everything else
  cy.elements().not(neighborhood).addClass('dimmed');
  
  // Show tooltip
  showNodeTooltip(node, event.renderedPosition);
});

cy.on('mouseout', 'node', function(event) {
  // Remove highlights
  cy.elements().removeClass('highlighted').removeClass('dimmed');
  
  // Hide tooltip
  hideTooltip();
});

// Click: Select mode
cy.on('tap', 'node', function(event) {
  const node = event.target;
  
  // If ctrl/cmd held, add to selection
  if (event.originalEvent.ctrlKey || event.originalEvent.metaKey) {
    node.select();
  } else {
    // Single select: clear others
    cy.elements().unselect();
    node.select();
  }
  
  // Open detail panel
  openNodeDetailPanel(node);
});

// Edge hover
cy.on('mouseover', 'edge', function(event) {
  const edge = event.target;
  edge.addClass('highlighted');
  
  // Show edge tooltip
  showEdgeTooltip(edge, event.renderedPosition);
});

cy.on('mouseout', 'edge', function(event) {
  event.target.removeClass('highlighted');
  hideTooltip();
});

// Edge click: Open evidence panel
cy.on('tap', 'edge', function(event) {
  const edge = event.target;
  edge.select();
  openEvidencePanel(edge);
});

// Background click: Deselect all
cy.on('tap', function(event) {
  if (event.target === cy) {
    cy.elements().unselect();
    closeAllPanels();
  }
});

// Double-click node: Zoom to neighborhood
cy.on('dbltap', 'node', function(event) {
  const node = event.target;
  const neighborhood = node.closedNeighborhood();
  
  cy.animate({
    fit: {
      eles: neighborhood,
      padding: 50
    },
    duration: 300
  });
});

// Double-click background: Fit all
cy.on('dbltap', function(event) {
  if (event.target === cy) {
    cy.animate({
      fit: {
        padding: 30
      },
      duration: 300
    });
  }
});
```

#### Right-Click Context Menu

Implement using a library like `cytoscape-context-menus` or custom HTML:

```javascript
// Context menu items for nodes
const nodeContextMenu = [
  {
    id: 'expand',
    content: 'Expand neighbors',
    selector: 'node',
    onClickFunction: function(event) {
      const node = event.target;
      expandNeighbors(node);
    }
  },
  {
    id: 'hide',
    content: 'Hide node',
    selector: 'node',
    onClickFunction: function(event) {
      const node = event.target;
      node.addClass('hidden');
      node.hide();
    }
  },
  {
    id: 'pin',
    content: 'Pin position',
    selector: 'node',
    onClickFunction: function(event) {
      const node = event.target;
      node.lock();
      node.addClass('pinned');
    }
  },
  {
    id: 'unpin',
    content: 'Unpin position',
    selector: 'node.pinned',
    onClickFunction: function(event) {
      const node = event.target;
      node.unlock();
      node.removeClass('pinned');
    }
  },
  {
    id: 'select-neighbors',
    content: 'Select all neighbors',
    selector: 'node',
    onClickFunction: function(event) {
      const node = event.target;
      node.neighborhood().select();
    }
  },
  {
    id: 'view-documents',
    content: 'View source documents',
    selector: 'node',
    onClickFunction: function(event) {
      const node = event.target;
      openDocumentList(node);
    }
  }
];

// Context menu items for edges
const edgeContextMenu = [
  {
    id: 'view-evidence',
    content: 'View evidence',
    selector: 'edge',
    onClickFunction: function(event) {
      const edge = event.target;
      openEvidencePanel(edge);
    }
  },
  {
    id: 'hide-edge',
    content: 'Hide relationship',
    selector: 'edge',
    onClickFunction: function(event) {
      const edge = event.target;
      edge.hide();
    }
  }
];

// Context menu for background
const backgroundContextMenu = [
  {
    id: 'show-all',
    content: 'Show all hidden elements',
    coreAsWell: true,
    onClickFunction: function() {
      cy.elements().removeClass('hidden').show();
    }
  },
  {
    id: 'fit-graph',
    content: 'Fit graph to view',
    coreAsWell: true,
    onClickFunction: function() {
      cy.fit(50);
    }
  },
  {
    id: 'run-layout',
    content: 'Re-run layout',
    coreAsWell: true,
    onClickFunction: function() {
      runForceDirectedLayout(cy);
    }
  }
];
```

---

### Tooltips

#### Node Tooltip Content

```javascript
function showNodeTooltip(node, position) {
  const data = node.data();
  
  const tooltip = document.getElementById('tooltip');
  tooltip.innerHTML = `
    <div class="tooltip-header">
      <span class="tooltip-type type-${data.type.toLowerCase()}">${data.type}</span>
      <span class="tooltip-label">${data.label}</span>
    </div>
    <div class="tooltip-body">
      <div class="tooltip-row">
        <span class="tooltip-key">First seen:</span>
        <span class="tooltip-value">${formatDate(data.firstSeen)}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-key">Last seen:</span>
        <span class="tooltip-value">${formatDate(data.lastSeen)}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-key">Mentions (7d):</span>
        <span class="tooltip-value">${data.mentionCount7d || 0}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-key">Connections:</span>
        <span class="tooltip-value">${data.degree || node.degree()}</span>
      </div>
      ${data.velocity > 0.5 ? `
        <div class="tooltip-badge trending">
          ↑ Trending (${(data.velocity * 100).toFixed(0)}% velocity)
        </div>
      ` : ''}
      ${isNewNode(data.firstSeen) ? `
        <div class="tooltip-badge new">
          ★ New (${daysBetween(data.firstSeen, today())} days old)
        </div>
      ` : ''}
    </div>
  `;
  
  // Position tooltip near cursor but not overlapping
  positionTooltip(tooltip, position);
  tooltip.classList.add('visible');
}

function hideTooltip() {
  const tooltip = document.getElementById('tooltip');
  tooltip.classList.remove('visible');
}
```

#### Edge Tooltip Content

```javascript
function showEdgeTooltip(edge, position) {
  const data = edge.data();
  const sourceLabel = edge.source().data('label');
  const targetLabel = edge.target().data('label');
  
  const tooltip = document.getElementById('tooltip');
  tooltip.innerHTML = `
    <div class="tooltip-header">
      <span class="tooltip-relation">${formatRelation(data.rel)}</span>
    </div>
    <div class="tooltip-body">
      <div class="tooltip-row relationship">
        <span class="tooltip-entity">${sourceLabel}</span>
        <span class="tooltip-arrow">→</span>
        <span class="tooltip-entity">${targetLabel}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-key">Kind:</span>
        <span class="tooltip-value kind-${data.kind}">${capitalize(data.kind)}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-key">Confidence:</span>
        <span class="tooltip-value">${(data.confidence * 100).toFixed(0)}%</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-key">Sources:</span>
        <span class="tooltip-value">${data.evidenceCount || 1} document(s)</span>
      </div>
    </div>
    <div class="tooltip-footer">
      Click for full evidence
    </div>
  `;
  
  positionTooltip(tooltip, position);
  tooltip.classList.add('visible');
}

function formatRelation(rel) {
  // Convert SNAKE_CASE to Title Case
  return rel.split('_').map(word => 
    word.charAt(0) + word.slice(1).toLowerCase()
  ).join(' ');
}
```

#### Tooltip Styling

```css
#tooltip {
  position: absolute;
  z-index: 10000;
  background: white;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 12px;
  min-width: 200px;
  max-width: 300px;
  font-size: 13px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

#tooltip.visible {
  opacity: 1;
}

.tooltip-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #E5E7EB;
}

.tooltip-type {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 4px;
  color: white;
}

.tooltip-type.type-org { background: #4A90D9; }
.tooltip-type.type-person { background: #50B4A8; }
.tooltip-type.type-model { background: #7C3AED; }
/* ... other types ... */

.tooltip-label {
  font-weight: 600;
  color: #1F2937;
}

.tooltip-row {
  display: flex;
  justify-content: space-between;
  margin: 4px 0;
}

.tooltip-key {
  color: #6B7280;
}

.tooltip-value {
  font-weight: 500;
  color: #1F2937;
}

.tooltip-badge {
  margin-top: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.tooltip-badge.trending {
  background: #FEF3C7;
  color: #D97706;
}

.tooltip-badge.new {
  background: #D1FAE5;
  color: #059669;
}

.tooltip-footer {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #E5E7EB;
  font-size: 11px;
  color: #9CA3AF;
}
```

---

### Search and Filter

#### Search Box (Always Visible)

Position at top of UI, always accessible:

```html
<div id="search-container">
  <input 
    type="text" 
    id="search-input" 
    placeholder="Search nodes..."
    autocomplete="off"
  />
  <span id="search-results-count"></span>
  <button id="search-clear" title="Clear search">×</button>
</div>
```

#### Search Implementation

```javascript
let searchTimeout;

document.getElementById('search-input').addEventListener('input', function(e) {
  clearTimeout(searchTimeout);
  
  // Debounce search
  searchTimeout = setTimeout(() => {
    performSearch(e.target.value);
  }, 150);
});

function performSearch(query) {
  const trimmedQuery = query.trim().toLowerCase();
  
  if (!trimmedQuery) {
    // Clear search
    cy.elements().removeClass('search-match').removeClass('dimmed');
    document.getElementById('search-results-count').textContent = '';
    return;
  }
  
  // Find matching nodes
  const matches = cy.nodes().filter(node => {
    const label = (node.data('label') || '').toLowerCase();
    const aliases = (node.data('aliases') || []).map(a => a.toLowerCase());
    const type = (node.data('type') || '').toLowerCase();
    
    return label.includes(trimmedQuery) ||
           aliases.some(alias => alias.includes(trimmedQuery)) ||
           type.includes(trimmedQuery);
  });
  
  // Update UI
  cy.elements().removeClass('search-match');
  
  if (matches.length > 0) {
    // Highlight matches
    matches.addClass('search-match');
    
    // Include edges between matches
    const matchEdges = matches.edgesWith(matches);
    matchEdges.addClass('search-match');
    
    // Dim non-matches
    cy.elements().not('.search-match').addClass('dimmed');
    
    // Show count
    document.getElementById('search-results-count').textContent = 
      `${matches.length} node${matches.length === 1 ? '' : 's'}`;
  } else {
    cy.elements().addClass('dimmed');
    document.getElementById('search-results-count').textContent = 'No matches';
  }
}

// Enter key: zoom to fit results
document.getElementById('search-input').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') {
    const matches = cy.nodes('.search-match');
    if (matches.length > 0) {
      cy.animate({
        fit: {
          eles: matches,
          padding: 50
        },
        duration: 300
      });
    }
  }
  
  // Escape: clear search
  if (e.key === 'Escape') {
    this.value = '';
    performSearch('');
    this.blur();
  }
});
```

#### Filter Panel

Collapsible sidebar with comprehensive filtering:

```html
<aside id="filter-panel" class="panel collapsed">
  <button id="filter-toggle" class="panel-toggle">
    <span class="icon">⚙</span>
    <span class="label">Filters</span>
  </button>
  
  <div class="panel-content">
    <!-- Date Range -->
    <section class="filter-section">
      <h3>Date Range</h3>
      <div class="date-range-inputs">
        <input type="date" id="filter-date-start" />
        <span>to</span>
        <input type="date" id="filter-date-end" />
      </div>
      <input 
        type="range" 
        id="filter-date-slider" 
        min="0" 
        max="100"
        class="date-slider"
      />
      <div class="date-presets">
        <button data-days="7">7d</button>
        <button data-days="30">30d</button>
        <button data-days="90">90d</button>
        <button data-days="all">All</button>
      </div>
    </section>
    
    <!-- Entity Types -->
    <section class="filter-section">
      <h3>Entity Types</h3>
      <div class="checkbox-grid">
        <label><input type="checkbox" data-type="Org" checked /> Org</label>
        <label><input type="checkbox" data-type="Person" checked /> Person</label>
        <label><input type="checkbox" data-type="Model" checked /> Model</label>
        <label><input type="checkbox" data-type="Tool" checked /> Tool</label>
        <label><input type="checkbox" data-type="Dataset" checked /> Dataset</label>
        <label><input type="checkbox" data-type="Benchmark" checked /> Benchmark</label>
        <label><input type="checkbox" data-type="Paper" checked /> Paper</label>
        <label><input type="checkbox" data-type="Repo" checked /> Repo</label>
        <label><input type="checkbox" data-type="Tech" checked /> Tech</label>
        <label><input type="checkbox" data-type="Topic" checked /> Topic</label>
        <label><input type="checkbox" data-type="Document" /> Document</label>
        <label><input type="checkbox" data-type="Event" checked /> Event</label>
        <label><input type="checkbox" data-type="Location" checked /> Location</label>
        <label><input type="checkbox" data-type="Other" checked /> Other</label>
      </div>
      <div class="type-actions">
        <button id="select-all-types">All</button>
        <button id="select-no-types">None</button>
      </div>
    </section>
    
    <!-- Relationship Kind -->
    <section class="filter-section">
      <h3>Relationship Kind</h3>
      <label><input type="checkbox" data-kind="asserted" checked /> Asserted</label>
      <label><input type="checkbox" data-kind="inferred" checked /> Inferred</label>
      <label><input type="checkbox" data-kind="hypothesis" /> Hypothesis</label>
    </section>
    
    <!-- Confidence Threshold -->
    <section class="filter-section">
      <h3>Minimum Confidence</h3>
      <input 
        type="range" 
        id="filter-confidence" 
        min="0" 
        max="100" 
        value="30"
      />
      <span id="confidence-value">30%</span>
    </section>
    
    <!-- View Presets -->
    <section class="filter-section">
      <h3>Show</h3>
      <label>
        <input type="radio" name="view-preset" value="all" />
        All nodes
      </label>
      <label>
        <input type="radio" name="view-preset" value="trending" checked />
        Trending only
      </label>
      <label>
        <input type="radio" name="view-preset" value="new" />
        New (last 7 days)
      </label>
    </section>
    
    <!-- Actions -->
    <section class="filter-actions">
      <button id="apply-filters" class="primary">Apply Filters</button>
      <button id="reset-filters">Reset All</button>
    </section>
  </div>
</aside>
```

#### Filter Implementation

```javascript
class GraphFilter {
  constructor(cy) {
    this.cy = cy;
    this.filters = {
      dateStart: null,
      dateEnd: null,
      types: new Set([
        'Org', 'Person', 'Model', 'Tool', 'Dataset', 'Benchmark',
        'Paper', 'Repo', 'Tech', 'Topic', 'Event', 'Location', 'Other'
      ]),
      kinds: new Set(['asserted', 'inferred']),
      minConfidence: 0.3,
      viewPreset: 'trending'
    };
  }
  
  setDateRange(start, end) {
    this.filters.dateStart = start;
    this.filters.dateEnd = end;
  }
  
  toggleType(type, enabled) {
    if (enabled) {
      this.filters.types.add(type);
    } else {
      this.filters.types.delete(type);
    }
  }
  
  toggleKind(kind, enabled) {
    if (enabled) {
      this.filters.kinds.add(kind);
    } else {
      this.filters.kinds.delete(kind);
    }
  }
  
  setMinConfidence(value) {
    this.filters.minConfidence = value;
  }
  
  setViewPreset(preset) {
    this.filters.viewPreset = preset;
  }
  
  apply() {
    const { cy, filters } = this;
    
    // Start with all elements visible
    cy.elements().removeClass('filtered-out');
    
    // Filter nodes
    cy.nodes().forEach(node => {
      let visible = true;
      
      // Type filter
      if (!filters.types.has(node.data('type'))) {
        visible = false;
      }
      
      // Date filter (by lastSeen)
      if (visible && filters.dateStart) {
        const lastSeen = node.data('lastSeen');
        if (lastSeen && lastSeen < filters.dateStart) {
          visible = false;
        }
      }
      
      if (visible && filters.dateEnd) {
        const firstSeen = node.data('firstSeen');
        if (firstSeen && firstSeen > filters.dateEnd) {
          visible = false;
        }
      }
      
      // View preset filters
      if (visible && filters.viewPreset === 'trending') {
        const velocity = node.data('velocity') || 0;
        if (velocity < 0.1) {
          visible = false;
        }
      }
      
      if (visible && filters.viewPreset === 'new') {
        const firstSeen = node.data('firstSeen');
        if (!isNewNode(firstSeen)) {
          visible = false;
        }
      }
      
      if (!visible) {
        node.addClass('filtered-out');
      }
    });
    
    // Filter edges
    cy.edges().forEach(edge => {
      let visible = true;
      
      // Kind filter
      if (!filters.kinds.has(edge.data('kind'))) {
        visible = false;
      }
      
      // Confidence filter
      const confidence = edge.data('confidence') || 0;
      if (confidence < filters.minConfidence) {
        visible = false;
      }
      
      // Hide edges connected to hidden nodes
      if (edge.source().hasClass('filtered-out') || 
          edge.target().hasClass('filtered-out')) {
        visible = false;
      }
      
      if (!visible) {
        edge.addClass('filtered-out');
      }
    });
    
    // Update visibility
    cy.elements('.filtered-out').hide();
    cy.elements().not('.filtered-out').show();
    
    // Update label visibility for remaining nodes
    updateLabelVisibility(cy);
    
    // Emit event for UI updates
    this.cy.emit('filtersApplied', this.getActiveFilterCount());
  }
  
  reset() {
    this.filters = {
      dateStart: null,
      dateEnd: null,
      types: new Set([
        'Org', 'Person', 'Model', 'Tool', 'Dataset', 'Benchmark',
        'Paper', 'Repo', 'Tech', 'Topic', 'Event', 'Location', 'Other'
      ]),
      kinds: new Set(['asserted', 'inferred']),
      minConfidence: 0.3,
      viewPreset: 'trending'
    };
    this.apply();
  }
  
  getActiveFilterCount() {
    let count = 0;
    if (this.filters.dateStart || this.filters.dateEnd) count++;
    if (this.filters.types.size < 14) count++;
    if (this.filters.kinds.size < 3) count++;
    if (this.filters.minConfidence > 0) count++;
    if (this.filters.viewPreset !== 'all') count++;
    return count;
  }
}
```

#### Filter Panel Styles

```css
.filtered-out {
  display: none !important;
}

#filter-panel {
  position: absolute;
  right: 0;
  top: 60px;  /* Below toolbar */
  bottom: 0;
  width: 280px;
  background: white;
  border-left: 1px solid #E5E7EB;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.05);
  transition: transform 0.3s ease;
  z-index: 100;
  overflow-y: auto;
}

#filter-panel.collapsed {
  transform: translateX(240px);
}

#filter-panel.collapsed .panel-content {
  opacity: 0;
  pointer-events: none;
}

.panel-toggle {
  position: absolute;
  left: -40px;
  top: 10px;
  width: 40px;
  height: 40px;
  background: white;
  border: 1px solid #E5E7EB;
  border-right: none;
  border-radius: 8px 0 0 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.panel-content {
  padding: 16px;
  transition: opacity 0.2s ease;
}

.filter-section {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #F3F4F6;
}

.filter-section h3 {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  color: #6B7280;
  margin-bottom: 12px;
}

.checkbox-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.checkbox-grid label {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.date-presets {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.date-presets button {
  flex: 1;
  padding: 6px;
  font-size: 12px;
  border: 1px solid #E5E7EB;
  background: white;
  border-radius: 4px;
  cursor: pointer;
}

.date-presets button:hover {
  background: #F9FAFB;
}

.date-presets button.active {
  background: #3B82F6;
  color: white;
  border-color: #3B82F6;
}

.filter-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.filter-actions button {
  flex: 1;
  padding: 10px;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
}

.filter-actions button.primary {
  background: #3B82F6;
  color: white;
  border: none;
}

.filter-actions button:not(.primary) {
  background: white;
  border: 1px solid #E5E7EB;
}
```

---

### Progressive Disclosure

#### Level 1: Overview (Default State)

The initial view shows a high-level summary optimized for trend detection:

```javascript
function showOverview(cy) {
  // Load trending view by default
  loadGraphView('trending');
  
  // Apply default filters
  const filter = new GraphFilter(cy);
  filter.setViewPreset('trending');
  filter.apply();
  
  // Run layout
  runLayout(cy, 'preset');  // V2: use preset if positions available
  
  // Fit to view
  cy.fit(50);
  
  // Update label visibility
  updateLabelVisibility(cy);
}
```

#### Level 2: Explore (Click to Expand)

When user clicks a node, reveal its neighborhood:

```javascript
function expandNeighbors(node, depth = 1) {
  const cy = node.cy();
  
  // Get neighbors up to specified depth
  let toExpand = node;
  for (let i = 0; i < depth; i++) {
    toExpand = toExpand.closedNeighborhood();
  }
  
  // If neighbors are hidden (filtered out), show them
  toExpand.removeClass('filtered-out').show();
  
  // Animate expansion
  const originalPositions = {};
  toExpand.nodes().forEach(n => {
    originalPositions[n.id()] = n.position();
    
    // New nodes start at the clicked node's position
    if (!n.visible() || n.hasClass('just-expanded')) {
      n.position(node.position());
      n.addClass('just-expanded');
    }
  });
  
  // Run local layout for just the expanded nodes
  toExpand.layout({
    name: 'concentric',
    concentric: function(n) {
      return n.id() === node.id() ? 10 : 1;
    },
    minNodeSpacing: 50,
    animate: true,
    animationDuration: 300
  }).run();
  
  // Update label visibility
  updateLabelVisibility(cy);
  
  // Fit to show expanded neighborhood
  cy.animate({
    fit: {
      eles: toExpand,
      padding: 50
    },
    duration: 300
  });
}
```

#### Level 3: Deep Dive (Detail Panel)

Full node metadata in a side panel:

```html
<aside id="detail-panel" class="panel hidden">
  <button class="panel-close">×</button>
  
  <div id="detail-content">
    <!-- Populated dynamically -->
  </div>
</aside>
```

```javascript
function openNodeDetailPanel(node) {
  const data = node.data();
  const panel = document.getElementById('detail-panel');
  const content = document.getElementById('detail-content');
  
  content.innerHTML = `
    <header class="detail-header">
      <span class="detail-type type-${data.type.toLowerCase()}">${data.type}</span>
      <h2 class="detail-title">${escapeHtml(data.label)}</h2>
      ${data.aliases && data.aliases.length > 0 ? `
        <div class="detail-aliases">
          Also known as: ${data.aliases.map(a => escapeHtml(a)).join(', ')}
        </div>
      ` : ''}
    </header>
    
    <section class="detail-section">
      <h3>Timeline</h3>
      <div class="detail-timeline">
        <div class="timeline-item">
          <span class="timeline-label">First seen</span>
          <span class="timeline-value">${formatDate(data.firstSeen)}</span>
          <span class="timeline-relative">${daysAgo(data.firstSeen)}</span>
        </div>
        <div class="timeline-item">
          <span class="timeline-label">Last seen</span>
          <span class="timeline-value">${formatDate(data.lastSeen)}</span>
          <span class="timeline-relative">${daysAgo(data.lastSeen)}</span>
        </div>
      </div>
    </section>
    
    <section class="detail-section">
      <h3>Activity</h3>
      <div class="detail-stats">
        <div class="stat">
          <span class="stat-value">${data.mentionCount7d || 0}</span>
          <span class="stat-label">Mentions (7d)</span>
        </div>
        <div class="stat">
          <span class="stat-value">${data.mentionCount30d || 0}</span>
          <span class="stat-label">Mentions (30d)</span>
        </div>
        <div class="stat">
          <span class="stat-value">${node.degree()}</span>
          <span class="stat-label">Connections</span>
        </div>
        <div class="stat ${data.velocity > 0.5 ? 'trending' : ''}">
          <span class="stat-value">${formatVelocity(data.velocity)}</span>
          <span class="stat-label">Velocity</span>
        </div>
      </div>
    </section>
    
    <section class="detail-section">
      <h3>Relationships (${node.connectedEdges().length})</h3>
      <div class="detail-relationships">
        ${renderRelationshipList(node)}
      </div>
    </section>
    
    <section class="detail-section">
      <h3>Source Documents</h3>
      <div class="detail-documents">
        ${renderDocumentList(node)}
      </div>
    </section>
    
    <footer class="detail-footer">
      <button class="btn" onclick="expandNeighbors(cy.$('#${data.id}'))">
        Expand neighbors
      </button>
      <button class="btn" onclick="zoomToNode(cy.$('#${data.id}'))">
        Center view
      </button>
    </footer>
  `;
  
  panel.classList.remove('hidden');
}

function renderRelationshipList(node) {
  const edges = node.connectedEdges();
  
  // Group by relationship type
  const grouped = {};
  edges.forEach(edge => {
    const rel = edge.data('rel');
    if (!grouped[rel]) grouped[rel] = [];
    grouped[rel].push(edge);
  });
  
  let html = '';
  for (const [rel, relEdges] of Object.entries(grouped)) {
    html += `
      <div class="relationship-group">
        <div class="relationship-type">${formatRelation(rel)}</div>
        <ul class="relationship-list">
          ${relEdges.slice(0, 5).map(edge => {
            const other = edge.source().id() === node.id() 
              ? edge.target() 
              : edge.source();
            const direction = edge.source().id() === node.id() ? '→' : '←';
            return `
              <li class="relationship-item" data-edge-id="${edge.id()}">
                <span class="rel-direction">${direction}</span>
                <span class="rel-target" onclick="selectNode('${other.id()}')">${other.data('label')}</span>
                <span class="rel-confidence">${(edge.data('confidence') * 100).toFixed(0)}%</span>
                <span class="rel-kind kind-${edge.data('kind')}">${edge.data('kind')}</span>
              </li>
            `;
          }).join('')}
          ${relEdges.length > 5 ? `
            <li class="relationship-more">
              +${relEdges.length - 5} more
            </li>
          ` : ''}
        </ul>
      </div>
    `;
  }
  
  return html;
}
```

#### Level 4: Evidence Panel (Edge Detail)

Full provenance for a relationship:

```javascript
function openEvidencePanel(edge) {
  const data = edge.data();
  const sourceNode = edge.source();
  const targetNode = edge.target();
  
  const panel = document.getElementById('evidence-panel');
  const content = document.getElementById('evidence-content');
  
  // Fetch full evidence (may need async call if not embedded in edge data)
  const evidence = data.evidence || [];
  
  content.innerHTML = `
    <header class="evidence-header">
      <div class="evidence-relationship">
        <span class="evidence-entity">${sourceNode.data('label')}</span>
        <span class="evidence-rel">${formatRelation(data.rel)}</span>
        <span class="evidence-entity">${targetNode.data('label')}</span>
      </div>
      <div class="evidence-meta">
        <span class="evidence-kind kind-${data.kind}">${capitalize(data.kind)}</span>
        <span class="evidence-confidence">
          ${(data.confidence * 100).toFixed(0)}% confidence
        </span>
        <span class="evidence-date">
          First asserted: ${formatDate(data.firstSeen)}
        </span>
      </div>
    </header>
    
    <section class="evidence-section">
      <h3>Evidence (${evidence.length} source${evidence.length === 1 ? '' : 's'})</h3>
      <ul class="evidence-list">
        ${evidence.map((ev, idx) => `
          <li class="evidence-item">
            <div class="evidence-source">
              <span class="evidence-icon">📄</span>
              <span class="evidence-title">${escapeHtml(ev.title || 'Untitled')}</span>
            </div>
            <div class="evidence-pub">
              ${ev.source || 'Unknown source'} · ${formatDate(ev.published)}
            </div>
            <blockquote class="evidence-snippet">
              "${escapeHtml(ev.snippet)}"
            </blockquote>
            <a href="${ev.url}" target="_blank" class="evidence-link">
              View document →
            </a>
          </li>
        `).join('')}
      </ul>
      ${evidence.length === 0 ? `
        <p class="evidence-empty">
          No evidence snippets available for this relationship.
          This may be an inferred or hypothesis edge.
        </p>
      ` : ''}
    </section>
    
    <footer class="evidence-footer">
      <button class="btn" onclick="selectNode('${sourceNode.id()}')">
        View ${sourceNode.data('label')}
      </button>
      <button class="btn" onclick="selectNode('${targetNode.id()}')">
        View ${targetNode.data('label')}
      </button>
    </footer>
  `;
  
  panel.classList.remove('hidden');
}
```

---

### Layout Strategy

#### V1: Force-Directed on Load

For V1, compute layout on each page load using a force-directed algorithm:

```javascript
// V1 Layout Configuration
const V1_LAYOUT_OPTIONS = {
  name: 'fcose',  // Fast compound spring embedder
  
  // Animation
  animate: true,
  animationDuration: 500,
  animationEasing: 'ease-out',
  
  // Layout quality
  quality: 'default',  // 'draft', 'default', or 'proof'
  randomize: true,
  
  // Node repulsion
  nodeRepulsion: 4500,
  idealEdgeLength: 100,
  edgeElasticity: 0.45,
  nestingFactor: 0.1,
  
  // Gravity (pulls disconnected components together)
  gravity: 0.25,
  gravityRange: 3.8,
  
  // Iteration limits
  numIter: 2500,
  
  // Tiling (for disconnected components)
  tile: true,
  tilingPaddingVertical: 30,
  tilingPaddingHorizontal: 30,
  
  // Fit after layout
  fit: true,
  padding: 30
};

function runForceDirectedLayout(cy) {
  showLayoutProgress(true);
  
  const layout = cy.layout(V1_LAYOUT_OPTIONS);
  
  layout.on('layoutstop', function() {
    showLayoutProgress(false);
    updateLabelVisibility(cy);
  });
  
  layout.run();
}
```

#### V2: Preset Default with Options

For V2, stored positions enable instant, stable rendering:

```javascript
// V2 Layout Modes
const LayoutMode = {
  PRESET: 'preset',
  FORCE: 'force',
  HYBRID: 'hybrid'
};

function runLayout(cy, mode = LayoutMode.PRESET) {
  switch (mode) {
    case LayoutMode.PRESET:
      runPresetLayout(cy);
      break;
    case LayoutMode.FORCE:
      runForceDirectedLayout(cy);
      break;
    case LayoutMode.HYBRID:
      runHybridLayout(cy);
      break;
  }
}

// Preset: Use stored positions (instant)
function runPresetLayout(cy) {
  const hasPositions = cy.nodes().every(n => n.position().x !== undefined);
  
  if (!hasPositions) {
    console.warn('No stored positions; falling back to force-directed');
    runForceDirectedLayout(cy);
    return;
  }
  
  cy.layout({
    name: 'preset',
    fit: true,
    padding: 30
  }).run();
  
  updateLabelVisibility(cy);
}

// Hybrid: Pin existing nodes, simulate new ones
function runHybridLayout(cy) {
  // Identify new nodes (no stored position or marked as new)
  const newNodes = cy.nodes().filter(n => {
    return !n.data('hasStoredPosition') || n.hasClass('just-added');
  });
  
  const existingNodes = cy.nodes().not(newNodes);
  
  // Lock existing nodes
  existingNodes.lock();
  
  // Place new nodes near their connected neighbors
  newNodes.forEach(node => {
    const neighbors = node.neighborhood('node');
    if (neighbors.length > 0) {
      // Average position of neighbors
      const avgX = neighbors.reduce((sum, n) => sum + n.position('x'), 0) / neighbors.length;
      const avgY = neighbors.reduce((sum, n) => sum + n.position('y'), 0) / neighbors.length;
      
      // Add some randomness to avoid overlap
      node.position({
        x: avgX + (Math.random() - 0.5) * 100,
        y: avgY + (Math.random() - 0.5) * 100
      });
    }
  });
  
  // Run constrained force-directed for new nodes only
  cy.layout({
    name: 'fcose',
    animate: true,
    animationDuration: 300,
    
    // Only affect new nodes
    fixedNodeConstraint: existingNodes.map(n => ({
      nodeId: n.id(),
      position: n.position()
    })),
    
    // Lighter simulation
    numIter: 500,
    nodeRepulsion: 3000,
    
    fit: false  // Don't change view
  }).run().on('layoutstop', () => {
    existingNodes.unlock();
    newNodes.removeClass('just-added');
    updateLabelVisibility(cy);
  });
}
```

#### Position Storage Format

When positions are saved (V2), the node data structure includes:

```json
{
  "data": {
    "id": "org:openai",
    "label": "OpenAI",
    "type": "Org",
    "hasStoredPosition": true
  },
  "position": {
    "x": 342.7,
    "y": -156.2
  }
}
```

The coordinate system is arbitrary (not pixels). The client scales to fit the viewport.

#### Daily Export Workflow (V2)

When generating daily exports, the backend should:

1. Load previous day's positions into a lookup table
2. For each node in today's graph:
   - If node existed yesterday: use previous position
   - If new node: leave position undefined (client will compute via hybrid layout)
3. Include `hasStoredPosition: true` only for nodes with carried-over positions

```python
# Pseudocode for backend position handling
def generate_export(today_graph, yesterday_positions):
    elements = {"nodes": [], "edges": []}
    
    for node in today_graph.nodes:
        node_data = {
            "data": {
                "id": node.id,
                "label": node.label,
                "type": node.type,
                # ... other fields
            }
        }
        
        # Check for existing position
        if node.id in yesterday_positions:
            node_data["position"] = yesterday_positions[node.id]
            node_data["data"]["hasStoredPosition"] = True
        else:
            # New node - no position
            node_data["data"]["hasStoredPosition"] = False
        
        elements["nodes"].append(node_data)
    
    return elements
```

---

### Temporal Features

#### V1: Static Temporal Filtering

V1 provides temporal context through filtering and visual encoding:

**Date Range Filter:**
- Implemented in Filter Panel (see Search and Filter section)
- Filters based on `firstSeen` and `lastSeen`
- Preset buttons: 7d, 30d, 90d, All

**Recency-Based Visual Encoding:**
- Node opacity/saturation based on `lastSeen` (see Node Visual Encoding)
- Edge color highlighting for new edges (see Edge Visual Encoding)

**"What's New" Toggle:**

```javascript
// Quick toggle for highlighting new elements
function toggleNewHighlight(enabled) {
  if (enabled) {
    // Highlight new nodes
    cy.nodes().forEach(node => {
      if (isNewNode(node.data('firstSeen'))) {
        node.addClass('new');
      }
    });
    
    // Highlight new edges  
    cy.edges().forEach(edge => {
      if (isNewEdge(edge)) {
        edge.addClass('new');
      }
    });
  } else {
    cy.elements().removeClass('new');
  }
}

function isNewNode(firstSeen) {
  if (!firstSeen) return false;
  return daysBetween(firstSeen, today()) <= 7;
}

function isNewEdge(edge) {
  const firstSeen = edge.data('firstSeen');
  if (!firstSeen) return false;
  return daysBetween(firstSeen, today()) <= 7;
}
```

**Temporal Information in Tooltips:**
- Node tooltip shows `firstSeen`, `lastSeen`, and days ago
- Edge tooltip shows first assertion date

#### V2: Time-Lapse Animation

Full animation support for watching graph evolution over time.

**Prerequisites:**
- Stored positions (preset layout)
- Cumulative daily exports (or reconstructable history)

**UI Controls:**

```html
<div id="timeline-controls" class="hidden">
  <button id="timeline-start" title="Jump to start">⏮</button>
  <button id="timeline-back" title="Previous day">◀</button>
  <button id="timeline-play" title="Play">▶</button>
  <button id="timeline-forward" title="Next day">▶</button>
  <button id="timeline-end" title="Jump to end">⏭</button>
  
  <input 
    type="range" 
    id="timeline-scrubber"
    min="0" 
    max="100"
  />
  
  <span id="timeline-date">2026-01-24</span>
  
  <div class="timeline-options">
    <label>
      Speed:
      <select id="timeline-speed">
        <option value="2000">0.5x</option>
        <option value="1000" selected>1x</option>
        <option value="500">2x</option>
        <option value="250">4x</option>
      </select>
    </label>
    <label>
      <input type="checkbox" id="timeline-labels" />
      Show labels
    </label>
    <label>
      <input type="checkbox" id="timeline-trails" />
      Trails
    </label>
  </div>
</div>
```

**Animation Implementation:**

```javascript
class TimelinePlayer {
  constructor(cy, snapshots) {
    this.cy = cy;
    this.snapshots = snapshots;  // Array of { date, elements }
    this.currentIndex = snapshots.length - 1;
    this.isPlaying = false;
    this.speed = 1000;  // ms per frame
    this.playInterval = null;
  }
  
  loadSnapshot(index) {
    if (index < 0 || index >= this.snapshots.length) return;
    
    const snapshot = this.snapshots[index];
    const cy = this.cy;
    
    // Get current elements for comparison
    const currentIds = new Set(cy.nodes().map(n => n.id()));
    const newIds = new Set(snapshot.elements.nodes.map(n => n.data.id));
    
    // Elements to add (new in this snapshot)
    const toAdd = snapshot.elements.nodes.filter(n => !currentIds.has(n.data.id));
    
    // Elements to remove (not in this snapshot)
    const toRemove = cy.nodes().filter(n => !newIds.has(n.id()));
    
    // Animate removals (fade out)
    toRemove.animate({
      style: { opacity: 0 },
      duration: this.speed * 0.3
    }).promise().then(() => {
      toRemove.remove();
    });
    
    // Add new elements (will fade in)
    if (toAdd.length > 0) {
      const added = cy.add(toAdd);
      added.style('opacity', 0);
      added.animate({
        style: { opacity: 1 },
        duration: this.speed * 0.3
      });
    }
    
    // Animate position changes for existing nodes
    cy.nodes().forEach(node => {
      const snapshotNode = snapshot.elements.nodes.find(n => n.data.id === node.id());
      if (snapshotNode && snapshotNode.position) {
        node.animate({
          position: snapshotNode.position,
          duration: this.speed * 0.5,
          easing: 'ease-in-out'
        });
      }
    });
    
    // Update size/color based on snapshot data
    cy.nodes().forEach(node => {
      const snapshotNode = snapshot.elements.nodes.find(n => n.data.id === node.id());
      if (snapshotNode) {
        // Update data (triggers style recalculation)
        node.data(snapshotNode.data);
      }
    });
    
    // Similarly handle edges...
    
    this.currentIndex = index;
    this.updateUI();
  }
  
  play() {
    if (this.isPlaying) return;
    
    this.isPlaying = true;
    document.getElementById('timeline-play').textContent = '⏸';
    
    this.playInterval = setInterval(() => {
      if (this.currentIndex >= this.snapshots.length - 1) {
        this.pause();
        return;
      }
      this.loadSnapshot(this.currentIndex + 1);
    }, this.speed);
  }
  
  pause() {
    this.isPlaying = false;
    document.getElementById('timeline-play').textContent = '▶';
    
    if (this.playInterval) {
      clearInterval(this.playInterval);
      this.playInterval = null;
    }
  }
  
  toggle() {
    if (this.isPlaying) {
      this.pause();
    } else {
      this.play();
    }
  }
  
  jumpTo(index) {
    this.pause();
    this.loadSnapshot(index);
  }
  
  setSpeed(ms) {
    this.speed = ms;
    if (this.isPlaying) {
      this.pause();
      this.play();
    }
  }
  
  updateUI() {
    const date = this.snapshots[this.currentIndex].date;
    document.getElementById('timeline-date').textContent = date;
    
    const scrubber = document.getElementById('timeline-scrubber');
    scrubber.value = (this.currentIndex / (this.snapshots.length - 1)) * 100;
  }
}
```

---

### Toolbar and Global Controls

#### Toolbar Layout

```html
<header id="toolbar">
  <div class="toolbar-left">
    <h1 class="app-title">AI Trend Graph</h1>
    
    <div class="toolbar-group">
      <label>View:</label>
      <select id="view-selector">
        <option value="trending">Trending</option>
        <option value="claims">Claims</option>
        <option value="mentions">Mentions</option>
        <option value="dependencies">Dependencies</option>
      </select>
    </div>
    
    <div class="toolbar-group">
      <label>Date:</label>
      <select id="date-selector">
        <!-- Populated dynamically -->
      </select>
    </div>
  </div>
  
  <div class="toolbar-center">
    <div id="search-container">
      <input type="text" id="search-input" placeholder="Search nodes..." />
      <span id="search-results-count"></span>
    </div>
  </div>
  
  <div class="toolbar-right">
    <button id="btn-zoom-in" title="Zoom in">+</button>
    <button id="btn-zoom-out" title="Zoom out">−</button>
    <button id="btn-fit" title="Fit to view">⊡</button>
    <button id="btn-layout" title="Re-run layout">↻</button>
    <button id="btn-fullscreen" title="Fullscreen">⛶</button>
  </div>
</header>
```

#### Toolbar Implementation

```javascript
// View selector
document.getElementById('view-selector').addEventListener('change', async (e) => {
  const view = e.target.value;
  const date = document.getElementById('date-selector').value;
  await loadGraphView(view, date);
});

// Date selector
document.getElementById('date-selector').addEventListener('change', async (e) => {
  const date = e.target.value;
  const view = document.getElementById('view-selector').value;
  await loadGraphView(view, date);
});

// Zoom controls
document.getElementById('btn-zoom-in').addEventListener('click', () => {
  cy.zoom({
    level: cy.zoom() * 1.2,
    renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 }
  });
});

document.getElementById('btn-zoom-out').addEventListener('click', () => {
  cy.zoom({
    level: cy.zoom() / 1.2,
    renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 }
  });
});

// Fit to view
document.getElementById('btn-fit').addEventListener('click', () => {
  cy.animate({
    fit: { padding: 30 },
    duration: 300
  });
});

// Re-run layout
document.getElementById('btn-layout').addEventListener('click', () => {
  runForceDirectedLayout(cy);
});

// Fullscreen
document.getElementById('btn-fullscreen').addEventListener('click', () => {
  const container = document.getElementById('app');
  if (document.fullscreenElement) {
    document.exitFullscreen();
  } else {
    container.requestFullscreen();
  }
});
```

---

### Performance Guidelines

#### Client-Side Rendering Thresholds

| Node Count | Edge Count | Recommendation |
|------------|------------|----------------|
| < 500 | < 1,000 | Render all; smooth experience |
| 500–1,000 | 1,000–2,000 | Enable text-on-viewport optimization |
| 1,000–2,000 | 2,000–5,000 | Warn user; suggest filtering |
| 2,000–5,000 | 5,000–10,000 | Auto-filter; load full on demand |
| > 5,000 | > 10,000 | Require server-side filtering |

#### Cytoscape Performance Optimizations

```javascript
// Performance settings for large graphs
const PERFORMANCE_OPTIONS = {
  // Texture on viewport: render to canvas when panning/zooming
  textureOnViewport: true,
  
  // Disable expensive operations during interaction
  hideEdgesOnViewport: false,  // Set to true for very large graphs
  hideLabelsOnViewport: true,
  
  // Reduce quality during motion
  motionBlur: false,
  
  // Wheel sensitivity (lower = less redraws)
  wheelSensitivity: 0.1,
  
  // Minimum zoom (prevents over-zoom and high node density)
  minZoom: 0.1,
  maxZoom: 3
};

// Apply when graph is large
function applyPerformanceMode(cy) {
  const nodeCount = cy.nodes().length;
  
  if (nodeCount > 1000) {
    cy.style()
      .selector('edge')
      .style({
        'curve-style': 'haystack'  // Faster than bezier
      })
      .update();
  }
  
  if (nodeCount > 2000) {
    // Disable animations
    cy.style()
      .selector('*')
      .style({
        'transition-property': 'none'
      })
      .update();
  }
}
```

#### Lazy Loading (V2)

For very large graphs, load details on demand:

```javascript
// Initial load: only node positions and minimal data
async function loadGraphSkeleton(view, date) {
  const response = await fetch(`/api/graphs/${date}/${view}/skeleton`);
  const skeleton = await response.json();
  
  // Skeleton contains: id, label, type, position, degree
  // Does NOT contain: aliases, evidence, full metadata
  
  cy.json({ elements: skeleton.elements });
}

// On node select: fetch full details
async function loadNodeDetails(nodeId) {
  const response = await fetch(`/api/nodes/${nodeId}`);
  const details = await response.json();
  
  // Update node data with full details
  cy.$(`#${nodeId}`).data(details);
  
  return details;
}

// On edge click: fetch evidence
async function loadEdgeEvidence(edgeId) {
  const response = await fetch(`/api/edges/${edgeId}/evidence`);
  const evidence = await response.json();
  
  return evidence;
}
```

#### JSON Compression

All graph exports should be gzipped. Modern browsers decompress automatically:

```python
# Backend: serve with gzip
import gzip

def export_graph(elements, output_path):
    json_str = json.dumps(elements, separators=(',', ':'))  # Compact
    
    with gzip.open(f"{output_path}.gz", 'wt', encoding='utf-8') as f:
        f.write(json_str)
```

```nginx
# Nginx: enable gzip
gzip on;
gzip_types application/json;
gzip_min_length 1000;
```

---

### Accessibility

#### Color Accessibility

- All color combinations must meet WCAG AA contrast ratio (4.5:1 for text, 3:1 for UI)
- Provide colorblind-safe palette option
- Never rely on color alone; use shape, pattern, or label

**Colorblind-Safe Alternative Palette:**

| Type | Default Color | Deuteranopia Safe |
|------|---------------|-------------------|
| Org | `#4A90D9` (Blue) | `#4A90D9` (Blue) |
| Person | `#50B4A8` (Teal) | `#D98200` (Orange) |
| Model | `#7C3AED` (Violet) | `#7C3AED` (Violet) |
| Dataset | `#F59E0B` (Orange) | `#0077BB` (Blue) |
| Paper | `#10B981` (Green) | `#EE7733` (Orange) |

```javascript
// Toggle colorblind mode
function setColorblindMode(enabled) {
  if (enabled) {
    cy.style()
      .selector('node[type = "Person"]')
      .style({ 'background-color': '#D98200' })
      .selector('node[type = "Dataset"]')
      .style({ 'background-color': '#0077BB' })
      .selector('node[type = "Paper"]')
      .style({ 'background-color': '#EE7733' })
      .update();
  } else {
    // Reset to default colors
    cy.style().resetToDefault().update();
  }
}
```

#### Keyboard Navigation

```javascript
// Enable keyboard navigation
document.addEventListener('keydown', (e) => {
  // Only when graph is focused
  if (document.activeElement !== cy.container()) return;
  
  const selected = cy.nodes(':selected');
  
  switch (e.key) {
    case 'Tab':
      e.preventDefault();
      // Move to next node
      const nodes = cy.nodes(':visible');
      const currentIndex = selected.length > 0 
        ? nodes.indexOf(selected[0]) 
        : -1;
      const nextIndex = (currentIndex + 1) % nodes.length;
      
      cy.nodes().unselect();
      nodes[nextIndex].select();
      centerOnNode(nodes[nextIndex]);
      break;
      
    case 'Enter':
      // Open detail panel for selected node
      if (selected.length > 0) {
        openNodeDetailPanel(selected[0]);
      }
      break;
      
    case 'Escape':
      // Close panels, clear selection
      closeAllPanels();
      cy.nodes().unselect();
      break;
      
    case '+':
    case '=':
      cy.zoom(cy.zoom() * 1.2);
      break;
      
    case '-':
      cy.zoom(cy.zoom() / 1.2);
      break;
      
    case '0':
      cy.fit(30);
      break;
      
    case 'ArrowUp':
    case 'ArrowDown':
    case 'ArrowLeft':
    case 'ArrowRight':
      e.preventDefault();
      // Navigate to nearest neighbor in direction
      if (selected.length > 0) {
        navigateToNeighbor(selected[0], e.key);
      }
      break;
  }
});

// Make container focusable
cy.container().setAttribute('tabindex', '0');
cy.container().setAttribute('role', 'application');
cy.container().setAttribute('aria-label', 'AI Trend Graph visualization');
```

#### Screen Reader Support

```javascript
// Announce selection changes
cy.on('select', 'node', function(event) {
  const node = event.target;
  const announcement = `Selected ${node.data('type')}: ${node.data('label')}. ` +
                       `${node.degree()} connections. ` +
                       `First seen ${formatDate(node.data('firstSeen'))}.`;
  
  announceToScreenReader(announcement);
});

function announceToScreenReader(text) {
  const announcer = document.getElementById('sr-announcer');
  announcer.textContent = text;
}
```

```html
<!-- Screen reader announcements -->
<div 
  id="sr-announcer" 
  aria-live="polite" 
  aria-atomic="true"
  class="sr-only"
></div>

<style>
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
```

#### Reduced Motion

```javascript
// Respect prefers-reduced-motion
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function animateIfAllowed(options) {
  if (prefersReducedMotion) {
    // Skip animation, apply immediately
    return Promise.resolve();
  }
  return cy.animate(options).promise();
}

// Use throughout:
animateIfAllowed({
  fit: { padding: 30 },
  duration: 300
});
```

---

### V1 vs V2 Feature Matrix

| Feature | V1 | V2 | Notes |
|---------|:--:|:--:|-------|
| **Layout** | | | |
| Force-directed on load | ✅ | ✅ | Optional in V2 |
| Preset layout | ❌ | ✅ | Default in V2 |
| Position storage | ❌ | ✅ | Enables stability |
| Hybrid layout ("Integrate new") | ❌ | ✅ | For daily updates |
| | | | |
| **Visualization** | | | |
| Velocity-based node sizing | ✅ | ✅ | |
| Type-based node coloring | ✅ | ✅ | |
| Recency opacity/saturation | ✅ | ✅ | |
| Confidence-based edge thickness | ✅ | ✅ | |
| Kind-based edge style | ✅ | ✅ | |
| Edge bundling | ❌ | ✅ | For dense graphs |
| | | | |
| **Interaction** | | | |
| Pan/zoom | ✅ | ✅ | |
| Click to select | ✅ | ✅ | |
| Hover to preview | ✅ | ✅ | |
| Context menu | ✅ | ✅ | |
| Node expansion | ❌ | ✅ | Load neighbors on demand |
| | | | |
| **Filtering** | | | |
| Date range filter | ✅ | ✅ | |
| Entity type filter | ✅ | ✅ | |
| Kind toggles | ✅ | ✅ | |
| Confidence threshold | ✅ | ✅ | |
| View presets (trending/new/all) | ✅ | ✅ | |
| | | | |
| **Search** | | | |
| Search by label/alias | ✅ | ✅ | |
| Search highlighting | ✅ | ✅ | |
| Zoom to results | ✅ | ✅ | |
| | | | |
| **Information Display** | | | |
| Node tooltips | ✅ | ✅ | |
| Edge tooltips | ✅ | ✅ | |
| Node detail panel | ✅ | ✅ | |
| Evidence panel | ✅ | ✅ | |
| | | | |
| **Temporal** | | | |
| Recency-based visual encoding | ✅ | ✅ | |
| "What's new" highlighting | ✅ | ✅ | |
| Time-lapse animation | ❌ | ✅ | |
| Timeline scrubber | ❌ | ✅ | |
| | | | |
| **Performance** | | | |
| Gzipped JSON | ✅ | ✅ | |
| Auto-filter large graphs | ✅ | ✅ | |
| Lazy loading details | ❌ | ✅ | |
| WebGL renderer | ❌ | ✅ | For 5k+ nodes |
| | | | |
| **Accessibility** | | | |
| Keyboard navigation | ✅ | ✅ | |
| Screen reader support | ✅ | ✅ | |
| Colorblind mode | ✅ | ✅ | |
| Reduced motion | ✅ | ✅ | |
| | | | |
| **Persistence** | | | |
| User preferences | ❌ | ✅ | localStorage |
| Saved views/filters | ❌ | ✅ | |

---

### File Structure (web/)

Recommended directory structure for the Cytoscape client:

```
web/
├── index.html              # Main HTML shell
├── css/
│   ├── main.css            # Core layout and components
│   ├── toolbar.css         # Toolbar styles
│   ├── panels.css          # Side panels (filter, detail, evidence)
│   ├── tooltips.css        # Tooltip styles
│   └── accessibility.css   # Screen reader, focus states
├── js/
│   ├── app.js              # Main application initialization
│   ├── graph.js            # Cytoscape setup and configuration
│   ├── styles.js           # Cytoscape visual styles
│   ├── layout.js           # Layout algorithms and positioning
│   ├── filter.js           # GraphFilter class
│   ├── search.js           # Search functionality
│   ├── panels.js           # Panel management (detail, evidence)
│   ├── tooltips.js         # Tooltip rendering
│   ├── timeline.js         # V2: TimelinePlayer class
│   ├── accessibility.js    # Keyboard nav, screen reader
│   └── utils.js            # Helper functions
├── assets/
│   └── icons/              # UI icons (SVG preferred)
└── lib/
    ├── cytoscape.min.js    # Cytoscape.js core
    ├── cytoscape-fcose.js  # Force-directed layout
    └── cytoscape-context-menus.js  # Right-click menus
```

---

### Dependencies

#### Required (V1)

| Library | Version | Purpose |
|---------|---------|---------|
| Cytoscape.js | ^3.28.0 | Core graph visualization |
| cytoscape-fcose | ^2.2.0 | Fast force-directed layout |

#### Optional (V1)

| Library | Version | Purpose |
|---------|---------|---------|
| cytoscape-context-menus | ^4.1.0 | Right-click menus |
| cytoscape-popper | ^2.0.0 | Tooltip positioning |

#### V2 Additions

| Library | Version | Purpose |
|---------|---------|---------|
| cytoscape-cose-bilkent | ^4.1.0 | Alternative layout algorithm |
| cytoscape-edge-bundling | ^1.0.0 | Edge bundling |
| cytoscape-webgl | ^0.1.0 | WebGL renderer for large graphs |

#### CDN Links

```html
<!-- Cytoscape core -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>

<!-- fcose layout -->
<script src="https://cdn.jsdelivr.net/npm/cytoscape-fcose@2.2.0/cytoscape-fcose.min.js"></script>

<!-- Context menus (optional) -->
<script src="https://cdn.jsdelivr.net/npm/cytoscape-context-menus@4.1.0/cytoscape-context-menus.min.js"></script>
```

---## Cytoscape Client UI Guidelines

This section provides comprehensive specifications for the Cytoscape.js visualization client. These guidelines are designed to be implementation-ready for code generation.

---

### Design Philosophy

The graph is a **living map with geographic memory**. Nodes maintain stable positions over time so that:

1. Emerging clusters appear in new regions of the map
2. Declining topics fade in place (visible through color/size changes, not disappearance)
3. Bridges between previously separate domains create visible long-distance edges
4. Users build spatial intuition ("AI safety discussions are always in the upper-right")

This spatial continuity is what makes trend detection visually intuitive. A user watching the graph over weeks should be able to see conceptual drift—new topics emerging in empty space, old topics fading but remaining in place, and unexpected connections spanning previously separate clusters.

---

### Information Density and Scale Management

#### Target Thresholds

| Node Count | Experience Level | Required Strategy |
|------------|------------------|-------------------|
| < 100 | Optimal comprehension | No intervention needed |
| 100–500 | Acceptable with good filtering | Provide filter controls |
| 500–2,000 | Requires active filtering | Warn user; suggest filtered view |
| 2,000–5,000 | Sluggish without optimization | Auto-filter to trending; offer "load all" with warning |
| > 5,000 | Unusable without server-side help | Refuse full client render; require pre-filtering |

#### Default View Strategy

Always default to `trending.json`, not the full graph. The trending view is pre-filtered to high-signal nodes and provides the best entry point for exploration.

#### Meta Object Requirement

Every exported JSON file MUST include a `meta` object at the top level for client-side decision making:

```json
{
  "meta": {
    "view": "trending",
    "nodeCount": 847,
    "edgeCount": 1392,
    "exportedAt": "2026-01-24T12:00:00Z",
    "dateRange": {
      "start": "2025-10-24",
      "end": "2026-01-24"
    },
    "filters": {
      "minVelocity": 0.1,
      "minConfidence": 0.3
    }
  },
  "elements": {
    "nodes": [...],
    "edges": [...]
  }
}
```

#### Client Behavior Based on Meta

```javascript
// Pseudocode for client-side scale handling
function handleGraphLoad(data) {
  const { nodeCount } = data.meta;
  
  if (nodeCount > 5000) {
    showError("Graph too large for client rendering. Please apply filters.");
    return;
  }
  
  if (nodeCount > 2000) {
    showWarning(`Large graph (${nodeCount} nodes). Showing trending subset.`);
    applyFilter({ showOnly: 'trending', limit: 500 });
    offerOption("Load all nodes anyway");
    return;
  }
  
  if (nodeCount > 500) {
    showInfo(`${nodeCount} nodes loaded. Use filters to focus exploration.`);
  }
  
  renderGraph(data);
}
```

---

### Node Visual Encoding

#### Node Data Structure

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

#### Sizing Strategy (Velocity-Weighted with Recency Boost)

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

#### Color Palette (by Entity Type)

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

#### Recency Overlay (Saturation/Opacity Based on lastSeen)

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

#### Node Border (Selection and Hover States)

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

### Edge Visual Encoding

#### Edge Data Structure

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

#### Line Style (by Kind)

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

#### Thickness (by Confidence)

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

#### Edge Color

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
}
```

#### Arrow Style

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

#### Edge Bundling (V2 Feature)

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

### Label Visibility

Labels are the primary source of visual clutter. Implement a tiered visibility system:

#### Visibility Tiers

| Tier | Criteria | Label Behavior |
|------|----------|----------------|
| 1 | Top 20 nodes by size | Always visible |
| 2 | Nodes 21–50 by size | Visible if space allows (collision detection) |
| 3 | All other nodes | Show on hover only |
| 4 | Search matches | Always visible (override tiers) |
| 5 | Selected node + neighbors | Always visible (override tiers) |

#### Implementation

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

#### Cytoscape Styles for Label Visibility

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

#### Progressive Label Reveal on Zoom

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

#### Label Truncation Helper

```javascript
function truncateLabel(label, maxLength) {
  if (!label) return '';
  if (label.length <= maxLength) return label;
  return label.substring(0, maxLength - 1) + '…';
}
```

---

### Interaction Patterns

#### Pan and Zoom

| Input | Action | Notes |
|-------|--------|-------|
| Mouse wheel | Zoom centered on cursor | Not viewport center |
| Drag on background | Pan | Standard behavior |
| Drag on node | Move node | Updates position in memory |
| Double-click background | Fit graph to viewport | Animated transition |
| Double-click node | Zoom to node + neighborhood | Show 1-hop neighbors |
| Pinch gesture (touch) | Zoom | Mobile support |
| Two-finger drag (touch) | Pan | Mobile support |

```javascript
// Cytoscape initialization options
const cyOptions = {
  container: document.getElementById('cy'),
  
  // Interaction settings
  zoomingEnabled: true,
  userZoomingEnabled: true,
  panningEnabled: true,
  userPanningEnabled: true,
  boxSelectionEnabled: true,
  selectionType: 'single',  // or 'additive' for multi-select
  
  // Touch settings
  touchTapThreshold: 8,
  desktopTapThreshold: 4,
  autoungrabifyNodes: false,
  
  // Zoom limits
  minZoom: 0.1,
  maxZoom: 5,
  
  // Wheel sensitivity
  wheelSensitivity: 0.2
};
```

#### Click vs Hover Behaviors

```javascript
// Hover: Preview mode
cy.on('mouseover', 'node', function(event) {
  const node = event.target;
  
  // Highlight node and immediate neighbors
  const neighborhood = node.closedNeighborhood();
  neighborhood.addClass('highlighted');
  
  // Dim everything else
  cy.elements().not(neighborhood).addClass('dimmed');
  
  // Show tooltip
  showNodeTooltip(node, event.renderedPosition);
});

cy.on('mouseout', 'node', function(event) {
  // Remove highlights
  cy.elements().removeClass('highlighted').removeClass('dimmed');
  
  // Hide tooltip
  hideTooltip();
});

// Click: Select mode
cy.on('tap', 'node', function(event) {
  const node = event.target;
  
  // If ctrl/cmd held, add to selection
  if (event.originalEvent.ctrlKey || event.originalEvent.metaKey) {
    node.select();
  } else {
    // Single select: clear others
    cy.elements().unselect();
    node.select();
  }
  
  // Open detail panel
  openNodeDetailPanel(node);
});

// Edge hover
cy.on('mouseover', 'edge', function(event) {
  const edge = event.target;
  edge.addClass('highlighted');
  
  // Show edge tooltip
  showEdgeTooltip(edge, event.renderedPosition);
});

cy.on('mouseout', 'edge', function(event) {
  event.target.removeClass('highlighted');
  hideTooltip();
});

// Edge click: Open evidence panel
cy.on('tap', 'edge', function(event) {
  const edge = event.target;
  edge.select();
  openEvidencePanel(edge);
});

// Background click: Deselect all
cy.on('tap', function(event) {
  if (event.target === cy) {
    cy.elements().unselect();
    closeAllPanels();
  }
});

// Double-click node: Zoom to neighborhood
cy.on('dbltap', 'node', function(event) {
  const node = event.target;
  const neighborhood = node.closedNeighborhood();
  
  cy.animate({
    fit: {
      eles: neighborhood,
      padding: 50
    },
    duration: 300
  });
});

// Double-click background: Fit all
cy.on('dbltap', function(event) {
  if (event.target === cy) {
    cy.animate({
      fit: {
        padding: 30
      },
      duration: 300
    });
  }
});
```

#### Right-Click Context Menu

Implement using a library like `cytoscape-context-menus` or custom HTML:

```javascript
// Context menu items for nodes
const nodeContextMenu = [
  {
    id: 'expand',
    content: 'Expand neighbors',
    selector: 'node',
    onClickFunction: function(event) {
      const node = event.target;
      expandNeighbors(node);
    }
  },
  {
    id: 'hide',
    content: 'Hide node',
    selector: 'node',
    onClickFunction: function(event) {
      const node = event.target;
      node.addClass('hidden');
      node.hide();
    }
  },
  {
    id: 'pin',
    content: 'Pin position',
    selector: 'node',
    onClickFunction: function(event) {
      const node = event.target;
      node.lock();
      node.addClass('pinned');
    }
  },
  {
    id: 'unpin',
    content: 'Unpin position',
    selector: 'node.pinned',
    onClickFunction: function(event) {
      const node = event.target;
      node.unlock();
      node.removeClass('pinned');
    }
  },
  {
    id: 'select-neighbors',
    content: 'Select all neighbors',
    selector: 'node',
    onClickFunction: function(event) {
      const node = event.target;
      node.neighborhood().select();
    }
  },
  {
    id: 'view-documents',
    content: 'View source documents',
    selector: 'node',
    onClickFunction: function(event) {
      const node = event.target;
      openDocumentList(node);
    }
  }
];

// Context menu items for edges
const edgeContextMenu = [
  {
    id: 'view-evidence',
    content: 'View evidence',
    selector: 'edge',
    onClickFunction: function(event) {
      const edge = event.target;
      openEvidencePanel(edge);
    }
  },
  {
    id: 'hide-edge',
    content: 'Hide relationship',
    selector: 'edge',
    onClickFunction: function(event) {
      const edge = event.target;
      edge.hide();
    }
  }
];

// Context menu for background
const backgroundContextMenu = [
  {
    id: 'show-all',
    content: 'Show all hidden elements',
    coreAsWell: true,
    onClickFunction: function() {
      cy.elements().removeClass('hidden').show();
    }
  },
  {
    id: 'fit-graph',
    content: 'Fit graph to view',
    coreAsWell: true,
    onClickFunction: function() {
      cy.fit(50);
    }
  },
  {
    id: 'run-layout',
    content: 'Re-run layout',
    coreAsWell: true,
    onClickFunction: function() {
      runForceDirectedLayout(cy);
    }
  }
];
```

---

### Tooltips

#### Node Tooltip Content

```javascript
function showNodeTooltip(node, position) {
  const data = node.data();
  
  const tooltip = document.getElementById('tooltip');
  tooltip.innerHTML = `
    <div class="tooltip-header">
      <span class="tooltip-type type-${data.type.toLowerCase()}">${data.type}</span>
      <span class="tooltip-label">${data.label}</span>
    </div>
    <div class="tooltip-body">
      <div class="tooltip-row">
        <span class="tooltip-key">First seen:</span>
        <span class="tooltip-value">${formatDate(data.firstSeen)}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-key">Last seen:</span>
        <span class="tooltip-value">${formatDate(data.lastSeen)}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-key">Mentions (7d):</span>
        <span class="tooltip-value">${data.mentionCount7d || 0}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-key">Connections:</span>
        <span class="tooltip-value">${data.degree || node.degree()}</span>
      </div>
      ${data.velocity > 0.5 ? `
        <div class="tooltip-badge trending">
          ↑ Trending (${(data.velocity * 100).toFixed(0)}% velocity)
        </div>
      ` : ''}
      ${isNewNode(data.firstSeen) ? `
        <div class="tooltip-badge new">
          ★ New (${daysBetween(data.firstSeen, today())} days old)
        </div>
      ` : ''}
    </div>
  `;
  
  // Position tooltip near cursor but not overlapping
  positionTooltip(tooltip, position);
  tooltip.classList.add('visible');
}

function hideTooltip() {
  const tooltip = document.getElementById('tooltip');
  tooltip.classList.remove('visible');
}
```

#### Edge Tooltip Content

```javascript
function showEdgeTooltip(edge, position) {
  const data = edge.data();
  const sourceLabel = edge.source().data('label');
  const targetLabel = edge.target().data('label');
  
  const tooltip = document.getElementById('tooltip');
  tooltip.innerHTML = `
    <div class="tooltip-header">
      <span class="tooltip-relation">${formatRelation(data.rel)}</span>
    </div>
    <div class="tooltip-body">
      <div class="tooltip-row relationship">
        <span class="tooltip-entity">${sourceLabel}</span>
        <span class="tooltip-arrow">→</span>
        <span class="tooltip-entity">${targetLabel}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-key">Kind:</span>
        <span class="tooltip-value kind-${data.kind}">${capitalize(data.kind)}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-key">Confidence:</span>
        <span class="tooltip-value">${(data.confidence * 100).toFixed(0)}%</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-key">Sources:</span>
        <span class="tooltip-value">${data.evidenceCount || 1} document(s)</span>
      </div>
    </div>
    <div class="tooltip-footer">
      Click for full evidence
    </div>
  `;
  
  positionTooltip(tooltip, position);
  tooltip.classList.add('visible');
}

function formatRelation(rel) {
  // Convert SNAKE_CASE to Title Case
  return rel.split('_').map(word => 
    word.charAt(0) + word.slice(1).toLowerCase()
  ).join(' ');
}
```

#### Tooltip Styling

```css
#tooltip {
  position: absolute;
  z-index: 10000;
  background: white;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 12px;
  min-width: 200px;
  max-width: 300px;
  font-size: 13px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

#tooltip.visible {
  opacity: 1;
}

.tooltip-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #E5E7EB;
}

.tooltip-type {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 4px;
  color: white;
}

.tooltip-type.type-org { background: #4A90D9; }
.tooltip-type.type-person { background: #50B4A8; }
.tooltip-type.type-model { background: #7C3AED; }
/* ... other types ... */

.tooltip-label {
  font-weight: 600;
  color: #1F2937;
}

.tooltip-row {
  display: flex;
  justify-content: space-between;
  margin: 4px 0;
}

.tooltip-key {
  color: #6B7280;
}

.tooltip-value {
  font-weight: 500;
  color: #1F2937;
}

.tooltip-badge {
  margin-top: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.tooltip-badge.trending {
  background: #FEF3C7;
  color: #D97706;
}

.tooltip-badge.new {
  background: #D1FAE5;
  color: #059669;
}

.tooltip-footer {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #E5E7EB;
  font-size: 11px;
  color: #9CA3AF;
}
```

---

### Search and Filter

#### Search Box (Always Visible)

Position at top of UI, always accessible:

```html
<div id="search-container">
  <input 
    type="text" 
    id="search-input" 
    placeholder="Search nodes..."
    autocomplete="off"
  />
  <span id="search-results-count"></span>
  <button id="search-clear" title="Clear search">×</button>
</div>
```

#### Search Implementation

```javascript
let searchTimeout;

document.getElementById('search-input').addEventListener('input', function(e) {
  clearTimeout(searchTimeout);
  
  // Debounce search
  searchTimeout = setTimeout(() => {
    performSearch(e.target.value);
  }, 150);
});

function performSearch(query) {
  const trimmedQuery = query.trim().toLowerCase();
  
  if (!trimmedQuery) {
    // Clear search
    cy.elements().removeClass('search-match').removeClass('dimmed');
    document.getElementById('search-results-count').textContent = '';
    return;
  }
  
  // Find matching nodes
  const matches = cy.nodes().filter(node => {
    const label = (node.data('label') || '').toLowerCase();
    const aliases = (node.data('aliases') || []).map(a => a.toLowerCase());
    const type = (node.data('type') || '').toLowerCase();
    
    return label.includes(trimmedQuery) ||
           aliases.some(alias => alias.includes(trimmedQuery)) ||
           type.includes(trimmedQuery);
  });
  
  // Update UI
  cy.elements().removeClass('search-match');
  
  if (matches.length > 0) {
    // Highlight matches
    matches.addClass('search-match');
    
    // Include edges between matches
    const matchEdges = matches.edgesWith(matches);
    matchEdges.addClass('search-match');
    
    // Dim non-matches
    cy.elements().not('.search-match').addClass('dimmed');
    
    // Show count
    document.getElementById('search-results-count').textContent = 
      `${matches.length} node${matches.length === 1 ? '' : 's'}`;
  } else {
    cy.elements().addClass('dimmed');
    document.getElementById('search-results-count').textContent = 'No matches';
  }
}

// Enter key: zoom to fit results
document.getElementById('search-input').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') {
    const matches = cy.nodes('.search-match');
    if (matches.length > 0) {
      cy.animate({
        fit: {
          eles: matches,
          padding: 50
        },
        duration: 300
      });
    }
  }
  
  // Escape: clear search
  if (e.key === 'Escape') {
    this.value = '';
    performSearch('');
    this.blur();
  }
});
```

#### Filter Panel

Collapsible sidebar with comprehensive filtering:

```html
<aside id="filter-panel" class="panel collapsed">
  <button id="filter-toggle" class="panel-toggle">
    <span class="icon">⚙</span>
    <span class="label">Filters</span>
  </button>
  
  <div class="panel-content">
    <!-- Date Range -->
    <section class="filter-section">
      <h3>Date Range</h3>
      <div class="date-range-inputs">
        <input type="date" id="filter-date-start" />
        <span>to</span>
        <input type="date" id="filter-date-end" />
      </div>
      <input 
        type="range" 
        id="filter-date-slider" 
        min="0" 
        max="100"
        class="date-slider"
      />
      <div class="date-presets">
        <button data-days="7">7d</button>
        <button data-days="30">30d</button>
        <button data-days="90">90d</button>
        <button data-days="all">All</button>
      </div>
    </section>
    
    <!-- Entity Types -->
    <section class="filter-section">
      <h3>Entity Types</h3>
      <div class="checkbox-grid">
        <label><input type="checkbox" data-type="Org" checked /> Org</label>
        <label><input type="checkbox" data-type="Person" checked /> Person</label>
        <label><input type="checkbox" data-type="Model" checked /> Model</label>
        <label><input type="checkbox" data-type="Tool" checked /> Tool</label>
        <label><input type="checkbox" data-type="Dataset" checked /> Dataset</label>
        <label><input type="checkbox" data-type="Benchmark" checked /> Benchmark</label>
        <label><input type="checkbox" data-type="Paper" checked /> Paper</label>
        <label><input type="checkbox" data-type="Repo" checked /> Repo</label>
        <label><input type="checkbox" data-type="Tech" checked /> Tech</label>
        <label><input type="checkbox" data-type="Topic" checked /> Topic</label>
        <label><input type="checkbox" data-type="Document" /> Document</label>
        <label><input type="checkbox" data-type="Event" checked /> Event</label>
        <label><input type="checkbox" data-type="Location" checked /> Location</label>
        <label><input type="checkbox" data-type="Other" checked /> Other</label>
      </div>
      <div class="type-actions">
        <button id="select-all-types">All</button>
        <button id="select-no-types">None</button>
      </div>
    </section>
    
    <!-- Relationship Kind -->
    <section class="filter-section">
      <h3>Relationship Kind</h3>
      <label><input type="checkbox" data-kind="asserted" checked /> Asserted</label>
      <label><input type="checkbox" data-kind="inferred" checked /> Inferred</label>
      <label><input type="checkbox" data-kind="hypothesis" /> Hypothesis</label>
    </section>
    
    <!-- Confidence Threshold -->
    <section class="filter-section">
      <h3>Minimum Confidence</h3>
      <input 
        type="range" 
        id="filter-confidence" 
        min="0" 
        max="100" 
        value="30"
      />
      <span id="confidence-value">30%</span>
    </section>
    
    <!-- View Presets -->
    <section class="filter-section">
      <h3>Show</h3>
      <label>
        <input type="radio" name="view-preset" value="all" />
        All nodes
      </label>
      <label>
        <input type="radio" name="view-preset" value="trending" checked />
        Trending only
      </label>
      <label>
        <input type="radio" name="view-preset" value="new" />
        New (last 7 days)
      </label>
    </section>
    
    <!-- Actions -->
    <section class="filter-actions">
      <button id="apply-filters" class="primary">Apply Filters</button>
      <button id="reset-filters">Reset All</button>
    </section>
  </div>
</aside>
```

#### Filter Implementation

```javascript
class GraphFilter {
  constructor(cy) {
    this.cy = cy;
    this.filters = {
      dateStart: null,
      dateEnd: null,
      types: new Set([
        'Org', 'Person', 'Model', 'Tool', 'Dataset', 'Benchmark',
        'Paper', 'Repo', 'Tech', 'Topic', 'Event', 'Location', 'Other'
      ]),
      kinds: new Set(['asserted', 'inferred']),
      minConfidence: 0.3,
      viewPreset: 'trending'
    };
  }
  
  setDateRange(start, end) {
    this.filters.dateStart = start;
    this.filters.dateEnd = end;
  }
  
  toggleType(type, enabled) {
    if (enabled) {
      this.filters.types.add(type);
    } else {
      this.filters.types.delete(type);
    }
  }
  
  toggleKind(kind, enabled) {
    if (enabled) {
      this.filters.kinds.add(kind);
    } else {
      this.filters.kinds.delete(kind);
    }
  }
  
  setMinConfidence(value) {
    this.filters.minConfidence = value;
  }
  
  setViewPreset(preset) {
    this.filters.viewPreset = preset;
  }
  
  apply() {
    const { cy, filters } = this;
    
    // Start with all elements visible
    cy.elements().removeClass('filtered-out');
    
    // Filter nodes
    cy.nodes().forEach(node => {
      let visible = true;
      
      // Type filter
      if (!filters.types.has(node.data('type'))) {
        visible = false;
      }
      
      // Date filter (by lastSeen)
      if (visible && filters.dateStart) {
        const lastSeen = node.data('lastSeen');
        if (lastSeen && lastSeen < filters.dateStart) {
          visible = false;
        }
      }
      
      if (visible && filters.dateEnd) {
        const firstSeen = node.data('firstSeen');
        if (firstSeen && firstSeen > filters.dateEnd) {
          visible = false;
        }
      }
      
      // View preset filters
      if (visible && filters.viewPreset === 'trending') {
        const velocity = node.data('velocity') || 0;
        if (velocity < 0.1) {
          visible = false;
        }
      }
      
      if (visible && filters.viewPreset === 'new') {
        const firstSeen = node.data('firstSeen');
        if (!isNewNode(firstSeen)) {
          visible = false;
        }
      }
      
      if (!visible) {
        node.addClass('filtered-out');
      }
    });
    
    // Filter edges
    cy.edges().forEach(edge => {
      let visible = true;
      
      // Kind filter
      if (!filters.kinds.has(edge.data('kind'))) {
        visible = false;
      }
      
      // Confidence filter
      const confidence = edge.data('confidence') || 0;
      if (confidence < filters.minConfidence) {
        visible = false;
      }
      
      // Hide edges connected to hidden nodes
      if (edge.source().hasClass('filtered-out') || 
          edge.target().hasClass('filtered-out')) {
        visible = false;
      }
      
      if (!visible) {
        edge.addClass('filtered-out');
      }
    });
    
    // Update visibility
    cy.elements('.filtered-out').hide();
    cy.elements().not('.filtered-out').show();
    
    // Update label visibility for remaining nodes
    updateLabelVisibility(cy);
    
    // Emit event for UI updates
    this.cy.emit('filtersApplied', this.getActiveFilterCount());
  }
  
  reset() {
    this.filters = {
      dateStart: null,
      dateEnd: null,
      types: new Set([
        'Org', 'Person', 'Model', 'Tool', 'Dataset', 'Benchmark',
        'Paper', 'Repo', 'Tech', 'Topic', 'Event', 'Location', 'Other'
      ]),
      kinds: new Set(['asserted', 'inferred']),
      minConfidence: 0.3,
      viewPreset: 'trending'
    };
    this.apply();
  }
  
  getActiveFilterCount() {
    let count = 0;
    if (this.filters.dateStart || this.filters.dateEnd) count++;
    if (this.filters.types.size < 14) count++;
    if (this.filters.kinds.size < 3) count++;
    if (this.filters.minConfidence > 0) count++;
    if (this.filters.viewPreset !== 'all') count++;
    return count;
  }
}
```

#### Filter Panel Styles

```css
.filtered-out {
  display: none !important;
}

#filter-panel {
  position: absolute;
  right: 0;
  top: 60px;  /* Below toolbar */
  bottom: 0;
  width: 280px;
  background: white;
  border-left: 1px solid #E5E7EB;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.05);
  transition: transform 0.3s ease;
  z-index: 100;
  overflow-y: auto;
}

#filter-panel.collapsed {
  transform: translateX(240px);
}

#filter-panel.collapsed .panel-content {
  opacity: 0;
  pointer-events: none;
}

.panel-toggle {
  position: absolute;
  left: -40px;
  top: 10px;
  width: 40px;
  height: 40px;
  background: white;
  border: 1px solid #E5E7EB;
  border-right: none;
  border-radius: 8px 0 0 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.panel-content {
  padding: 16px;
  transition: opacity 0.2s ease;
}

.filter-section {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #F3F4F6;
}

.filter-section h3 {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  color: #6B7280;
  margin-bottom: 12px;
}

.checkbox-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.checkbox-grid label {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.date-presets {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.date-presets button {
  flex: 1;
  padding: 6px;
  font-size: 12px;
  border: 1px solid #E5E7EB;
  background: white;
  border-radius: 4px;
  cursor: pointer;
}

.date-presets button:hover {
  background: #F9FAFB;
}

.date-presets button.active {
  background: #3B82F6;
  color: white;
  border-color: #3B82F6;
}

.filter-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.filter-actions button {
  flex: 1;
  padding: 10px;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
}

.filter-actions button.primary {
  background: #3B82F6;
  color: white;
  border: none;
}

.filter-actions button:not(.primary) {
  background: white;
  border: 1px solid #E5E7EB;
}
```

---

### Progressive Disclosure

#### Level 1: Overview (Default State)

The initial view shows a high-level summary optimized for trend detection:

```javascript
function showOverview(cy) {
  // Load trending view by default
  loadGraphView('trending');
  
  // Apply default filters
  const filter = new GraphFilter(cy);
  filter.setViewPreset('trending');
  filter.apply();
  
  // Run layout
  runLayout(cy, 'preset');  // V2: use preset if positions available
  
  // Fit to view
  cy.fit(50);
  
  // Update label visibility
  updateLabelVisibility(cy);
}
```

#### Level 2: Explore (Click to Expand)

When user clicks a node, reveal its neighborhood:

```javascript
function expandNeighbors(node, depth = 1) {
  const cy = node.cy();
  
  // Get neighbors up to specified depth
  let toExpand = node;
  for (let i = 0; i < depth; i++) {
    toExpand = toExpand.closedNeighborhood();
  }
  
  // If neighbors are hidden (filtered out), show them
  toExpand.removeClass('filtered-out').show();
  
  // Animate expansion
  const originalPositions = {};
  toExpand.nodes().forEach(n => {
    originalPositions[n.id()] = n.position();
    
    // New nodes start at the clicked node's position
    if (!n.visible() || n.hasClass('just-expanded')) {
      n.position(node.position());
      n.addClass('just-expanded');
    }
  });
  
  // Run local layout for just the expanded nodes
  toExpand.layout({
    name: 'concentric',
    concentric: function(n) {
      return n.id() === node.id() ? 10 : 1;
    },
    minNodeSpacing: 50,
    animate: true,
    animationDuration: 300
  }).run();
  
  // Update label visibility
  updateLabelVisibility(cy);
  
  // Fit to show expanded neighborhood
  cy.animate({
    fit: {
      eles: toExpand,
      padding: 50
    },
    duration: 300
  });
}
```

#### Level 3: Deep Dive (Detail Panel)

Full node metadata in a side panel:

```html
<aside id="detail-panel" class="panel hidden">
  <button class="panel-close">×</button>
  
  <div id="detail-content">
    <!-- Populated dynamically -->
  </div>
</aside>
```

```javascript
function openNodeDetailPanel(node) {
  const data = node.data();
  const panel = document.getElementById('detail-panel');
  const content = document.getElementById('detail-content');
  
  content.innerHTML = `
    <header class="detail-header">
      <span class="detail-type type-${data.type.toLowerCase()}">${data.type}</span>
      <h2 class="detail-title">${escapeHtml(data.label)}</h2>
      ${data.aliases && data.aliases.length > 0 ? `
        <div class="detail-aliases">
          Also known as: ${data.aliases.map(a => escapeHtml(a)).join(', ')}
        </div>
      ` : ''}
    </header>
    
    <section class="detail-section">
      <h3>Timeline</h3>
      <div class="detail-timeline">
        <div class="timeline-item">
          <span class="timeline-label">First seen</span>
          <span class="timeline-value">${formatDate(data.firstSeen)}</span>
          <span class="timeline-relative">${daysAgo(data.firstSeen)}</span>
        </div>
        <div class="timeline-item">
          <span class="timeline-label">Last seen</span>
          <span class="timeline-value">${formatDate(data.lastSeen)}</span>
          <span class="timeline-relative">${daysAgo(data.lastSeen)}</span>
        </div>
      </div>
    </section>
    
    <section class="detail-section">
      <h3>Activity</h3>
      <div class="detail-stats">
        <div class="stat">
          <span class="stat-value">${data.mentionCount7d || 0}</span>
          <span class="stat-label">Mentions (7d)</span>
        </div>
        <div class="stat">
          <span class="stat-value">${data.mentionCount30d || 0}</span>
          <span class="stat-label">Mentions (30d)</span>
        </div>
        <div class="stat">
          <span class="stat-value">${node.degree()}</span>
          <span class="stat-label">Connections</span>
        </div>
        <div class="stat ${data.velocity > 0.5 ? 'trending' : ''}">
          <span class="stat-value">${formatVelocity(data.velocity)}</span>
          <span class="stat-label">Velocity</span>
        </div>
      </div>
    </section>
    
    <section class="detail-section">
      <h3>Relationships (${node.connectedEdges().length})</h3>
      <div class="detail-relationships">
        ${renderRelationshipList(node)}
      </div>
    </section>
    
    <section class="detail-section">
      <h3>Source Documents</h3>
      <div class="detail-documents">
        ${renderDocumentList(node)}
      </div>
    </section>
    
    <footer class="detail-footer">
      <button class="btn" onclick="expandNeighbors(cy.$('#${data.id}'))">
        Expand neighbors
      </button>
      <button class="btn" onclick="zoomToNode(cy.$('#${data.id}'))">
        Center view
      </button>
    </footer>
  `;
  
  panel.classList.remove('hidden');
}

function renderRelationshipList(node) {
  const edges = node.connectedEdges();
  
  // Group by relationship type
  const grouped = {};
  edges.forEach(edge => {
    const rel = edge.data('rel');
    if (!grouped[rel]) grouped[rel] = [];
    grouped[rel].push(edge);
  });
  
  let html = '';
  for (const [rel, relEdges] of Object.entries(grouped)) {
    html += `
      <div class="relationship-group">
        <div class="relationship-type">${formatRelation(rel)}</div>
        <ul class="relationship-list">
          ${relEdges.slice(0, 5).map(edge => {
            const other = edge.source().id() === node.id() 
              ? edge.target() 
              : edge.source();
            const direction = edge.source().id() === node.id() ? '→' : '←';
            return `
              <li class="relationship-item" data-edge-id="${edge.id()}">
                <span class="rel-direction">${direction}</span>
                <span class="rel-target" onclick="selectNode('${other.id()}')">${other.data('label')}</span>
                <span class="rel-confidence">${(edge.data('confidence') * 100).toFixed(0)}%</span>
                <span class="rel-kind kind-${edge.data('kind')}">${edge.data('kind')}</span>
              </li>
            `;
          }).join('')}
          ${relEdges.length > 5 ? `
            <li class="relationship-more">
              +${relEdges.length - 5} more
            </li>
          ` : ''}
        </ul>
      </div>
    `;
  }
  
  return html;
}
```

#### Level 4: Evidence Panel (Edge Detail)

Full provenance for a relationship:

```javascript
function openEvidencePanel(edge) {
  const data = edge.data();
  const sourceNode = edge.source();
  const targetNode = edge.target();
  
  const panel = document.getElementById('evidence-panel');
  const content = document.getElementById('evidence-content');
  
  // Fetch full evidence (may need async call if not embedded in edge data)
  const evidence = data.evidence || [];
  
  content.innerHTML = `
    <header class="evidence-header">
      <div class="evidence-relationship">
        <span class="evidence-entity">${sourceNode.data('label')}</span>
        <span class="evidence-rel">${formatRelation(data.rel)}</span>
        <span class="evidence-entity">${targetNode.data('label')}</span>
      </div>
      <div class="evidence-meta">
        <span class="evidence-kind kind-${data.kind}">${capitalize(data.kind)}</span>
        <span class="evidence-confidence">
          ${(data.confidence * 100).toFixed(0)}% confidence
        </span>
        <span class="evidence-date">
          First asserted: ${formatDate(data.firstSeen)}
        </span>
      </div>
    </header>
    
    <section class="evidence-section">
      <h3>Evidence (${evidence.length} source${evidence.length === 1 ? '' : 's'})</h3>
      <ul class="evidence-list">
        ${evidence.map((ev, idx) => `
          <li class="evidence-item">
            <div class="evidence-source">
              <span class="evidence-icon">📄</span>
              <span class="evidence-title">${escapeHtml(ev.title || 'Untitled')}</span>
            </div>
            <div class="evidence-pub">
              ${ev.source || 'Unknown source'} · ${formatDate(ev.published)}
            </div>
            <blockquote class="evidence-snippet">
              "${escapeHtml(ev.snippet)}"
            </blockquote>
            <a href="${ev.url}" target="_blank" class="evidence-link">
              View document →
            </a>
          </li>
        `).join('')}
      </ul>
      ${evidence.length === 0 ? `
        <p class="evidence-empty">
          No evidence snippets available for this relationship.
          This may be an inferred or hypothesis edge.
        </p>
      ` : ''}
    </section>
    
    <footer class="evidence-footer">
      <button class="btn" onclick="selectNode('${sourceNode.id()}')">
        View ${sourceNode.data('label')}
      </button>
      <button class="btn" onclick="selectNode('${targetNode.id()}')">
        View ${targetNode.data('label')}
      </button>
    </footer>
  `;
  
  panel.classList.remove('hidden');
}
```

---

### Layout Strategy

#### V1: Force-Directed on Load

For V1, compute layout on each page load using a force-directed algorithm:

```javascript
// V1 Layout Configuration
const V1_LAYOUT_OPTIONS = {
  name: 'fcose',  // Fast compound spring embedder
  
  // Animation
  animate: true,
  animationDuration: 500,
  animationEasing: 'ease-out',
  
  // Layout quality
  quality: 'default',  // 'draft', 'default', or 'proof'
  randomize: true,
  
  // Node repulsion
  nodeRepulsion: 4500,
  idealEdgeLength: 100,
  edgeElasticity: 0.45,
  nestingFactor: 0.1,
  
  // Gravity (pulls disconnected components together)
  gravity: 0.25,
  gravityRange: 3.8,
  
  // Iteration limits
  numIter: 2500,
  
  // Tiling (for disconnected components)
  tile: true,
  tilingPaddingVertical: 30,
  tilingPaddingHorizontal: 30,
  
  // Fit after layout
  fit: true,
  padding: 30
};

function runForceDirectedLayout(cy) {
  showLayoutProgress(true);
  
  const layout = cy.layout(V1_LAYOUT_OPTIONS);
  
  layout.on('layoutstop', function() {
    showLayoutProgress(false);
    updateLabelVisibility(cy);
  });
  
  layout.run();
}
```

#### V2: Preset Default with Options

For V2, stored positions enable instant, stable rendering:

```javascript
// V2 Layout Modes
const LayoutMode = {
  PRESET: 'preset',
  FORCE: 'force',
  HYBRID: 'hybrid'
};

function runLayout(cy, mode = LayoutMode.PRESET) {
  switch (mode) {
    case LayoutMode.PRESET:
      runPresetLayout(cy);
      break;
    case LayoutMode.FORCE:
      runForceDirectedLayout(cy);
      break;
    case LayoutMode.HYBRID:
      runHybridLayout(cy);
      break;
  }
}

// Preset: Use stored positions (instant)
function runPresetLayout(cy) {
  const hasPositions = cy.nodes().every(n => n.position().x !== undefined);
  
  if (!hasPositions) {
    console.warn('No stored positions; falling back to force-directed');
    runForceDirectedLayout(cy);
    return;
  }
  
  cy.layout({
    name: 'preset',
    fit: true,
    padding: 30
  }).run();
  
  updateLabelVisibility(cy);
}

// Hybrid: Pin existing nodes, simulate new ones
function runHybridLayout(cy) {
  // Identify new nodes (no stored position or marked as new)
  const newNodes = cy.nodes().filter(n => {
    return !n.data('hasStoredPosition') || n.hasClass('just-added');
  });
  
  const existingNodes = cy.nodes().not(newNodes);
  
  // Lock existing nodes
  existingNodes.lock();
  
  // Place new nodes near their connected neighbors
  newNodes.forEach(node => {
    const neighbors = node.neighborhood('node');
    if (neighbors.length > 0) {
      // Average position of neighbors
      const avgX = neighbors.reduce((sum, n) => sum + n.position('x'), 0) / neighbors.length;
      const avgY = neighbors.reduce((sum, n) => sum + n.position('y'), 0) / neighbors.length;
      
      // Add some randomness to avoid overlap
      node.position({
        x: avgX + (Math.random() - 0.5) * 100,
        y: avgY + (Math.random() - 0.5) * 100
      });
    }
  });
  
  // Run constrained force-directed for new nodes only
  cy.layout({
    name: 'fcose',
    animate: true,
    animationDuration: 300,
    
    // Only affect new nodes
    fixedNodeConstraint: existingNodes.map(n => ({
      nodeId: n.id(),
      position: n.position()
    })),
    
    // Lighter simulation
    numIter: 500,
    nodeRepulsion: 3000,
    
    fit: false  // Don't change view
  }).run().on('layoutstop', () => {
    existingNodes.unlock();
    newNodes.removeClass('just-added');
    updateLabelVisibility(cy);
  });
}
```

#### Position Storage Format

When positions are saved (V2), the node data structure includes:

```json
{
  "data": {
    "id": "org:openai",
    "label": "OpenAI",
    "type": "Org",
    "hasStoredPosition": true
  },
  "position": {
    "x": 342.7,
    "y": -156.2
  }
}
```

The coordinate system is arbitrary (not pixels). The client scales to fit the viewport.

#### Daily Export Workflow (V2)

When generating daily exports, the backend should:

1. Load previous day's positions into a lookup table
2. For each node in today's graph:
   - If node existed yesterday: use previous position
   - If new node: leave position undefined (client will compute via hybrid layout)
3. Include `hasStoredPosition: true` only for nodes with carried-over positions

```python
# Pseudocode for backend position handling
def generate_export(today_graph, yesterday_positions):
    elements = {"nodes": [], "edges": []}
    
    for node in today_graph.nodes:
        node_data = {
            "data": {
                "id": node.id,
                "label": node.label,
                "type": node.type,
                # ... other fields
            }
        }
        
        # Check for existing position
        if node.id in yesterday_positions:
            node_data["position"] = yesterday_positions[node.id]
            node_data["data"]["hasStoredPosition"] = True
        else:
            # New node - no position
            node_data["data"]["hasStoredPosition"] = False
        
        elements["nodes"].append(node_data)
    
    return elements
```

---

### Temporal Features

#### V1: Static Temporal Filtering

V1 provides temporal context through filtering and visual encoding:

**Date Range Filter:**
- Implemented in Filter Panel (see Search and Filter section)
- Filters based on `firstSeen` and `lastSeen`
- Preset buttons: 7d, 30d, 90d, All

**Recency-Based Visual Encoding:**
- Node opacity/saturation based on `lastSeen` (see Node Visual Encoding)
- Edge color highlighting for new edges (see Edge Visual Encoding)

**"What's New" Toggle:**

```javascript
// Quick toggle for highlighting new elements
function toggleNewHighlight(enabled) {
  if (enabled) {
    // Highlight new nodes
    cy.nodes().forEach(node => {
      if (isNewNode(node.data('firstSeen'))) {
        node.addClass('new');
      }
    });
    
    // Highlight new edges  
    cy.edges().forEach(edge => {
      if (isNewEdge(edge)) {
        edge.addClass('new');
      }
    });
  } else {
    cy.elements().removeClass('new');
  }
}

function isNewNode(firstSeen) {
  if (!firstSeen) return false;
  return daysBetween(firstSeen, today()) <= 7;
}

function isNewEdge(edge) {
  const firstSeen = edge.data('firstSeen');
  if (!firstSeen) return false;
  return daysBetween(firstSeen, today()) <= 7;
}
```

**Temporal Information in Tooltips:**
- Node tooltip shows `firstSeen`, `lastSeen`, and days ago
- Edge tooltip shows first assertion date

#### V2: Time-Lapse Animation

Full animation support for watching graph evolution over time.

**Prerequisites:**
- Stored positions (preset layout)
- Cumulative daily exports (or reconstructable history)

**UI Controls:**

```html
<div id="timeline-controls" class="hidden">
  <button id="timeline-start" title="Jump to start">⏮</button>
  <button id="timeline-back" title="Previous day">◀</button>
  <button id="timeline-play" title="Play">▶</button>
  <button id="timeline-forward" title="Next day">▶</button>
  <button id="timeline-end" title="Jump to end">⏭</button>
  
  <input 
    type="range" 
    id="timeline-scrubber"
    min="0" 
    max="100"
  />
  
  <span id="timeline-date">2026-01-24</span>
  
  <div class="timeline-options">
    <label>
      Speed:
      <select id="timeline-speed">
        <option value="2000">0.5x</option>
        <option value="1000" selected>1x</option>
        <option value="500">2x</option>
        <option value="250">4x</option>
      </select>
    </label>
    <label>
      <input type="checkbox" id="timeline-labels" />
      Show labels
    </label>
    <label>
      <input type="checkbox" id="timeline-trails" />
      Trails
    </label>
  </div>
</div>
```

**Animation Implementation:**

```javascript
class TimelinePlayer {
  constructor(cy, snapshots) {
    this.cy = cy;
    this.snapshots = snapshots;  // Array of { date, elements }
    this.currentIndex = snapshots.length - 1;
    this.isPlaying = false;
    this.speed = 1000;  // ms per frame
    this.playInterval = null;
  }
  
  loadSnapshot(index) {
    if (index < 0 || index >= this.snapshots.length) return;
    
    const snapshot = this.snapshots[index];
    const cy = this.cy;
    
    // Get current elements for comparison
    const currentIds = new Set(cy.nodes().map(n => n.id()));
    const newIds = new Set(snapshot.elements.nodes.map(n => n.data.id));
    
    // Elements to add (new in this snapshot)
    const toAdd = snapshot.elements.nodes.filter(n => !currentIds.has(n.data.id));
    
    // Elements to remove (not in this snapshot)
    const toRemove = cy.nodes().filter(n => !newIds.has(n.id()));
    
    // Animate removals (fade out)
    toRemove.animate({
      style: { opacity: 0 },
      duration: this.speed * 0.3
    }).promise().then(() => {
      toRemove.remove();
    });
    
    // Add new elements (will fade in)
    if (toAdd.length > 0) {
      const added = cy.add(toAdd);
      added.style('opacity', 0);
      added.animate({
        style: { opacity: 1 },
        duration: this.speed * 0.3
      });
    }
    
    // Animate position changes for existing nodes
    cy.nodes().forEach(node => {
      const snapshotNode = snapshot.elements.nodes.find(n => n.data.id === node.id());
      if (snapshotNode && snapshotNode.position) {
        node.animate({
          position: snapshotNode.position,
          duration: this.speed * 0.5,
          easing: 'ease-in-out'
        });
      }
    });
    
    // Update size/color based on snapshot data
    cy.nodes().forEach(node => {
      const snapshotNode = snapshot.elements.nodes.find(n => n.data.id === node.id());
      if (snapshotNode) {
        // Update data (triggers style recalculation)
        node.data(snapshotNode.data);
      }
    });
    
    // Similarly handle edges...
    
    this.currentIndex = index;
    this.updateUI();
  }
  
  play() {
    if (this.isPlaying) return;
    
    this.isPlaying = true;
    document.getElementById('timeline-play').textContent = '⏸';
    
    this.playInterval = setInterval(() => {
      if (this.currentIndex >= this.snapshots.length - 1) {
        this.pause();
        return;
      }
      this.loadSnapshot(this.currentIndex + 1);
    }, this.speed);
  }
  
  pause() {
    this.isPlaying = false;
    document.getElementById('timeline-play').textContent = '▶';
    
    if (this.playInterval) {
      clearInterval(this.playInterval);
      this.playInterval = null;
    }
  }
  
  toggle() {
    if (this.isPlaying) {
      this.pause();
    } else {
      this.play();
    }
  }
  
  jumpTo(index) {
    this.pause();
    this.loadSnapshot(index);
  }
  
  setSpeed(ms) {
    this.speed = ms;
    if (this.isPlaying) {
      this.pause();
      this.play();
    }
  }
  
  updateUI() {
    const date = this.snapshots[this.currentIndex].date;
    document.getElementById('timeline-date').textContent = date;
    
    const scrubber = document.getElementById('timeline-scrubber');
    scrubber.value = (this.currentIndex / (this.snapshots.length - 1)) * 100;
  }
}
```

---

### Toolbar and Global Controls

#### Toolbar Layout

```html
<header id="toolbar">
  <div class="toolbar-left">
    <h1 class="app-title">AI Trend Graph</h1>
    
    <div class="toolbar-group">
      <label>View:</label>
      <select id="view-selector">
        <option value="trending">Trending</option>
        <option value="claims">Claims</option>
        <option value="mentions">Mentions</option>
        <option value="dependencies">Dependencies</option>
      </select>
    </div>
    
    <div class="toolbar-group">
      <label>Date:</label>
      <select id="date-selector">
        <!-- Populated dynamically -->
      </select>
    </div>
  </div>
  
  <div class="toolbar-center">
    <div id="search-container">
      <input type="text" id="search-input" placeholder="Search nodes..." />
      <span id="search-results-count"></span>
    </div>
  </div>
  
  <div class="toolbar-right">
    <button id="btn-zoom-in" title="Zoom in">+</button>
    <button id="btn-zoom-out" title="Zoom out">−</button>
    <button id="btn-fit" title="Fit to view">⊡</button>
    <button id="btn-layout" title="Re-run layout">↻</button>
    <button id="btn-fullscreen" title="Fullscreen">⛶</button>
  </div>
</header>
```

#### Toolbar Implementation

```javascript
// View selector
document.getElementById('view-selector').addEventListener('change', async (e) => {
  const view = e.target.value;
  const date = document.getElementById('date-selector').value;
  await loadGraphView(view, date);
});

// Date selector
document.getElementById('date-selector').addEventListener('change', async (e) => {
  const date = e.target.value;
  const view = document.getElementById('view-selector').value;
  await loadGraphView(view, date);
});

// Zoom controls
document.getElementById('btn-zoom-in').addEventListener('click', () => {
  cy.zoom({
    level: cy.zoom() * 1.2,
    renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 }
  });
});

document.getElementById('btn-zoom-out').addEventListener('click', () => {
  cy.zoom({
    level: cy.zoom() / 1.2,
    renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 }
  });
});

// Fit to view
document.getElementById('btn-fit').addEventListener('click', () => {
  cy.animate({
    fit: { padding: 30 },
    duration: 300
  });
});

// Re-run layout
document.getElementById('btn-layout').addEventListener('click', () => {
  runForceDirectedLayout(cy);
});

// Fullscreen
document.getElementById('btn-fullscreen').addEventListener('click', () => {
  const container = document.getElementById('app');
  if (document.fullscreenElement) {
    document.exitFullscreen();
  } else {
    container.requestFullscreen();
  }
});
```

---

### Performance Guidelines

#### Client-Side Rendering Thresholds

| Node Count | Edge Count | Recommendation |
|------------|------------|----------------|
| < 500 | < 1,000 | Render all; smooth experience |
| 500–1,000 | 1,000–2,000 | Enable text-on-viewport optimization |
| 1,000–2,000 | 2,000–5,000 | Warn user; suggest filtering |
| 2,000–5,000 | 5,000–10,000 | Auto-filter; load full on demand |
| > 5,000 | > 10,000 | Require server-side filtering |

#### Cytoscape Performance Optimizations

```javascript
// Performance settings for large graphs
const PERFORMANCE_OPTIONS = {
  // Texture on viewport: render to canvas when panning/zooming
  textureOnViewport: true,
  
  // Disable expensive operations during interaction
  hideEdgesOnViewport: false,  // Set to true for very large graphs
  hideLabelsOnViewport: true,
  
  // Reduce quality during motion
  motionBlur: false,
  
  // Wheel sensitivity (lower = less redraws)
  wheelSensitivity: 0.1,
  
  // Minimum zoom (prevents over-zoom and high node density)
  minZoom: 0.1,
  maxZoom: 3
};

// Apply when graph is large
function applyPerformanceMode(cy) {
  const nodeCount = cy.nodes().length;
  
  if (nodeCount > 1000) {
    cy.style()
      .selector('edge')
      .style({
        'curve-style': 'haystack'  // Faster than bezier
      })
      .update();
  }
  
  if (nodeCount > 2000) {
    // Disable animations
    cy.style()
      .selector('*')
      .style({
        'transition-property': 'none'
      })
      .update();
  }
}
```

#### Lazy Loading (V2)

For very large graphs, load details on demand:

```javascript
// Initial load: only node positions and minimal data
async function loadGraphSkeleton(view, date) {
  const response = await fetch(`/api/graphs/${date}/${view}/skeleton`);
  const skeleton = await response.json();
  
  // Skeleton contains: id, label, type, position, degree
  // Does NOT contain: aliases, evidence, full metadata
  
  cy.json({ elements: skeleton.elements });
}

// On node select: fetch full details
async function loadNodeDetails(nodeId) {
  const response = await fetch(`/api/nodes/${nodeId}`);
  const details = await response.json();
  
  // Update node data with full details
  cy.$(`#${nodeId}`).data(details);
  
  return details;
}

// On edge click: fetch evidence
async function loadEdgeEvidence(edgeId) {
  const response = await fetch(`/api/edges/${edgeId}/evidence`);
  const evidence = await response.json();
  
  return evidence;
}
```

#### JSON Compression

All graph exports should be gzipped. Modern browsers decompress automatically:

```python
# Backend: serve with gzip
import gzip

def export_graph(elements, output_path):
    json_str = json.dumps(elements, separators=(',', ':'))  # Compact
    
    with gzip.open(f"{output_path}.gz", 'wt', encoding='utf-8') as f:
        f.write(json_str)
```

```nginx
# Nginx: enable gzip
gzip on;
gzip_types application/json;
gzip_min_length 1000;
```

---

### Accessibility

#### Color Accessibility

- All color combinations must meet WCAG AA contrast ratio (4.5:1 for text, 3:1 for UI)
- Provide colorblind-safe palette option
- Never rely on color alone; use shape, pattern, or label

**Colorblind-Safe Alternative Palette:**

| Type | Default Color | Deuteranopia Safe |
|------|---------------|-------------------|
| Org | `#4A90D9` (Blue) | `#4A90D9` (Blue) |
| Person | `#50B4A8` (Teal) | `#D98200` (Orange) |
| Model | `#7C3AED` (Violet) | `#7C3AED` (Violet) |
| Dataset | `#F59E0B` (Orange) | `#0077BB` (Blue) |
| Paper | `#10B981` (Green) | `#EE7733` (Orange) |

```javascript
// Toggle colorblind mode
function setColorblindMode(enabled) {
  if (enabled) {
    cy.style()
      .selector('node[type = "Person"]')
      .style({ 'background-color': '#D98200' })
      .selector('node[type = "Dataset"]')
      .style({ 'background-color': '#0077BB' })
      .selector('node[type = "Paper"]')
      .style({ 'background-color': '#EE7733' })
      .update();
  } else {
    // Reset to default colors
    cy.style().resetToDefault().update();
  }
}
```

#### Keyboard Navigation

```javascript
// Enable keyboard navigation
document.addEventListener('keydown', (e) => {
  // Only when graph is focused
  if (document.activeElement !== cy.container()) return;
  
  const selected = cy.nodes(':selected');
  
  switch (e.key) {
    case 'Tab':
      e.preventDefault();
      // Move to next node
      const nodes = cy.nodes(':visible');
      const currentIndex = selected.length > 0 
        ? nodes.indexOf(selected[0]) 
        : -1;
      const nextIndex = (currentIndex + 1) % nodes.length;
      
      cy.nodes().unselect();
      nodes[nextIndex].select();
      centerOnNode(nodes[nextIndex]);
      break;
      
    case 'Enter':
      // Open detail panel for selected node
      if (selected.length > 0) {
        openNodeDetailPanel(selected[0]);
      }
      break;
      
    case 'Escape':
      // Close panels, clear selection
      closeAllPanels();
      cy.nodes().unselect();
      break;
      
    case '+':
    case '=':
      cy.zoom(cy.zoom() * 1.2);
      break;
      
    case '-':
      cy.zoom(cy.zoom() / 1.2);
      break;
      
    case '0':
      cy.fit(30);
      break;
      
    case 'ArrowUp':
    case 'ArrowDown':
    case 'ArrowLeft':
    case 'ArrowRight':
      e.preventDefault();
      // Navigate to nearest neighbor in direction
      if (selected.length > 0) {
        navigateToNeighbor(selected[0], e.key);
      }
      break;
  }
});

// Make container focusable
cy.container().setAttribute('tabindex', '0');
cy.container().setAttribute('role', 'application');
cy.container().setAttribute('aria-label', 'AI Trend Graph visualization');
```

#### Screen Reader Support

```javascript
// Announce selection changes
cy.on('select', 'node', function(event) {
  const node = event.target;
  const announcement = `Selected ${node.data('type')}: ${node.data('label')}. ` +
                       `${node.degree()} connections. ` +
                       `First seen ${formatDate(node.data('firstSeen'))}.`;
  
  announceToScreenReader(announcement);
});

function announceToScreenReader(text) {
  const announcer = document.getElementById('sr-announcer');
  announcer.textContent = text;
}
```

```html
<!-- Screen reader announcements -->
<div 
  id="sr-announcer" 
  aria-live="polite" 
  aria-atomic="true"
  class="sr-only"
></div>

<style>
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
```

#### Reduced Motion

```javascript
// Respect prefers-reduced-motion
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function animateIfAllowed(options) {
  if (prefersReducedMotion) {
    // Skip animation, apply immediately
    return Promise.resolve();
  }
  return cy.animate(options).promise();
}

// Use throughout:
animateIfAllowed({
  fit: { padding: 30 },
  duration: 300
});
```

---

### V1 vs V2 Feature Matrix

| Feature | V1 | V2 | Notes |
|---------|:--:|:--:|-------|
| **Layout** | | | |
| Force-directed on load | ✅ | ✅ | Optional in V2 |
| Preset layout | ❌ | ✅ | Default in V2 |
| Position storage | ❌ | ✅ | Enables stability |
| Hybrid layout ("Integrate new") | ❌ | ✅ | For daily updates |
| | | | |
| **Visualization** | | | |
| Velocity-based node sizing | ✅ | ✅ | |
| Type-based node coloring | ✅ | ✅ | |
| Recency opacity/saturation | ✅ | ✅ | |
| Confidence-based edge thickness | ✅ | ✅ | |
| Kind-based edge style | ✅ | ✅ | |
| Edge bundling | ❌ | ✅ | For dense graphs |
| | | | |
| **Interaction** | | | |
| Pan/zoom | ✅ | ✅ | |
| Click to select | ✅ | ✅ | |
| Hover to preview | ✅ | ✅ | |
| Context menu | ✅ | ✅ | |
| Node expansion | ❌ | ✅ | Load neighbors on demand |
| | | | |
| **Filtering** | | | |
| Date range filter | ✅ | ✅ | |
| Entity type filter | ✅ | ✅ | |
| Kind toggles | ✅ | ✅ | |
| Confidence threshold | ✅ | ✅ | |
| View presets (trending/new/all) | ✅ | ✅ | |
| | | | |
| **Search** | | | |
| Search by label/alias | ✅ | ✅ | |
| Search highlighting | ✅ | ✅ | |
| Zoom to results | ✅ | ✅ | |
| | | | |
| **Information Display** | | | |
| Node tooltips | ✅ | ✅ | |
| Edge tooltips | ✅ | ✅ | |
| Node detail panel | ✅ | ✅ | |
| Evidence panel | ✅ | ✅ | |
| | | | |
| **Temporal** | | | |
| Recency-based visual encoding | ✅ | ✅ | |
| "What's new" highlighting | ✅ | ✅ | |
| Time-lapse animation | ❌ | ✅ | |
| Timeline scrubber | ❌ | ✅ | |
| | | | |
| **Performance** | | | |
| Gzipped JSON | ✅ | ✅ | |
| Auto-filter large graphs | ✅ | ✅ | |
| Lazy loading details | ❌ | ✅ | |
| WebGL renderer | ❌ | ✅ | For 5k+ nodes |
| | | | |
| **Accessibility** | | | |
| Keyboard navigation | ✅ | ✅ | |
| Screen reader support | ✅ | ✅ | |
| Colorblind mode | ✅ | ✅ | |
| Reduced motion | ✅ | ✅ | |
| | | | |
| **Persistence** | | | |
| User preferences | ❌ | ✅ | localStorage |
| Saved views/filters | ❌ | ✅ | |

---

### File Structure (web/)

Recommended directory structure for the Cytoscape client:

```
web/
├── index.html              # Main HTML shell
├── css/
│   ├── main.css            # Core layout and components
│   ├── toolbar.css         # Toolbar styles
│   ├── panels.css          # Side panels (filter, detail, evidence)
│   ├── tooltips.css        # Tooltip styles
│   └── accessibility.css   # Screen reader, focus states
├── js/
│   ├── app.js              # Main application initialization
│   ├── graph.js            # Cytoscape setup and configuration
│   ├── styles.js           # Cytoscape visual styles
│   ├── layout.js           # Layout algorithms and positioning
│   ├── filter.js           # GraphFilter class
│   ├── search.js           # Search functionality
│   ├── panels.js           # Panel management (detail, evidence)
│   ├── tooltips.js         # Tooltip rendering
│   ├── timeline.js         # V2: TimelinePlayer class
│   ├── accessibility.js    # Keyboard nav, screen reader
│   └── utils.js            # Helper functions
├── assets/
│   └── icons/              # UI icons (SVG preferred)
└── lib/
    ├── cytoscape.min.js    # Cytoscape.js core
    ├── cytoscape-fcose.js  # Force-directed layout
    └── cytoscape-context-menus.js  # Right-click menus
```

---

### Dependencies

#### Required (V1)

| Library | Version | Purpose |
|---------|---------|---------|
| Cytoscape.js | ^3.28.0 | Core graph visualization |
| cytoscape-fcose | ^2.2.0 | Fast force-directed layout |

#### Optional (V1)

| Library | Version | Purpose |
|---------|---------|---------|
| cytoscape-context-menus | ^4.1.0 | Right-click menus |
| cytoscape-popper | ^2.0.0 | Tooltip positioning |

#### V2 Additions

| Library | Version | Purpose |
|---------|---------|---------|
| cytoscape-cose-bilkent | ^4.1.0 | Alternative layout algorithm |
| cytoscape-edge-bundling | ^1.0.0 | Edge bundling |
| cytoscape-webgl | ^0.1.0 | WebGL renderer for large graphs |

#### CDN Links

```html
<!-- Cytoscape core -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>

<!-- fcose layout -->
<script src="https://cdn.jsdelivr.net/npm/cytoscape-fcose@2.2.0/cytoscape-fcose.min.js"></script>

<!-- Context menus (optional) -->
<script src="https://cdn.jsdelivr.net/npm/cytoscape-context-menus@4.1.0/cytoscape-context-menus.min.js"></script>
```

---