# Implementation Guide

V1/V2 feature matrix, file structure, and dependencies.

-----

## V1 vs V2 Feature Matrix

|Feature                        |V1 |V2 |Notes                   |
|-------------------------------|:-:|:-:|------------------------|
|**Layout**                     |   |   |                        |
|Force-directed on load         |✅  |✅  |Optional in V2          |
|Preset layout                  |❌  |✅  |Default in V2           |
|Position storage               |❌  |✅  |Enables stability       |
|Hybrid layout (“Integrate new”)|❌  |✅  |For daily updates       |
|                               |   |   |                        |
|**Visualization**              |   |   |                        |
|Velocity-based node sizing     |✅  |✅  |                        |
|Type-based node coloring       |✅  |✅  |                        |
|Recency opacity/saturation     |✅  |✅  |                        |
|Confidence-based edge thickness|✅  |✅  |                        |
|Kind-based edge style          |✅  |✅  |                        |
|Edge bundling                  |❌  |✅  |For dense graphs        |
|                               |   |   |                        |
|**Interaction**                |   |   |                        |
|Pan/zoom                       |✅  |✅  |                        |
|Click to select                |✅  |✅  |                        |
|Hover to preview               |✅  |✅  |                        |
|Context menu                   |✅  |✅  |                        |
|Node expansion                 |❌  |✅  |Load neighbors on demand|
|                               |   |   |                        |
|**Filtering**                  |   |   |                        |
|Date range filter              |✅  |✅  |                        |
|Entity type filter             |✅  |✅  |                        |
|Kind toggles                   |✅  |✅  |                        |
|Confidence threshold           |✅  |✅  |                        |
|View presets (trending/new/all)|✅  |✅  |                        |
|                               |   |   |                        |
|**Search**                     |   |   |                        |
|Search by label/alias          |✅  |✅  |                        |
|Search highlighting            |✅  |✅  |                        |
|Zoom to results                |✅  |✅  |                        |
|                               |   |   |                        |
|**Information Display**        |   |   |                        |
|Node tooltips                  |✅  |✅  |                        |
|Edge tooltips                  |✅  |✅  |                        |
|Node detail panel              |✅  |✅  |                        |
|Evidence panel                 |✅  |✅  |                        |
|                               |   |   |                        |
|**Temporal**                   |   |   |                        |
|Recency-based visual encoding  |✅  |✅  |                        |
|“What’s new” highlighting      |✅  |✅  |                        |
|Time-lapse animation           |❌  |✅  |                        |
|Timeline scrubber              |❌  |✅  |                        |
|                               |   |   |                        |
|**Performance**                |   |   |                        |
|Gzipped JSON                   |✅  |✅  |                        |
|Auto-filter large graphs       |✅  |✅  |                        |
|Lazy loading details           |❌  |✅  |                        |
|WebGL renderer                 |❌  |✅  |For 5k+ nodes           |
|                               |   |   |                        |
|**Accessibility**              |   |   |                        |
|Keyboard navigation            |✅  |✅  |                        |
|Screen reader support          |✅  |✅  |                        |
|Colorblind mode                |✅  |✅  |                        |
|Reduced motion                 |✅  |✅  |                        |
|                               |   |   |                        |
|**Persistence**                |   |   |                        |
|User preferences               |❌  |✅  |localStorage            |
|Saved views/filters            |❌  |✅  |                        |

-----

## File Structure (web/)

Recommended directory structure for the Cytoscape client:

```
web/
├── index.html              # Main HTML shell
├── css/
│   ├── tokens.css          # Design tokens (from design-tokens.md) — LOAD FIRST
│   ├── reset.css           # Minimal reset (box-sizing, margins)
│   ├── base.css            # Body, typography defaults, links
│   ├── components/
│   │   ├── button.css
│   │   ├── input.css
│   │   ├── badge.css
│   │   ├── panel.css
│   │   ├── toolbar.css
│   │   ├── tooltip.css
│   │   └── ...
│   ├── graph/
│   │   ├── cytoscape.css   # Cytoscape container styles
│   │   └── overlays.css    # Graph-specific overlays
│   ├── utilities.css       # Small utility classes
│   └── main.css            # Imports all above in order
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

### CSS Import Order

The order matters. `main.css` should import files in this sequence:

```css
/* main.css */

