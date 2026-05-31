# Movers page — wireframe v0

**Status:** Signed off — coding can begin. All five open decisions confirmed 2026-05-23.
**Author:** Claude (assisted) — 2026-05-23
**Sprint:** [15 — Movers Frontend V1](../project-plan.md#sprint-15-—-movers-frontend-v1)
**Design parent:** [movers-and-focus-mode.md §Workstream B](../plans/movers-and-focus-mode.md)
**Data contract:** [movers-and-focus-mode.md Appendix A](../plans/movers-and-focus-mode.md#appendix-a)
**Preset definitions:** [movers-vs-current-landscape.md](../free-text/movers-vs-current-landscape.md)

This document locks the layout, columns, presets, and URL state decisions
*before* any code is written. Sprint 15 items 15.1, 15.3, 15.4, 15.6, and
15.9 shape themselves around this wireframe.

---

## Scope

A standalone page at `/movers.html?domain={slug}` that consumes
`movers.json` and renders the full scored entity population for a domain
through five named lenses + a Custom mode.

Out of scope (deferred to Sprint 16 or later): universal "View in graph"
deep-link, LLM narrative display, mobile-tuned layout, watchlists.

---

## Page layout — desktop (1280×800 reference)

```
+--------------------------------------------------------------------------------+
|  TOOLBAR  (sticky)                                                             |
|  +------------------+-----------------------+----------------+--------------+  |
|  | Film Trend Graph | Domain (v)  As of: 5/23 |  <- Graph    |  ? Help     |  |
|  +------------------+-----------------------+----------------+--------------+  |
+--------------------------------------------------------------------------------+
|  PRESET CHIPS  (sticky under toolbar)                                          |
|  +------------------------------------------------------------------------+    |
|  | [Biggest climbers *] [Just appeared] [Fastest accelerators]            |    |
|  | [Emerging consensus] [Sanity reference] [(gear) Custom]                |    |
|  +------------------------------------------------------------------------+    |
|  description strip: "Entities that rose the most ranks in the last 7 days."    |
+--------------------------------------------------------------------------------+
|                                                                                |
|  TABLE (sticky header)                                                         |
|  +--+---------------------------+---------+--------+------+--------+-------+   |
|  | #| Entity                    | Delta   | 7d     | 30d  | src 7d | first |   |
|  +--+---------------------------+---------+--------+------+--------+-------+   |
|  |51| (o) Org   A24 Films       |  ^65    |  17    |  42  |   5    | 56d   |   |
|  |52| (o) Tech  Volumetric capt |  NEW    |   4    |   4  |   3    | 4d *  |   |
|  |53| (o) Per   Jane Schoenbrun |  ^28    |  11    |  22  |   4    | 71d   |   |
|  |..|                           |         |        |      |        |       |   |
|  +--+---------------------------+---------+--------+------+--------+-------+   |
|                                                                                |
|  virtualized scroll — more rows loaded on scroll                               |
|                                                                                |
|  WHEN ROW CLICKED -> detail panel slides in from RIGHT (320px wide)            |
+--------------------------------------------------------------------------------+
```

## Detail panel — right slide-in, 320px wide

Slides in from the right edge when a row is clicked. Replaces the
existing detail content if open; closes via X, Esc, or background click.

```
                              +----------------------------------+
                              |  X  Volumetric capture           |
                              |  (o) Tech       (*) NEW          |
                              +----------------------------------+
                              |  RANK                            |
                              |   Today  Prior  Delta            |
                              |     52     -    NEW              |
                              +----------------------------------+
                              |  MENTIONS                        |
                              |  7d: 4   30d: 4                  |
                              |  Distinct sources (7d): 3        |
                              +----------------------------------+
                              |  TIMELINE                        |
                              |  First seen: 2026-05-19          |
                              |  4 days ago                      |
                              +----------------------------------+
                              |  RECENT SOURCES                  |
                              |  (favicon) nofilmschool.com      |
                              |  (favicon) deadline.com          |
                              |  (favicon) indiewire.com         |
                              +----------------------------------+
                              |  [ View in graph -> ]            |
                              |   (only when in_trending_view)   |
                              +----------------------------------+
```

When `in_trending_view: false`, the "View in graph" button is replaced
with the graceful note from the plan: *"Not currently in Current
Landscape — coming in a future update."* (Universal deep-link arrives in
Sprint 16 via on-demand neighborhoods.)

---

## Column decisions

Default visible columns. Hidden columns are exposed via Custom mode.

| Column      | Field                    | Width  | Notes                                                                         |
|-------------|--------------------------|--------|-------------------------------------------------------------------------------|
| `#`         | `current_rank`           | 48px   | Right-aligned, monospace                                                      |
| Entity      | type badge + `label`     | flex   | Type badge reuses `.badge-type-*` from existing graph; aliases hidden in V1   |
| Delta rank  | `rank_delta`             | 80px   | Rendered as `^65` / `v3` / `—` / **NEW** badge (when `is_new: true`)          |
| 7d          | `mention_count_7d`       | 60px   | Right-aligned                                                                 |
| 30d         | `mention_count_30d`      | 60px   | Right-aligned                                                                 |
| src 7d      | `distinct_sources_7d`    | 60px   | Right-aligned                                                                 |
| first       | `days_since_first_seen`  | 80px   | `4d` / `56d` — gold-star indicator when ≤ 14d (Just-appeared visual cue)      |

**Hidden by default, available in Custom mode:** `velocity_raw`,
`trend_score`, `first_seen` (raw ISO date), entity aliases. These are
power-user fields and would crowd the default view.

---

## Preset chip group

Six chips in a sticky row. Active chip uses the same flame-orange
treatment as the focus chip (visual continuity with Sprint 14B).
Default selection is **Biggest climbers** unless URL specifies
otherwise.

Each preset is a `{sort, filter, description}` tuple. The description
renders in the strip below the chips so the user knows what they're
looking at.

| Chip                       | Sort                              | Filter                          | Description strip                                                                       |
|----------------------------|-----------------------------------|---------------------------------|-----------------------------------------------------------------------------------------|
| **Biggest climbers** (default) | `rank_delta` desc             | `current_rank > 50`             | "Entities that climbed the most ranks in the last 7d."                                  |
| **Just appeared**          | `days_since_first_seen` asc       | `days_since_first_seen <= 14`   | "Entities first seen in the last two weeks."                                            |
| **Fastest accelerators**   | `velocity_raw` desc               | `mention_count_7d >= 3`         | "Entities with the steepest mention growth (min 3 mentions to filter noise)."           |
| **Emerging consensus**     | `distinct_sources_7d` desc        | `current_rank > 50`             | "Entities being picked up across many independent sources."                             |
| **Sanity reference**       | `mention_count_7d` desc           | (none)                          | "Top entities by raw 7d mention count — sanity check vs. the other lenses."             |
| **(gear) Custom**          | user-set dropdown                 | user-set filter pills           | (no fixed description)                                                                  |

### Custom mode controls

When the Custom chip is active, two control rows appear above the table:

1. **Sort dropdown** — every numeric column + first_seen + velocity_raw + trend_score
2. **Filter pills** — togglable:
   - `Hide top 50` — `current_rank > 50`
   - `First seen ≤ N` — number input, default 14
   - `Entity type: {Org, Person, Tech, ...}` — multi-select chips
   - `Min 7d mentions` — number input

All sort/filter state mirrors to the URL (see below).

### Rank-delta column rendering rules

| Value of `rank_delta` | Display       | Color                     |
|-----------------------|---------------|---------------------------|
| `rank_delta > 0`      | `↑{n}`        | green                     |
| `rank_delta < 0`      | `↓{n}`        | red                       |
| `rank_delta == 0`     | `—`           | gray                      |
| `is_new: true` (and `rank_delta` is null) | `NEW` badge | flame-orange (matches focus chip) |

---

## URL state

The page URL is the canonical state. Reload should be lossless.

| Param      | Values                                                                                          | Default            |
|------------|-------------------------------------------------------------------------------------------------|--------------------|
| `domain`   | `ai` / `film` / `semiconductors` / `biosafety`                                                  | `film`             |
| `preset`   | `biggest-climbers` / `just-appeared` / `fastest-accelerators` / `emerging-consensus` / `sanity` / `custom` | `biggest-climbers` |
| `sort`     | column key (Custom mode only)                                                                   | preset-derived     |
| `filter`   | comma-separated `key:value` pairs (Custom mode only) — e.g. `type:Org,mentions_7d_min:5`        | preset-derived     |
| `entity`   | canonical entity id — when present, opens detail panel for that entity on load                  | (none)             |

### Examples

- `/movers.html?domain=film` — film domain, default preset (Biggest climbers)
- `/movers.html?domain=semiconductors&preset=just-appeared` — semis just-appeared
- `/movers.html?domain=ai&preset=custom&sort=trend_score&filter=type:Org,mentions_7d_min:5` — custom mode
- `/movers.html?domain=film&entity=production:project_hail_mary` — opens with detail panel for Project Hail Mary

---

## Navigation entry point

Add a Movers button to the existing `index.html` toolbar between the
**What's Hot** flame icon and the zoom controls. Lucide icon:
`trending-up`. Tooltip: `Movers`. Clicking opens `/movers.html?domain={current_domain}`
in the same tab.

Add a return-link from the Movers toolbar back to the graph view:
`<- Graph` button on the left side of the Movers toolbar.

---

## Empty states

| Condition                                  | Render                                                                                                       |
|--------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| `rowCount: 0`                              | Centered card: "No movers data for {domain} yet. Run `make daily DOMAIN={domain}` to populate."             |
| All rows filtered out by current preset    | "No entities match this preset for {domain}. Try **Sanity reference** or **Custom mode**."                  |
| **Film "Just appeared" specifically**      | Film has zero `is_new` rows because the trend_history was bootstrapped (no fresh entities). The empty state should NOT read like a bug. Add an explicit copy variant: *"Film domain hasn't ingested new docs recently. Try Biggest climbers to see rank movement on existing entities."* |
| Domain not configured                      | "Unknown domain: {slug}." with link back to graph view.                                                      |

---

## Mobile

V1 ships with **graceful degradation only**. A tuned mobile layout is a
separate effort.

- Detail panel becomes a fullscreen overlay (not slide-in) on screens <768px wide.
- Preset chips horizontally scroll on narrow screens.
- Columns get progressively dropped at narrower breakpoints in this priority order: `src 7d` → `30d` → `first`. `#`, `Entity`, `Delta rank`, and `7d` are always visible.
- The mobile redirect from `index.html` does NOT apply to `movers.html` — Movers serves the same page on mobile and desktop.

---

## Pagination / scroll strategy

Film has 8,641 rows; semiconductors will be similar order. Naïvely
rendering every `<tr>` into the DOM crawls. Decision:

**Virtual scroll** — render only ~50 rows around the visible viewport,
recycle DOM nodes on scroll. The selected preset's sort order is
applied once when the preset changes; the virtual scroller indexes
into the sorted array.

Implementation: a thin custom virtualizer in `web/js/movers.js` (no
new dependency). Existing dashboard.html / ontology.html don't have
this need, so no shared component to reuse.

---

## Decisions locked in this pass

| Decision                              | Choice                                                          | Rationale                                                                                       |
|---------------------------------------|-----------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| Detail panel position                 | **right slide-in**                                              | Matches dashboard convention; rank column stays visible                                         |
| Preset chips above OR below toolbar   | **below**                                                       | Sticky toolbar stays clean; chips relate to table content                                       |
| Default preset                        | **Biggest climbers**                                            | Per design doc — the headline daily-moves view                                                  |
| Pagination strategy                   | **virtual scroll**                                              | 8K+ rows make DOM-everything untenable                                                          |
| Mobile                                | **graceful degrade**                                            | Detail panel becomes fullscreen overlay; chips horizontally scroll; tuned mobile is V2          |
| Domain switcher                       | **reuse `domain-switcher.js`**                                  | Single source of truth for `KNOWN_DOMAINS`                                                      |
| "View in graph" deep-link             | **opens `index.html` in same tab** with `?domain=X&select=<id>` | Add `select=` URL param to graph page (sibling to Sprint 14B's `?focus=`)                       |
| Search box                            | **NOT in V1**                                                   | Custom mode + entity type filter cover the use case; search creeps scope                        |
| `?entity=<id>` deep-link              | **in V1**                                                       | Opens detail panel on page load; useful for shareable links                                     |
| Sort column for NEW rows in "Biggest climbers" | NEW rows sort to the bottom of the list                | They have `rank_delta: null`; sorting them with climbers would mix metaphors. Other presets surface them. |

---

## Sprint 15 items shaped by this wireframe

After signoff, these items can be picked up:

- **15.1** `web/movers.html` shell — per page layout above
- **15.3** Table component — per column decisions
- **15.4** Preset chip group — per preset table
- **15.5** Custom-mode controls — per Custom mode section
- **15.6** Detail side-panel — per detail panel section
- **15.7** Deep-link to graph — per URL state
- **15.9** Basic responsive — per mobile section

Items that don't depend on the wireframe (can start in parallel):

- **15.2** Data loader — purely JSON ingestion
- **15.8** Navigation entry points — toolbar buttons
- **15.10** Playwright smoke test — fixture-based, written alongside impl
- **15.11** Manual QA — runs after impl

---

## Signoff record (2026-05-23)

All five decisions confirmed. Locked in for V1 implementation.

| # | Question | Decision |
|---|----------|----------|
| 1 | Detail panel placement | **Right slide-in, 320px wide.** Matches dashboard convention; rank column stays visible behind it. |
| 2 | Default preset on first visit | **Biggest climbers.** Per design doc — the headline daily-moves view. |
| 3 | Default visible columns | **The 7 drafted above** (`#`, Entity, Δ rank, 7d, 30d, src 7d, first). `velocity_raw`, `trend_score`, raw `first_seen`, and aliases remain Custom-mode-only. |
| 4 | "View in graph" UX for non-top-50 | **Graceful note.** Button absent for non-trending entities; replaced with "Not currently in Current Landscape — coming in a future update." Universal deep-link defers to Sprint 16. |
| 5 | NEW badge color | **Flame-orange.** Matches focus chip; reinforces the "you're seeing emerging signal" visual language. Distinct from the green `.new` graph-node treatment by design. |

Subsequent changes to these decisions should be tracked here as
amendments rather than overwrites, so reviewers can see the history of
the V1 frame.
