# Cytoscape Client UI Guidelines

Comprehensive specifications for the Cytoscape.js visualization client. These guidelines are implementation-ready for code generation.

## Document Structure

This documentation is organized into focused modules:

|Document                   |Description                                                                               |
|---------------------------|------------------------------------------------------------------------------------------|
|<design-tokens.md>         |**Start here.** Spacing, typography, colors, shadows—the foundation for visual consistency|
|<visual-encoding.md>       |Node sizing, colors, edge styles, label visibility                                        |
|<interaction.md>           |Pan/zoom, click/hover, context menus, tooltips                                            |
|<search-filter.md>         |Search box, filter panel, GraphFilter class                                               |
|<progressive-disclosure.md>|Overview → explore → detail → evidence flow                                               |
|<layout-temporal.md>       |Layout algorithms, position storage, time-lapse                                           |
|<controls.md>              |Toolbar layout and global controls                                                        |
|<performance.md>           |Rendering thresholds, optimizations                                                       |
|<accessibility.md>         |Keyboard nav, screen reader, colorblind mode                                              |
|<implementation.md>        |V1/V2 matrix, file structure, dependencies                                                |
|<v1-gaps.md>               |**Start here for dev work.** What's built, what's partial, what's missing                 |
|<troubleshooting.md>       |**Common issues and fixes.** fcose registration, CDN fallbacks, debug tools               |
|<audit-2026-02-27.md>      |**Full codebase audit.** Structural analysis, honest observations, gap matrix             |
|<gap-remediation-plan.md>  |Sequenced plan for closing spec gaps (4 phases)                                           |
|<polish-strategy.md>       |Visual and interaction refinements ("glow up"), ordered by perceptual impact               |
|<ui-testing-strategy.md>   |Testing approach: unit, integration, visual regression, a11y, performance                 |


> **Important:** All CSS must use the design tokens from `design-tokens.md`. Never use hardcoded pixel values, colors, or arbitrary spacing. This ensures visual consistency across the entire UI.

-----

## Design Philosophy

The graph is a **living map with geographic memory**. Nodes maintain stable positions over time so that:

1. Emerging clusters appear in new regions of the map
1. Declining topics fade in place (visible through color/size changes, not disappearance)
1. Bridges between previously separate domains create visible long-distance edges
1. Users build spatial intuition (“AI safety discussions are always in the upper-right”)

This spatial continuity is what makes trend detection visually intuitive. A user watching the graph over weeks should be able to see conceptual drift—new topics emerging in empty space, old topics fading but remaining in place, and unexpected connections spanning previously separate clusters.

-----

## Visual Design Principles

The UI should feel **clean, tight, and professional**—not flashy or clever. Think VS Code, Linear, or GitHub’s dashboard: tools that respect your attention with clear hierarchy, nothing arbitrary, and quiet confidence.

Key principles:

- **Consistency over creativity**: Every spacing, color, and size comes from the token system
- **Invisible good design**: Users don’t notice it, they just think “this feels solid”
- **Information density done right**: Dense but not cluttered; every pixel earns its place

-----

## Information Density and Scale Management

### Target Thresholds

|Node Count |Experience Level                 |Required Strategy                                     |
|-----------|---------------------------------|------------------------------------------------------|
|< 100      |Optimal comprehension            |No intervention needed                                |
|100–500    |Acceptable with good filtering   |Provide filter controls                               |
|500–2,000  |Requires active filtering        |Warn user; suggest filtered view                      |
|2,000–5,000|Sluggish without optimization    |Auto-filter to trending; offer “load all” with warning|
|> 5,000    |Unusable without server-side help|Refuse full client render; require pre-filtering      |

### Default View Strategy

Always default to `trending.json`, not the full graph. The trending view is pre-filtered to high-signal nodes and provides the best entry point for exploration.

### Meta Object Requirement

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

### Client Behavior Based on Meta

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