/* 1. Design tokens — foundation for everything */
@import 'tokens.css';

/* 2. Reset — normalize browser defaults */
@import 'reset.css';

/* 3. Base — typography, body, links */
@import 'base.css';

/* 4. Components — individual UI pieces */
@import 'components/button.css';
@import 'components/input.css';
@import 'components/badge.css';
@import 'components/panel.css';
@import 'components/toolbar.css';
@import 'components/tooltip.css';

/* 5. Graph-specific */
@import 'graph/cytoscape.css';
@import 'graph/overlays.css';

/* 6. Utilities — last, so they can override */
@import 'utilities.css';
```

-----

## Dependencies

### Required (V1)

|Library        |Version|Purpose                   |
|---------------|-------|--------------------------|
|Cytoscape.js   |^3.28.0|Core graph visualization  |
|cytoscape-fcose|^2.2.0 |Fast force-directed layout|

### Optional (V1)

|Library                |Version|Purpose            |
|-----------------------|-------|-------------------|
|cytoscape-context-menus|^4.1.0 |Right-click menus  |
|cytoscape-popper       |^2.0.0 |Tooltip positioning|

### V2 Additions

|Library                |Version|Purpose                        |
|-----------------------|-------|-------------------------------|
|cytoscape-cose-bilkent |^4.1.0 |Alternative layout algorithm   |
|cytoscape-edge-bundling|^1.0.0 |Edge bundling                  |
|cytoscape-webgl        |^0.1.0 |WebGL renderer for large graphs|

-----

## CDN Links

```html
<!-- Cytoscape core -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>

<!-- fcose layout -->
<script src="https://cdn.jsdelivr.net/npm/cytoscape-fcose@2.2.0/cytoscape-fcose.min.js"></script>

<!-- Context menus (optional) -->
<script src="https://cdn.jsdelivr.net/npm/cytoscape-context-menus@4.1.0/cytoscape-context-menus.min.js"></script>
```

-----

## NPM Installation

```bash
# Core dependencies
npm install cytoscape cytoscape-fcose

# Optional V1 dependencies
npm install cytoscape-context-menus cytoscape-popper

# V2 dependencies
npm install cytoscape-cose-bilkent cytoscape-edge-bundling
```

-----

## Initialization Example

```javascript
// app.js - Main entry point
import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';
import contextMenus from 'cytoscape-context-menus';

import { initializeStyles } from './styles.js';
import { GraphFilter } from './filter.js';
import { initializeSearch } from './search.js';
import { initializePanels } from './panels.js';
import { initializeAccessibility } from './accessibility.js';

// Register extensions
cytoscape.use(fcose);
cytoscape.use(contextMenus);

// Initialize application
async function init() {
  // Create Cytoscape instance
  const cy = cytoscape({
    container: document.getElementById('cy'),
    style: initializeStyles(),
    // ... other options
  });

  // Initialize modules
  const filter = new GraphFilter(cy);
  initializeSearch(cy);
  initializePanels(cy);
  initializeAccessibility(cy);

  // Load default view
  await loadGraphView('trending');

  // Apply initial filter
  filter.apply();
}

// Start when DOM is ready
document.addEventListener('DOMContentLoaded', init);
```

-----

## Design Token Usage

All CSS must use design tokens from `tokens.css`. This is non-negotiable for visual consistency.

### Required Patterns

```css
/* ✓ Correct — uses tokens */
.panel {
  padding: var(--space-4);
  background: var(--gray-50);
  border: var(--border-width) solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
}

.panel-title {
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
  color: var(--gray-900);
  margin-bottom: var(--space-3);
}
```

### Anti-Patterns

```css
/* ✗ Wrong — hardcoded values */
.panel {
  padding: 15px;
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.panel-title {
  font-size: 18px;
  font-weight: 600;
  color: #212529;
  margin-bottom: 12px;
}
```

See <design-tokens.md> for the complete token reference.