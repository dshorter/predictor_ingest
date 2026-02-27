# Gap Remediation Plan

Sequenced plan for closing the spec-vs-implementation gaps identified in
[audit-2026-02-27.md](audit-2026-02-27.md). Ordered by dependency chain and effort,
not arbitrary priority numbers.

**Principle:** Fix dead code and wiring gaps first. They're cheap, they reduce the
delta between spec and reality, and they remove noise from future audits. Then build
missing features. Polish comes after (see [polish-strategy.md](polish-strategy.md)).

---

## Phase 1 — Dead Code & Wiring (1–2 sessions)

These are features where the hard work is done but the last mile was never wired.
Each is ≤20 lines of JS.

### 1.1 Apply `.new` class to recent nodes

**Gap:** `isNewNode()` in `utils.js` exists. `.new` CSS class in `styles.js` exists
(green double border). But no code ever calls `node.addClass('new')`.

**Fix:** After `addElements(cy, data)` in `graph.js`, iterate nodes and apply:

```javascript
cy.nodes().forEach(node => {
  if (isNewNode(node.data('firstSeen'))) {
    node.addClass('new');
  }
});
```

**Also needed:** Clear `.new` on view switch (before loading new data).

**Files:** `web/js/graph.js`, possibly `web/js/app.js` (view switch handler)
**Effort:** ~10 lines

### 1.2 Wire double-click (dbltap) handlers

**Gap:** `interaction.md` specifies double-click on node → zoom to 1-hop neighborhood,
double-click on background → fit graph. `expandNeighbors()` and `cy.fit()` both exist.

**Fix:** In `app.js` event setup:

```javascript
cy.on('dbltap', 'node', (evt) => {
  const node = evt.target;
  expandNeighbors(node.id());
  cy.animate({ fit: { eles: node.neighborhood().add(node), padding: 50 } });
});

cy.on('dbltap', (evt) => {
  if (evt.target === cy) {
    cy.animate({ fit: { padding: 50 } });
  }
});
```

**Files:** `web/js/app.js`
**Effort:** ~15 lines

### 1.3 Apply `prefers-reduced-motion`

**Gap:** `reset.css` declares `scroll-behavior: auto` for reduced motion, but layout
animations, panel transitions, and tooltip fades all ignore it.

**Fix:** Read the preference once at init:

```javascript
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
```

Then pass `animationDuration: prefersReducedMotion ? 0 : 500` to layout config,
and conditionally set `transition-duration: 0s` on panels/tooltips (via a body class
like `.reduced-motion`).

**Files:** `web/js/app.js` (init), `web/js/layout.js` (duration), `web/css/tokens.css`
or a new utility class
**Effort:** ~20 lines JS + ~10 lines CSS

---

## Phase 2 — Missing Features, Low Effort (1–2 sessions)

### 2.1 Gzipped JSON export

**Gap:** `performance.md` and `implementation.md` both list gzipped JSON as V1.
Current export is plain JSON.

**Fix:** Add a build step (in `scripts/` or `Makefile`) that runs `gzip -k` on
exported JSON files. For static hosting, configure `Content-Encoding: gzip` headers.
Alternatively, use client-side Compression Streams API for decompression.

**Decision needed:** Server-side gzip (simpler, depends on hosting) vs client-side
decompression (portable, slightly more code). Recommend server-side for V1.

**Files:** `scripts/export_graph.py` or `Makefile`, hosting config
**Effort:** Low (build step + config)

### 2.2 Document the hypothesis-unchecked decision

**Gap:** `filter.js:18` initializes kind filters with only `asserted` and `inferred`
checked. Hypothesis is off by default. This is probably intentional (hypothesis edges
are speculative) but it's not documented anywhere.

**Fix:** Add a comment in `filter.js` and a note in `search-filter.md` explaining the
design decision. If it's NOT intentional, flip the default.

**Files:** `web/js/filter.js`, `docs/ux/search-filter.md`
**Effort:** ~5 minutes

---

## Phase 3 — Missing Features, Medium Effort (2–4 sessions)

### 3.1 Context menu (right-click)

**Gap:** `interaction.md` fully specifies a right-click context menu with: Expand
neighbors, Hide node, Pin position, Select neighbors, View documents. The
`cytoscape-context-menus` extension is listed in dependencies but never loaded.

