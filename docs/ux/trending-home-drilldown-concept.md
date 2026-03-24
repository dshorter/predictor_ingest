# Trending as Home + Source Layer Drill-Down (Design Concept)

**Status:** Thinking / pre-design. Do not implement until state management prerequisites
are resolved. See open questions below.

**Origin:** Conversation 2026-03-24. Captures the "money view" framing and the
proposed drill-down flow for future planning.

---

## The Core Idea

The four views are not peers. They have a hierarchy:

```
trending      ← the product (synthesized signal, scored, filtered)
  claims      ← ingredient: asserted relationships with evidence
  dependencies← ingredient: tech/tool dependency graph
  mentions    ← ingredient: raw co-occurrence (noisiest, most voluminous)
```

**Trending is the money view.** Claims, dependencies, and mentions are the provenance
stack — the receipts that explain *why* something is trending. They have many times
more nodes/edges and are overwhelming in their global form.

The current UI treats all four as peer tabs. This undersells what the system does and
buries the signal in the noise.

---

## Proposed Flow

Trending is the default and only entry point. The other three views are not directly
navigable — they are reachable only by drilling down from a specific entity.

```
Trending (home)
  └─ click node → detail panel
       ├─ "14 claims"   → Claims view, scoped to that node's neighborhood (1-2 hops)
       ├─ "83 mentions" → Mentions view, same
       └─ "depends on 6"→ Dependencies view, same
```

When you enter a source layer:
- The anchor node arrives **pre-selected and centered**
- The layout runs on the **neighborhood subgraph only** — not the full global graph
- A **breadcrumb/back affordance** ("← Back to Trending") is always visible
- The **URL reflects state**: `?view=claims&focus=org:openai` — shareable and bookmarkable

Count badges in the detail panel give you a reason to drill: "14 claims" signals
substance; "2 mentions" tells you it's thin. Users who see low counts may choose not
to drill at all.

The source layers never need a global browse mode in the primary UI. If a power user
wants that, it can live at a diagnostic URL, not a first-class nav item.

---

## State Management Prerequisites

This flow requires capabilities the UI does not currently have. These need to be
designed and built before the drill-down pattern is implemented.

### 1. Navigation History (Forward / Back)

A browser-like history stack scoped to the graph session:

- Each navigation action (enter source layer, select node, expand neighborhood) pushes
  a state entry
- Back restores the previous view, focus, zoom level, and filter state
- Forward re-applies if the user backed up
- The browser's native back button should ideally be wired to this stack (via
  `history.pushState`)

This is non-trivial because Cytoscape state (positions, zoom, pan, which nodes are
visible) is not automatically serializable.

### 2. View + Filter State Serialization

To support back/forward and session persistence, the following must be serializable
into a compact URL or storage object:

| State | Notes |
|-------|-------|
| Active view | `trending`, `claims`, `dependencies`, `mentions` |
| Focus entity | `org:openai` or null |
| Neighborhood depth | 1 or 2 hops |
| Zoom + pan | `cy.zoom()`, `cy.pan()` |
| Selected node/edge | ID or null |
| Active filters | min confidence, node types, date range |

The URL approach (`?view=claims&focus=org:openai&depth=1`) is preferable to
localStorage for shareability, but zoom/pan may need to live in session storage to
avoid ugly URLs.

### 3. Session Persistence (Return to Where You Left Off)

Users want to close and return to find the graph where they left it — modulo new data
from pipeline runs.

Design tension: new data may add/remove nodes. The session state must degrade
gracefully when the saved focus entity no longer exists or has changed.

Options to think through:
- **LocalStorage snapshot**: serialize the full state on `beforeunload`, restore on
  load if the graph data hasn't changed (compare export timestamp)
- **URL-only**: rely on the shareable URL — users bookmark what they want to return to
- **Hybrid**: URL for view/focus, localStorage for zoom/pan

The "modulo new data" case needs a decision: when the graph has updated since the
session was saved, do we restore view/focus but reset zoom/pan? Restore everything and
let the user notice changes? Show a "graph updated since your last visit" banner?

---

## Open Questions

1. **Should the source views ever be accessible globally?** As a power-user escape
   hatch (e.g., `?view=mentions`), or never outside drill-down?

2. **Neighborhood depth**: 1 hop vs. 2 hops — 2 hops can explode for high-degree
   nodes (e.g., `org:openai` in mentions). Need a cap or a "expand further" affordance.

3. **Back to trending**: does it restore the exact zoom/pan/selection the user had in
   trending, or just return to the default trending view? Restoring is better UX but
   requires the history stack.

4. **Multi-entity drill-down**: user drills into OpenAI, then from the source layer
   clicks to GPT-5, which also has claim/mention counts. Does the drill-down stack?
   Probably yes, but the breadcrumb needs to handle depth > 1.

5. **Mobile**: the drill-down detail panel assumes a side panel layout. Mobile may need
   a bottom sheet or full-screen takeover for the source layer. Defer to after desktop
   is designed.

---

## Relationship to Existing Docs

- `docs/ux/progressive-disclosure.md` — the existing 4-level hierarchy (Overview →
  Explore → Detail → Evidence) operates *within* a single view. This concept operates
  *across* views. They are complementary, not redundant.
- `docs/ux/delight-backlog.md` — "What's Hot" and guided entry are also trending-first
  patterns; this aligns with that direction.
- `docs/ux/README.md` — implementation guidelines; update when this moves to active
  design.

---

## Next Steps (when ready to act)

1. Decide on state serialization approach (URL vs. localStorage vs. hybrid)
2. Prototype the history stack as a standalone JS module before wiring to Cytoscape
3. Implement `?focus=<id>` URL param support in the existing views as a first step —
   this is useful independently and unblocks the drill-down entry point
4. Design the breadcrumb/back affordance in the toolbar (low visual weight)
5. Add count badges to the detail panel footer (claims N / mentions N) — this can
   ship before the full drill-down is ready and starts training user expectations
