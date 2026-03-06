# AI Trend Graph — Web Client

Interactive Cytoscape.js knowledge graph explorer. Static site — no backend required beyond the exported JSON files from the pipeline.

## Getting Started

```bash
# From the project root:
make copy-to-live                      # Publish latest export to web/data/graphs/live/
cd web && python -m http.server 8000   # Serve at http://localhost:8000
```

Or use any static file server (nginx, Caddy, etc.) pointed at `web/`.

Without live data, the app can load **sample datasets** (small/medium/large/stress) bundled in `data/graphs/` — selectable from the filter panel.

## Features

| Feature | Description |
|---------|-------------|
| **4 graph views** | Trending, Claims, Mentions, Dependencies — switch via toolbar dropdown |
| **Force-directed layout** | fcose with automatic clustering; re-run button in toolbar |
| **Search** | Real-time node search with match highlighting and dimming |
| **Filters** | Entity type, relationship kind (asserted/inferred/hypothesis), confidence threshold, date range presets (7d/30d/90d/All) |
| **Node detail panel** | Click a node to see type, aliases, connections, trend scores, evidence |
| **Edge evidence panel** | Click an edge to see provenance: source snippet, URL, confidence |
| **Minimap** | Navigator overlay for orientation in large graphs |
| **Dark mode** | System-aware with manual toggle; persists to localStorage |
| **Mobile** | Dedicated touch-optimized viewer at `mobile/` with swipe gestures |
| **Accessibility** | ARIA roles, keyboard navigation, screen reader live region |
| **Empty state** | Helpful messaging when a view has no data, with reset/switch suggestions |

## Architecture

```
index.html                  ← Desktop entry point (redirects mobile UA to mobile/)
├── js/
│   ├── app.js              ← App init, state management, theme, data loading
│   ├── graph.js            ← Cytoscape instance creation, node/edge interaction
│   ├── layout.js           ← fcose registration, layout runner, fallback to cose
│   ├── styles.js           ← Cytoscape stylesheet (node shapes, colors, labels)
│   ├── filter.js           ← GraphFilter class: type/kind/confidence/date filtering
│   ├── search.js           ← Real-time search with result counting and highlighting
│   ├── panels.js           ← Detail, evidence, and filter panel management
│   ├── tooltips.js         ← Hover tooltips with debounced positioning
│   ├── help.js             ← Help panel with tabs (Quick Start, Topics)
│   └── utils.js            ← Shared helpers (formatting, date, DOM)
├── css/
│   ├── main.css            ← CSS import aggregator
│   ├── tokens.css          ← Design tokens (colors, spacing, typography, radii)
│   ├── base.css            ← Base element styles
│   ├── reset.css           ← CSS reset
│   ├── utilities.css       ← Utility classes
│   ├── components/         ← panel, toolbar, button, input, badge, tooltip, help-panel
│   └── graph/              ← cytoscape.css (node/edge visual encoding), overlays.css
├── help/
│   ├── content.js          ← Help content data structure (quick start + topic accordion)
│   └── glossary.html       ← Standalone glossary page
├── dashboard.html          ← Dashboard / insights view
├── mobile/
│   ├── index.html          ← Mobile entry point
│   ├── js/                 ← app-mobile.js, panels-mobile.js, touch.js
│   └── css/mobile.css      ← Mobile-specific styles
└── data/graphs/
    ├── live/               ← Production data (symlinked from pipeline output)
    │   ├── mentions.json
    │   ├── claims.json
    │   ├── dependencies.json
    │   └── trending.json
    ├── small/              ← ~15 nodes (quick testing)
    ├── medium/             ← ~150 nodes (default sample)
    ├── large/              ← ~500 nodes
    ├── stress/             ← ~2000 nodes (performance testing)
    └── latest/             ← Most recent export
```

## Data Format

The client expects Cytoscape.js `elements` JSON. Each view file follows this structure:

```json
{
  "meta": {
    "view": "trending",
    "nodeCount": 42,
    "edgeCount": 87,
    "exportedAt": "2026-03-06T12:00:00Z",
    "dateRange": { "start": "2026-02-04", "end": "2026-03-06" }
  },
  "elements": {
    "nodes": [
      {
        "data": {
          "id": "org:openai",
          "label": "OpenAI",
          "type": "Org",
          "trendScore": 0.85,
          "velocity": 2.3,
          "novelty": 0.1,
          "mentionCount7d": 15,
          "mentionCount30d": 42
        }
      }
    ],
    "edges": [
      {
        "data": {
          "id": "e-123",
          "source": "org:openai",
          "target": "model:gpt-5",
          "rel": "LAUNCHED",
          "kind": "asserted",
          "confidence": 0.95,
          "snippet": "OpenAI announced GPT-5 on...",
          "docId": "doc:abc123"
        }
      }
    ]
  }
}
```

See [docs/schema/data-contracts.md](../docs/schema/data-contracts.md) for the full schema.

## CDN Dependencies

Loaded in `index.html` in this order (order matters for fcose):

1. **Cytoscape.js** 3.28.1 — core graph library
2. **layout-base** 2.0.1 — fcose dependency
3. **cose-base** 2.2.0 — fcose dependency
4. **cytoscape-fcose** 2.2.0 — force-directed layout
5. **cytoscape-navigator** 2.0.1 — minimap extension

If unpkg fails, fcose falls back to jsdelivr CDN automatically.

## Cytoscape.js Gotchas

These are critical for anyone modifying the web client:

1. **No CSS pseudo-selectors.** Cytoscape.js only supports `:selected`, `:active`, `:grabbed`. Use JS events to add/remove classes (e.g., `.hover`, `.dimmed`).

2. **Colon-safe ID lookups.** Entity IDs contain colons (`org:openai`). Always use `cy.getElementById('org:openai')`, never `cy.$('#org:openai')` — the colon breaks CSS selector parsing.

3. **Manual `cy.resize()` after container changes.** Call with `setTimeout(~50ms)` after toggling panels or the minimap, otherwise the canvas dimensions are stale.

4. **fcose CDN load order.** Must load `layout-base` → `cose-base` → `cytoscape-fcose` in that order, or fcose silently fails to register. The app has multi-attempt registration and console diagnostics (`window.debugFcose()`).

5. **Separate CSS classes for dimming contexts.** Search uses `.dimmed`; neighborhood highlighting uses `.neighborhood-dimmed`. Don't merge them or clearing one context will clear the other.

## Design Tokens

Visual styling is centralized in `css/tokens.css`:

- **Colors:** semantic palette for node types, confidence levels, UI chrome
- **Spacing:** 4px base unit scale
- **Typography:** Inter for headings, system mono stack for data
- **Dark mode:** `[data-theme="dark"]` overrides on all tokens

## Related Documentation

| Document | Purpose |
|----------|---------|
| [UX Implementation Spec](../docs/ux/README.md) | Full client implementation guidelines |
| [Visual Encoding](../docs/ux/visual-encoding.md) | Node shape/color/size rules by entity type |
| [Design Tokens](../docs/ux/design-tokens.md) | Color palette, spacing, typography scale |
| [Polish Strategy](../docs/ux/polish-strategy.md) | Aesthetic refinements: toolbar, canvas, depth |
| [Troubleshooting](../docs/ux/troubleshooting.md) | Detailed Cytoscape.js fixes with root causes |
| [Accessibility](../docs/ux/accessibility.md) | A11y compliance and keyboard navigation |
| [Search & Filter](../docs/ux/search-filter.md) | Search/filter UX specification |
| [Product Guide](../docs/product/README.md) | End-user walkthrough and workflows |
