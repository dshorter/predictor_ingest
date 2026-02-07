# V1 Implementation Gaps

Audit of the V1 feature matrix (`implementation.md`) against actual code in `web/`.
Last updated: 2026-01-31.

Use this document to prioritize remaining V1 work without re-auditing the codebase.

---

## Summary

| Feature | Status | Notes |
|---------|--------|-------|
| Force-directed on load | Done | fcose with cose fallback |
| Velocity-based node sizing | Done | log2 degree scaling |
| Type-based node coloring | Done | 15-type palette |
| Recency opacity | Done | lastSeen-based fade |
| Confidence-based edge thickness | Done | 0.5–4px linear |
| Kind-based edge style | Done | solid/dashed/dotted |
| Pan/zoom | Done | |
| Click to select | Done | |
| Click to highlight neighborhood | Done | `neighborhood-dimmed` class |
| Hover tooltip | Done | `.hover` class + 400ms delay |
| Search by label/alias | Done | Debounced, dimming |
| Search highlighting | Done | `.search-match` class |
| Zoom to results | Done | Enter key fits matches |
| Node detail panel | Done | |
| Evidence panel | Done | Canvas resizes |
| Auto-filter large graphs | Done | 3-tier nodeCount check |
| Entity type filter | Done | Dynamic checkboxes, all 15 types |
| Confidence threshold | Done | Slider, default 30% |
| View presets | Done | 4 views (trending/claims/mentions/dependencies) |
| Screen reader support | Done | `aria-live` region + announcements |
| Keyboard navigation | Done | Arrow keys + Escape + `/` for search |
| Kind toggles | **Partial** | Works, but hypothesis unchecked by default (intentional?) |
| Date range filter | **Partial** | Preset buttons (7d/30d/90d/All) only, no custom date picker |
| Label visibility | **Partial** | Zoom + importance-based; no true collision detection |
| "What's new" node highlight | **Partial** | `.new` CSS class defined but never applied to nodes; edges work |
| Context menu | **Not built** | No right-click handlers or cytoscape-context-menus |
| Gzipped JSON | **Not built** | Plain JSON files served |
| Colorblind mode | **Not built** | No alternate palette or toggle |
| Reduced motion | **Not built** | No `prefers-reduced-motion` check |
| Double-click behaviors | **Not built** | No `dbltap` handlers |

---

## Detailed Gap Analysis

### Partial Implementations

#### Kind toggles
- **What works:** HTML checkboxes, filter logic, edge styling (solid/dashed/dotted)
- **Gap:** Hypothesis is excluded by default (`filter.js:18` only initializes with `asserted` and `inferred`). This may be intentional (hypothesis edges are speculative), but the feature matrix marks it as fully implemented.
- **Files:** `web/js/filter.js:18, 51-59`, `web/index.html:103-111`

#### Date range filter
- **What works:** Preset buttons (7d, 30d, 90d, All) set date ranges and filter by `lastSeen`/`firstSeen`
- **Gap:** No custom date picker input. Users can't specify arbitrary start/end dates.
- **Files:** `web/js/filter.js:27-30, 93-106, 252-269`, `web/index.html:78-86`

#### Label visibility
- **What works:** Zoom-based: at zoom >= 0.8 all labels show; below that, only hub nodes (degree > 5) and high-velocity nodes (> 0.7) keep labels
- **Gap:** No actual bounding-box collision detection. Labels can overlap on dense clusters. Docs describe a tier system with `updateConditionalLabels()` and rectangle overlap checks, but the implementation uses a simpler heuristic.
- **Files:** `web/js/layout.js:172-190`

#### "What's new" node highlighting
- **What works:** CSS class `.new` defined (green double border). `isNewNode()` utility exists. Edge highlighting for new edges works via `isNewEdge()`.
- **Gap:** No code ever calls `node.addClass('new')`. The style is defined but never applied. The "new" view preset filters to recent nodes but doesn't visually mark them.
- **Files:** `web/js/styles.js:204-211`, `web/js/utils.js:55-57`
- **Fix:** Add a pass after graph load that applies `.new` to nodes where `isNewNode(firstSeen)` returns true.

### Not Built

#### Context menu (right-click)
- **Scope:** `cytoscape-context-menus` extension or custom HTML overlay
- **Planned items:** Expand neighbors, hide node, pin position, select neighbors, view documents
- **Effort:** Medium. The extension is listed in dependencies but not loaded or initialized.
- **Spec:** `docs/ux/interaction.md` (Right-Click Context Menu section)

#### Gzipped JSON
- **Scope:** Pre-compress `data/graphs/**/*.json` to `.json.gz`; serve with appropriate headers or use client-side decompression
- **Effort:** Low. Can be a build step (`gzip -k`) with a static server config, or use the Compression Streams API client-side.
- **Note:** Only matters at scale. Current sample data is small.

#### Colorblind mode
- **Scope:** Alternate node color palette optimized for deuteranopia/protanopia. Toggle in toolbar.
- **Effort:** Medium. Requires defining a second `nodeTypeColors` object and swapping it at runtime.
- **Spec:** `docs/ux/accessibility.md`

#### Reduced motion
- **Scope:** Check `window.matchMedia('(prefers-reduced-motion: reduce)')` and disable layout animation, pan/zoom transitions, and tooltip fade.
- **Effort:** Low. Add a global check and set `animationDuration: 0` in layout config + skip `cy.animate()` calls.
- **Files to modify:** `web/js/layout.js`, `web/js/app.js`, `web/js/panels.js`

#### Double-click behaviors
- **Scope:** `dbltap` on node zooms to neighborhood; `dbltap` on background fits graph.
- **Effort:** Low. ~15 lines in `app.js`.
- **Spec:** `docs/ux/interaction.md` (Double-Click section, code already in docs)

---

## V2-Only Features (Not Expected in V1)

These are tracked in `implementation.md` but explicitly deferred:

| Feature | V2 Rationale |
|---------|-------------|
| Hide/show isolated nodes toggle | Trending view can have disconnected nodes (high velocity but edges only to non-trending entities). fcose tiles them in a grid via `tile: true`, which is correct graph layout behavior. V2 toggle to hide isolates or pull in their top neighbor would give users control. |
| ~~Navigator minimap (bird's-eye inset)~~ | **IMPLEMENTED** - Added in V1. Toggle button in toolbar, positioned bottom-right corner, adjusts when panels open. |
| Preset layout (stored positions) | Needs position persistence infrastructure |
| Hybrid layout ("integrate new") | Depends on preset layout |
| Edge bundling | Requires `cytoscape-edge-bundling` extension |
| Node expansion (load on demand) | Needs lazy data loading |
| Time-lapse animation | Needs `TimelinePlayer` class + multi-date data |
| Timeline scrubber | Depends on time-lapse |
| Lazy loading details | Needs server-side API |
| WebGL renderer | For 5k+ nodes only |
| User preferences (localStorage) | Nice-to-have |
| Saved views/filters | Nice-to-have |