**Approach:**
1. Load the extension from CDN (add `<script>` to `index.html`)
2. Register with `cytoscape.use(contextMenus)`
3. Configure menu items per the spec
4. Wire handlers to existing functions (`expandNeighbors`, etc.)
5. Handle "pin position" as a new feature (lock node, exclude from layout)
6. Handle "hide node" (add `.filtered-out` class, track manually hidden nodes)

**Complexity:** The extension loading is straightforward. The tricky parts are:
- "Pin position" needs layout integration (pinned nodes get `position: 'fixed'` in fcose)
- "Hide node" needs state tracking so nodes can be unhidden
- Mobile: no right-click. Could add long-press → context menu, or skip for mobile V1.

**Files:** `web/index.html`, `web/js/app.js` (or new `web/js/context-menu.js`)
**Effort:** Medium. Core menu ~50 lines. Pin/hide logic ~100 lines.

### 3.2 Colorblind-safe palette

**Gap:** `accessibility.md` specifies an alternate palette. No toggle exists.

**Approach:**
1. Define a second set of entity-type color tokens (e.g., `--entity-org-cb`) using
   a deuteranopia/protanopia-safe palette (Wong palette or similar)
2. Add a toggle button in toolbar (or settings area)
3. On toggle, apply `[data-colorblind="true"]` to `<html>`, which swaps the tokens
4. Persist preference in `localStorage`
5. Update `styles.js` `getNodeTypeColors()` to read from the active token set

**Files:** `web/css/tokens.css` (alternate palette), `web/js/app.js` (toggle),
`web/js/styles.js` (color reading), `web/index.html` (toggle button)
**Effort:** Medium. Palette design ~30 min. Wiring ~50 lines.

### 3.3 Custom date range picker

**Gap:** Only preset buttons (7d/30d/90d/All). No arbitrary date input.

**Approach:**
1. Add `<input type="date">` fields for start and end dates in the filter panel
2. Wire to `GraphFilter.setDateRange(start, end)`
3. Keep preset buttons as shortcuts that populate the date inputs
4. Sync: when a preset is clicked, update the date inputs; when dates are manually
   changed, deselect the active preset

**Files:** `web/index.html` (inputs), `web/js/app.js` (wiring), `web/js/filter.js`
(already supports arbitrary ranges)
**Effort:** Medium. UI ~30 lines HTML, wiring ~40 lines JS.

---

## Phase 4 — Deferred / Decide Later

### 4.1 Label collision detection

**Current:** Zoom + importance heuristic (degree > 5 or velocity > 0.7 at low zoom).
**Spec:** Bounding-box overlap detection with priority-based hiding.

**Assessment:** The current heuristic works acceptably for graphs under ~200 nodes.
True collision detection requires measuring rendered text bounds
(`node.renderedBoundingBox()`) on every zoom change, which has performance
implications for large graphs.

**Recommendation:** Defer to V2 unless user feedback specifically complains about
label overlap. The current approach is a reasonable tradeoff.

### 4.2 Mobile CSS splitting

**Current:** `mobile.css` is 1,170 lines in one file.
**Observation:** Could be split into component files like desktop. But it works,
and splitting purely for organization without other changes adds churn.

**Recommendation:** Split only if mobile CSS needs significant changes for other
reasons. Don't split for its own sake.

---

## Sequencing Summary

```
Phase 1 (dead code)     Phase 2 (low effort)     Phase 3 (medium)         Phase 4 (defer)
┌─────────────────┐    ┌───────────────────┐    ┌──────────────────────┐  ┌──────────────┐
│ 1.1 .new class  │    │ 2.1 Gzipped JSON  │    │ 3.1 Context menu     │  │ 4.1 Label    │
│ 1.2 dbltap      │───▶│ 2.2 Document      │───▶│ 3.2 Colorblind mode  │  │     collision │
│ 1.3 Reduced     │    │     hypothesis     │    │ 3.3 Custom date pick │  │ 4.2 Mobile   │
│     motion      │    │     decision       │    │                      │  │     CSS split │
└─────────────────┘    └───────────────────┘    └──────────────────────┘  └──────────────┘
     ~1 session              ~1 session              ~3 sessions              V2 / as-needed
```

**Total estimated sessions for Phases 1–3:** 5–8 focused sessions.

Phase 1 should be completed before any polish work begins (see
[polish-strategy.md](polish-strategy.md)). Phases 2 and 3 can interleave with
polish if needed — they're independent tracks.
