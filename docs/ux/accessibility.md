# Accessibility

Keyboard navigation, screen reader support, and colorblind mode.

---

## Color Accessibility

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

---

## Keyboard Navigation

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

---

## Directional Navigation

```javascript
function navigateToNeighbor(node, direction) {
  const neighbors = node.neighborhood('node');
  if (neighbors.length === 0) return;

  const nodePos = node.position();
  let bestMatch = null;
  let bestScore = -Infinity;

  neighbors.forEach(neighbor => {
    const pos = neighbor.position();
    const dx = pos.x - nodePos.x;
    const dy = pos.y - nodePos.y;

    let score;
    switch (direction) {
      case 'ArrowUp':
        score = -dy - Math.abs(dx) * 0.5;
        break;
      case 'ArrowDown':
        score = dy - Math.abs(dx) * 0.5;
        break;
      case 'ArrowLeft':
        score = -dx - Math.abs(dy) * 0.5;
        break;
      case 'ArrowRight':
        score = dx - Math.abs(dy) * 0.5;
        break;
    }

    if (score > bestScore) {
      bestScore = score;
      bestMatch = neighbor;
    }
  });

  if (bestMatch) {
    cy.nodes().unselect();
    bestMatch.select();
    centerOnNode(bestMatch);
  }
}

function centerOnNode(node) {
  cy.animate({
    center: { eles: node },
    duration: 200
  });
}
```

---

## Screen Reader Support

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

---

## Reduced Motion

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

## Focus Indicators

```css
/* Visible focus indicators */
#cy:focus {
  outline: 3px solid #3B82F6;
  outline-offset: 2px;
}

button:focus,
select:focus,
input:focus {
  outline: 2px solid #3B82F6;
  outline-offset: 2px;
}

/* High contrast mode support */
@media (prefers-contrast: high) {
  .tooltip-type {
    border: 2px solid currentColor;
  }

  .node-highlight {
    outline: 3px solid black;
  }
}
```

---

## ARIA Labels

```javascript
// Add ARIA labels to dynamic content
function updateAriaLabels(cy) {
  const nodeCount = cy.nodes(':visible').length;
  const edgeCount = cy.edges(':visible').length;

  cy.container().setAttribute(
    'aria-label',
    `AI Trend Graph visualization with ${nodeCount} nodes and ${edgeCount} connections`
  );
}

// Update on filter changes
cy.on('filtersApplied', () => {
  updateAriaLabels(cy);
});
```
