# Layout and Temporal Features

Layout algorithms, position storage, and time-based features.

---

## V1: Force-Directed on Load

For V1, compute layout on each page load using a force-directed algorithm.
Parameters auto-scale based on graph size and density using a **reference
calibration** from the trending view.

### Reference Calibration (Golden Ratio)

The trending view at medium scale (37 nodes, 31 edges, density ~0.84) is our
golden reference where the base parameters produce a well-spaced, readable
layout. All larger graphs scale from this reference point.

| Parameter | Reference Value | Scaling Rule | Rationale |
|-----------|----------------|--------------|-----------|
| `nodeSeparation` | 75 | × √(nodeRatio) | Spectral phase spacing grows with graph, sqrt prevents extreme values |
| `nodeRepulsion` | 4500 | × nodeRatio × densityRatio | Linear per node; denser graphs get proportionally more push |
| `idealEdgeLength` | 50 | × √(nodeRatio) × √(densityRatio) | Longer edges in bigger/denser graphs reduce overlap |
| `gravity` | 0.25 | ÷ nodeRatio | Inverse scaling — weaker pull prevents central hairball |
| `gravityRange` | 3.8 | × √(nodeRatio), max 15 | Falloff covers larger layout space |
| `numIter` | 2500 | 3000 at 100+, 3500 at 500+, 4000 at 1000+ | More iterations for convergence at scale |

Where:
- `nodeRatio = nodeCount / 37`
- `densityRatio = (edgeCount/nodeCount) / 0.84`

**Why ratio-based, not logarithmic:** With `fit: true`, fcose computes positions
then scales to the viewport. What matters is the *ratio between forces*, not
absolute values. The repulsion/gravity ratio determines cluster tightness even
after fit-normalization. Linear scaling preserves this ratio proportionally;
logarithmic scaling was too conservative and produced visually identical results.

### Example Scaled Values

| View | Nodes | Edges | nodeSep | Repulsion | EdgeLen | Gravity |
|------|-------|-------|---------|-----------|---------|---------|
| Trending (ref) | 37 | 31 | 75 | 4,500 | 50 | 0.2500 |
| Claims medium | 136 | 371 | 144 | 53,855 | 173 | 0.0680 |
| Claims large | 422 | 1,403 | 253 | 203,661 | 336 | 0.0219 |
| Stress claims | 1,203 | 4,622 | 428 | 670,935 | 611 | 0.0077 |

### Base Configuration

```javascript
// Base layout options (used as-is for graphs ≤ 37 nodes)
const LAYOUT_OPTIONS_BASE = {
  name: 'fcose',  // Fast compound spring embedder

  // Animation
  animate: true,
  animationDuration: 500,
  animationEasing: 'ease-out',

  // Layout quality
  quality: 'default',  // 'draft', 'default', or 'proof'
  randomize: true,

  // Node repulsion (reference values for ~37 nodes)
  nodeSeparation: 75,
  nodeRepulsion: 4500,
  idealEdgeLength: 50,
  edgeElasticity: 0.45,
  nestingFactor: 0.1,

  // Gravity (pulls disconnected components together)
  gravity: 0.25,
  gravityRange: 3.8,

  // Iteration limits
  numIter: 2500,

  // Tiling (for disconnected components)
  tile: true,
  tilingPaddingVertical: 10,
  tilingPaddingHorizontal: 10,

  // Fit after layout
  fit: true,
  padding: 50
};

// Reference calibration point
const REFERENCE = {
  nodes: 37,        // trending medium node count
  edges: 31,        // trending medium edge count
  density: 31 / 37  // ~0.84 edges per node
};
```

### Auto-Scaling Implementation

See `web/js/layout.js` — `getScaledLayoutOptions(nodeCount, edgeCount)`.

The console logs the computed ratios and final params on every layout run for
debugging:
```
Layout ratio-scale: 136n/371e | nodeRatio=3.7x, density=2.73, densityRatio=3.26x
Scaled → nodeSep=144, repulsion=53855, edgeLen=173, gravity=0.0680, gravRange=7.3, iters=3000
```

Use `debugLayout()` in the browser console to see base vs scaled params for the
current graph. Use `adjustLayout({ gravity: 0.01 })` to test individual params.

---

## V2: Preset Default with Options

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

---

## Position Storage Format

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

---

## Daily Export Workflow (V2)

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

## Temporal Features

### V1: Static Temporal Filtering

V1 provides temporal context through filtering and visual encoding:

**Date Range Filter:**
- Implemented in Filter Panel (see [search-filter.md](search-filter.md))
- Filters based on `firstSeen` and `lastSeen`
- Preset buttons: 7d, 30d, 90d, All

**Recency-Based Visual Encoding:**
- Node opacity/saturation based on `lastSeen` (see [visual-encoding.md](visual-encoding.md))
- Edge color highlighting for new edges

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

---

### V2: Time-Lapse Animation

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

**TimelinePlayer Class:**

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
