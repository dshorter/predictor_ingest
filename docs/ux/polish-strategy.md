# Polish Strategy ("Glow Up")

Visual and interaction refinements that take the UI from "works correctly" to "feels right."
These are not bugs or spec gaps — they're the difference between a tool and a product.

**Prerequisite:** Complete [Phase 1 of gap remediation](gap-remediation-plan.md) first.
Dead code and wiring gaps should be settled before polishing. No point shining something
that's not fully connected.

---

## Honest Assessment

The foundation doesn't need a rescue. The token system, component architecture, and visual
encoding are genuinely well-built. What's missing is the *connective tissue* — the
micro-interactions and transitions that make state changes feel intentional rather than
abrupt.

The items below are ordered by **perceptual impact** (what users notice most), not
engineering effort.

---

## P1 — High Perceptual Impact

### View switch transition

**Current:** Switching views (trending → claims) causes the graph to vanish and reappear
after a brief loading pause. No visual continuity.

**Target:** Smooth crossfade or opacity transition during the load-layout cycle.

**Approach:**
1. When view switch is triggered, fade the `#cy` container to 50% opacity (100ms)
2. Show a subtle inline spinner (not the full-screen overlay — that feels heavy)
3. Load new data, run layout
4. On `layoutstop`, fade `#cy` back to 100% (200ms)

**Why it matters:** View switching is one of the most frequent interactions. Every switch
currently feels like a page reload. A transition signals "same tool, different lens"
rather than "broken → loading → fixed."

**Files:** `web/js/app.js` (view switch handler), `web/css/graph/cytoscape.css` (transition)
**Effort:** ~30 lines

### Panel open/close animation smoothness

**Current:** Panels slide in with `transform: translateX()` and a 300ms transition.
The graph container resizes via CSS, which triggers Cytoscape to re-render.

**Observation:** The panel animations are fine. But the Cytoscape resize causes a visual
jump because `cy.resize()` is called synchronously. The graph content snaps to the new
bounds while the panel is still sliding.

**Target:** Defer `cy.resize()` until the panel transition completes (listen for
`transitionend`), or animate the Cytoscape container bounds in sync with the panel.

**Files:** `web/js/panels.js` (`updateCyContainer`), `web/js/app.js`
**Effort:** ~15 lines (add `transitionend` listener)

### Empty state design

**Current:** Empty state shows a centered icon + text message. Functional but generic.

**Target:** Add contextual guidance based on *why* it's empty:
- No data loaded → "Select a view to get started"
- All filtered out → "Your filters are hiding all nodes. Try widening your date range or enabling more entity types." + Reset Filters button
- Network error → Current error dialog (fine as-is)

**Files:** `web/js/graph.js` (empty state handler), `web/js/filter.js` (filter-caused empty)
**Effort:** ~40 lines

---

## P2 — Medium Perceptual Impact

### Detail panel inline styles → CSS classes

**Current:** The stats grid in the detail panel uses inline styles:
```javascript
`<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px">`
```

This breaks the "all styling via tokens" discipline that every other component follows.

**Target:** Extract to `.detail-stats-grid` class in `panel.css`:
```css
.detail-stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}
```

**Files:** `web/css/components/panel.css`, `web/js/panels.js`
**Effort:** ~10 lines

### Toolbar touch targets (desktop)

**Current:** Some toolbar buttons are 36×36px. The spec recommends ≥44×44px for
accessibility compliance (WCAG 2.5.5 Target Size).

**Assessment:** 36px is acceptable for desktop mouse interaction but fails the
accessibility spec. The mobile implementation correctly uses 48px.

**Target:** Increase `.btn-icon` to 40×40px minimum on desktop. Full 44px may crowd
the toolbar — test and decide.

**Files:** `web/css/components/button.css`
**Effort:** 1 line (change `width/height` on `.btn-icon`)

### Tooltip positioning edge cases

**Current:** Tooltips reposition to avoid viewport edges. But when a node is near
the bottom-right corner and both the detail panel (left) and filter panel (right)
are open, the available space can be very narrow.

**Target:** Account for open panel widths when computing available tooltip space.

**Files:** `web/js/tooltips.js` (positioning logic)
**Effort:** ~15 lines

### Search result count positioning

**Current:** Search result count ("5 nodes") is absolutely positioned inside the
search input. On narrow viewports or with long count text, it can overlap the
search text.

**Target:** Either:
- Move count below the input (small label)
- Or clip count to "5" instead of "5 nodes" when space is tight

**Files:** `web/css/components/toolbar.css`, `web/js/search.js`
**Effort:** ~10 lines

---

## P3 — Lower Priority Polish

### "What's New" temporal highlight mode

**Current:** The `.new` class exists for nodes. After Phase 1.1, it'll be auto-applied.
But there's no active toggle to "show me what changed."

**Target:** Add a toolbar toggle (or view preset) that:
1. Dims everything older than 7 days
2. Highlights new nodes with the green border
3. Highlights new edges
4. Shows a "What's New: 3 nodes, 5 edges" summary

This is a natural evolution after the `.new` class is wired (Phase 1.1).

**Files:** `web/js/app.js` (toggle), `web/js/filter.js` (temporal mode)
**Effort:** ~50 lines

### Loading skeleton for panels

**Current:** Panels show content immediately when opened (data is already in memory).
No loading state needed for current behavior.

**But:** If V2 adds lazy-loaded details (per `implementation.md`), panels will need
a loading state. A skeleton placeholder would look polished.

**Recommendation:** Skip for V1 unless panels start fetching data asynchronously.
Document as a V2 polish item.

### Minimap toggle animation

**Current:** Minimap shows/hides with opacity + translate. Acceptable.

**Could be nicer:** Scale from 0 at the corner (origin: bottom-right) for a more
natural "collapse into corner" feel. Very low priority.

### Dark mode transition

**Current:** Theme toggle is instant. All colors swap at once.

**Could be nicer:** A 200ms cross-fade on `background-color` and `color` transitions
on `<body>`. Most design-conscious apps do this. But it requires adding `transition`
to many elements, which can cause performance issues.

**Recommendation:** Skip unless it bothers users. The instant swap is fine.

---

## Sequencing

```
After Phase 1 gaps are closed:

P1 (high impact)         P2 (medium impact)       P3 (lower priority)
┌──────────────────┐    ┌──────────────────────┐  ┌──────────────────┐
│ View transitions │    │ Detail panel CSS      │  │ "What's New"     │
│ Panel resize     │    │ Touch targets 40px    │  │    toggle mode   │
│   smoothness     │    │ Tooltip positioning   │  │ Panel skeletons  │
│ Contextual empty │    │ Search count overflow │  │ Minimap anim     │
│   states         │    │                       │  │ Dark mode fade   │
└──────────────────┘    └──────────────────────┘  └──────────────────┘
    ~2 sessions              ~1 session               As-needed / V2
```

**Total estimated sessions for P1–P2:** 3 focused sessions.

---

## What NOT to Polish

Explicit non-goals to avoid scope creep:

- **Don't add animations for their own sake.** Every transition must serve a
  purpose (continuity, orientation, feedback).
- **Don't redesign the toolbar layout.** It works. It's clear. Moving things
  around for aesthetics risks confusing returning users.
- **Don't add color gradients to nodes.** The flat color + border encoding is
  clean and readable. Gradients add visual noise without information.
- **Don't add a splash screen or onboarding wizard.** The help panel already
  exists and is comprehensive.
- **Don't optimize for "wow" screenshots.** Optimize for "I can read this graph
  at 9am on my second coffee."
