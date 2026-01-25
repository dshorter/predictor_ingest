# Performance Guidelines

Rendering thresholds and optimization strategies.

---

## Client-Side Rendering Thresholds

| Node Count | Edge Count | Recommendation |
|------------|------------|----------------|
| < 500 | < 1,000 | Render all; smooth experience |
| 500–1,000 | 1,000–2,000 | Enable text-on-viewport optimization |
| 1,000–2,000 | 2,000–5,000 | Warn user; suggest filtering |
| 2,000–5,000 | 5,000–10,000 | Auto-filter; load full on demand |
| > 5,000 | > 10,000 | Require server-side filtering |

---

## Cytoscape Performance Optimizations

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

---

## Lazy Loading (V2)

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

---

## JSON Compression

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

## Memory Management

```javascript
// Clean up when switching views
function cleanupGraph(cy) {
  // Remove all elements
  cy.elements().remove();

  // Clear caches
  cy.style().resetToDefault();

  // Force garbage collection hint
  if (window.gc) window.gc();
}

// Batch updates for better performance
function batchUpdate(cy, updates) {
  cy.startBatch();
  try {
    updates();
  } finally {
    cy.endBatch();
  }
}

// Example usage
batchUpdate(cy, () => {
  cy.nodes().forEach(node => {
    node.data('highlighted', false);
    node.removeClass('dimmed');
  });
});
```

---

## Debouncing and Throttling

```javascript
// Debounce for search input
function debounce(fn, delay) {
  let timeout;
  return function(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn.apply(this, args), delay);
  };
}

// Throttle for zoom/pan events
function throttle(fn, limit) {
  let inThrottle;
  return function(...args) {
    if (!inThrottle) {
      fn.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

// Apply to events
cy.on('zoom', throttle(updateLabelsOnZoom, 100));
cy.on('pan', throttle(updateViewportInfo, 50));
```
