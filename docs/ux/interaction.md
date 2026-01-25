# Interaction Patterns

Pan/zoom behavior, click/hover actions, context menus, and tooltips.

---

## Pan and Zoom

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

---

## Click vs Hover Behaviors

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

---

## Right-Click Context Menu

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

## Tooltips

### Node Tooltip Content

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

### Edge Tooltip Content

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

### Tooltip Styling

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
