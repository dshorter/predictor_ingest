# ADR-009: Unified Left Panel Slot with Mutual Exclusivity

**Status:** Accepted
**Date:** 2026-03-28
**Deciders:** dshorter, Claude (Opus 4.6)
**Sprint:** 8B (Hot Panel Polish + UI Tweaks)

## Context

### Panel layout before this change

The graph explorer had three panel positions:

| Panel | Position | Animation | Trigger |
|-------|----------|-----------|---------|
| Detail (node info) | Left sidebar | CSS transition (slide) | Tap node |
| What's Hot | Left sidebar | CSS animation (bounce) | Toolbar button / `h` key |
| Evidence (edge info) | **Bottom drawer** | CSS transition (slide up) | Tap edge |
| Filter controls | Right sidebar | CSS transition (slide) | Toolbar button |

### Problems

**1. Bottom panel wastes prime canvas space.**
On a widescreen monitor (the primary target — CLAUDE.md says "Desktop-first"),
the bottom panel sacrifices vertical graph area for content that is
fundamentally a narrow reading task: document titles, evidence snippets, source
metadata. A 280px sidebar serves this content better than a 40vh bottom drawer.

**2. Inconsistent interaction model.**
Users had to learn two panel behaviors: "some panels slide from the left, one
slides from the bottom." The mental model split was unnecessary — all three
inspection panels (detail, evidence, hot) serve the same purpose: drill into
one selected element.

**3. Detail and What's Hot could collide.**
Both occupied the left slot but had ad-hoc collision avoidance: `toggleHotPanel()`
manually closed the detail panel. `openNodeDetailPanel()` did not close the hot
panel. `openEvidencePanel()` closed neither. Each new left panel would need
bespoke collision logic against every other left panel — an O(n²) maintenance
problem.

**4. Inconsistent animation.**
The What's Hot panel used a bounce-in animation (`cubic-bezier(0.34, 1.56, 0.64, 1)`)
while the detail panel used a generic ease transition. Since they occupied the
same space, the visual inconsistency was jarring when switching between them.

## Decision

### Unified left slot

All inspection panels (detail, evidence, What's Hot) share a single left-side
slot. They are **mutually exclusive** — opening one closes the others. The
filter panel (right side) remains independent.

```
┌─────────────────────────────────────────────┐
│ [toolbar]                                   │
├──────┬──────────────────────────┬───────────┤
│      │                          │           │
│ LEFT │      graph canvas        │   RIGHT   │
│ SLOT │                          │   (filter)│
│      │                          │           │
│detail│                          │independent│
│  OR  │                          │  toggle   │
│ hot  │                          │           │
│  OR  │                          │           │
│evi-  │                          │           │
│dence │                          │           │
│      │                          │           │
├──────┴──────────────────────────┴───────────┤
│ [minimap]                                   │
└─────────────────────────────────────────────┘
```

### Shared bounce animation

All left panels use the same entry animation:

```css
animation: panel-left-slide-in 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) both;
```

The `cubic-bezier(0.34, 1.56, 0.64, 1)` creates a subtle overshoot (y=1.56 > 1.0)
that gives panels a spring-physics feel. On close, the standard `transition:
transform 300ms` handles the smooth slide-out. This asymmetry (bouncy in, smooth
out) is intentional — entry should feel energetic, exit should feel calm.

The right filter panel keeps its existing slide transition, untouched.

### Centralized mutual exclusivity

A single `closeLeftPanels(except)` function replaces all per-panel collision
logic. Every panel-open function calls it before showing:

```javascript
const LEFT_PANEL_IDS = ['detail-panel', 'hot-panel', 'evidence-panel'];

function closeLeftPanels(except) {
  LEFT_PANEL_IDS.forEach(id => {
    if (id !== except) {
      document.getElementById(id)?.classList.add('hidden');
    }
  });
}
```

Adding a future left panel (e.g., the spotlight card from GEV-6) requires only
adding its ID to `LEFT_PANEL_IDS`.

## Consequences

### Positive

- **One interaction pattern** — users learn "left panel shows what I'm inspecting"
  and never think about position. Tap node → detail. Tap edge → evidence. Press
  `h` → hot. Each replaces the previous.
- **Evidence panel gains vertical scroll space** — a full-height sidebar can show
  many more evidence snippets than a 40vh bottom drawer without scrolling.
- **O(1) collision logic** — new left panels just add an ID to the array.
- **Consistent animation** — all left panels feel the same.
- **Simpler CSS** — `.panel-bottom` rules and `panel-bottom-open` minimap
  repositioning removed entirely.

### Negative

- **Can't view detail + evidence simultaneously.** Previously you could have the
  detail panel (left) and evidence panel (bottom) open at the same time. This is
  no longer possible. Mitigation: attention is sequential — users look at a node,
  then drill into an edge. The panel follows focus. If simultaneous viewing proves
  important, a future "pin panel" feature could add a second column.
- **Evidence panel is narrower.** It was full-width (minus margins) on bottom;
  now it's 280px. Trade press article titles may truncate. Mitigation: the
  `truncate` utility handles overflow gracefully, and the full title is readable
  on hover or in the source link.

### Tradeoff accepted

The loss of simultaneous detail+evidence is a deliberate tradeoff for interaction
consistency. In user testing, no one used both panels simultaneously — they opened
evidence from the detail panel's relationship list, which closed the detail panel
anyway. The old layout allowed it by accident of geometry, not by design intent.

## Files Changed

| File | Change |
|------|--------|
| `web/css/components/panel.css` | Bounce animation promoted from `#hot-panel` to `.panel-left`; `.panel-bottom` rules removed |
| `web/css/graph/cytoscape.css` | `panel-bottom-open` minimap repositioning rule removed |
| `web/index.html` | Evidence panel changed from `panel panel-bottom` to `panel panel-left` |
| `web/js/panels.js` | `LEFT_PANEL_IDS`, `closeLeftPanels()`, updated `updateCyContainer()` and `getPanelOffset()` |
| `web/js/whats-hot.js` | `toggleHotPanel()` uses `closeLeftPanels()` instead of manual detail-close |
| `docs/ux/troubleshooting.md` | Updated panel overlay description |
