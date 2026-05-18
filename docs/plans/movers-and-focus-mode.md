# Movers + Graph Focus Mode — Implementation Plan

*Companion to [docs/free-text/movers-vs-current-landscape.md](../free-text/movers-vs-current-landscape.md), which captures the design conversation. That doc is the source of substance and rationale; this doc is the actionable plan.*

*Created: 2026-05-10*

---

## Status / Next Action

*Last updated: 2026-05-10*

**Planning phase complete.** All four sprints are defined in
[`docs/project-plan.md`](../project-plan.md) (Sprints 14 / 14B / 15 / 16).
The design rationale lives in
[`docs/free-text/movers-vs-current-landscape.md`](../free-text/movers-vs-current-landscape.md).

**Tracking PR:** #255 (merge gate for planning artifacts; #254 was the
initial design + plan).

### Ready to start now

- **Sprint 14 — Backend Movers** — all decisions locked (see §"Before A"
  below). `movers.json` schema in Appendix A.
- **Sprint 14B — Locked-neighborhood focus mode** — client-only,
  independent of Sprint 14. Can ship in parallel.

### Gated

- **Sprint 15 — Movers Frontend V1** — execution-gated on a UI
  wireframe pass (column layout, preset chip placement, detail panel
  positioning). Items 15.1 / 15.3 / 15.4 / 15.6 / 15.9 shape to the
  wireframe; other items can begin earlier with mock data.
- **Sprint 16 — Universal Movers deep-link** — waits for 14B + 15 to
  ship first.

### Open human-action items

- **Wireframe pass for Sprint 15** — cannot be done by an agent. Even a
  hand-drawn napkin referencing the visual idiom of `dashboard.html` /
  `ontology.html` is enough to unblock the wireframe-dependent items.

### Recently completed

- Locked the three "Before A" open items (PR #255)
- Added `movers.json` schema as Appendix A (PR #255)
- Drafted Sprints 14 / 14B / 15 / 16 in project-plan.md (PR #255)

---

## Overview

Two related features being planned together:

1. **Movers** — a new domain-agnostic view exposing the full scored entity
   population as a sortable / filterable table, surfacing emerging entities
   that don't break into the top-50 "Current Landscape" graph. Renames the
   existing "trending" view to "Current Landscape" by convention (no schema
   change; terminology only).

2. **Graph Focus Mode** — a new graph interaction mode where focus on an
   entity is an explicit, persistent state. Independently justified (fixes
   a pre-existing neighborhood-navigation pain point); also the connective
   tissue for Movers row deep-links into the graph.

Both build on existing infrastructure. The domain model, schemas, and
pipeline are not disturbed — this is additive work at the export and UI
tiers. See the freeform doc's "Does Movers break the domain model?" and
"Is there a treasure trove" sections for the rationale.

---

## Workstreams

Three discrete workstreams. A and C1 can ship in parallel; B depends on A;
C2 is a follow-on that improves Movers UX but is not blocking.

| ID | Workstream | Depends on | Blocking for |
|---|---|---|---|
| **A** | Backend Movers | — | B |
| **B** | Movers Frontend V1 | A | — |
| **C1** | Locked-neighborhood focus mode (client-only) | — | C2 |
| **C2** | On-demand neighborhood endpoint + Movers deep-link | C1, A | — |

---

### Workstream A — Backend Movers

Produce a new export artifact and the chatter-source policy change that
makes Movers' velocity signal honest.

**In scope:**

- New `scripts/run_movers.py` — reads `trend_history`, computes rank Δ
  over a configurable window (default 7d), emits `movers.json` with the
  column set defined in the freeform doc's "Movers columns" section.
- Output lands at `data/graphs/{domain}/{date}/movers.json` and is
  published to `web/data/graphs/live/{domain}/movers.json` via the
  existing `copy-to-live` flow.
- Source-type registry change in `src/ingest/dispatch.py` (or a new
  config block): map `source_type → { extract: bool }`. Set
  `extract: false` for `bluesky` and `reddit`. Tied to source_type, not
  individual feeds (see freeform doc "Chatter source types").
- `src/doc_select/` skips docs whose source_type is non-extracting —
  they're still ingested, they just never enter the extraction budget.
- New `make movers` target in the Makefile; insert after `trending`,
  before `copy-to-live` in `make daily`.
- Schema entry for `movers.json` in `schemas/` (or extension of an
  existing schema).

**Out of scope (defer):**

- LLM-written Movers narratives (cheap to add later as a `--narratives`
  flag on `run_movers.py`).
- V2 length / density filter for chatter sources — V1 is blanket
  ingest-only for chatter source types.
- Stored `rank` column on `trend_history` — default to computing via
  `ROW_NUMBER() OVER (ORDER BY trend_score DESC)` at query time. Revisit
  if performance demands.

**Tests:**

- Unit: rank Δ math, just-appeared entities (no historical rank → "NEW"
  marker, not numeric Δ), source-type registry behavior, empty
  `trend_history` corner case.
- Integration: `make movers DOMAIN=ai` produces a valid `movers.json`
  passing schema validation. Smoke run for film domain (see acceptance).

**Acceptance:**

- `make daily DOMAIN={ai,semiconductors,film,biosafety}` produces
  `movers.json` with the documented column set.
- Schema-validated output.
- Film domain produces meaningfully different rankings under Movers than
  under Current Landscape — this is the proof the new lens works. Manual
  sanity check; not a hard automated criterion.
- Bluesky and Reddit feeds continue to ingest documents (visible in
  `feed_stats`) but contribute zero extraction tokens.

**Estimated size:** Moderate. Most of the substrate exists; the work is
glue code + a new export script + the source-type registry. ~400-600
LOC including tests.

---

### Workstream B — Movers Frontend V1

A standalone page exposing the Movers table. No focus-mode dependency.

**In scope:**

- New page `web/movers.html` (and JS in `web/js/movers.js`).
- Domain-aware via `?domain=<slug>` URL param. Reuses
  `web/js/domain-switcher.js` and its `KNOWN_DOMAINS` registry.
- Table component rendering the columns from the freeform doc.
- Preset dropdown with the five named presets from the freeform doc, plus
  a "Custom" mode that exposes sort + filter controls separately.
- Inline detail side-panel when a row is clicked: entity label, type,
  mentions, top sources, sample evidence snippets, links to source docs.
- "View in graph" link on rows where the entity is currently in top 50
  (deep-links to `index.html?domain=<slug>` and selects the node via
  existing `navigateToNode` codepath). For entities not in top 50, the
  link is absent or shows a graceful "Not currently in Current Landscape
  — coming in a future update" note. Universal deep-link arrives in C2.
- Navigation entry point — link from `web/index.html` (and dashboard?)
  to the new Movers page. Keep it visible but unobtrusive.
- Playwright smoke test using the existing self-contained harness
  pattern (see `docs/testing/playwright-guide.md`).

**Out of scope (defer):**

- Graph focus mode integration (C2).
- LLM narratives display (waits for Movers narratives to exist).
- Mobile-optimized layout — basic responsive only for V1. Mobile-tuned
  Movers is a separate effort.
- "Watchlist" / user-saved presets — explicit non-goal.

**Tests:**

- Playwright: page loads, preset switching works, table renders rows,
  click row opens detail panel, click "View in graph" deep-links
  correctly.
- Manual QA: each preset surfaces *something interesting* in AI,
  semiconductors, and especially film. Film is the qualitative
  proof-point — if Movers doesn't make film domain feel useful, V1 has
  shipped without its main justification.

**Acceptance:**

- Page loads `movers.json` for the selected domain.
- All five presets behave as documented.
- Custom mode allows arbitrary sort + filter compositions.
- Row click opens detail panel; "View in graph" works for top-50
  entities.
- Playwright smoke test passes.
- Manual sanity check on all four domains — particularly film.

**Estimated size:** Moderate to large. Table component is the bulk of the
work. ~800-1200 LOC including tests.

---

### Workstream C1 — Locked-neighborhood focus mode (client-only)

Pure UX improvement to the existing graph page. No backend changes; no
new data. Independently justified — addresses a pre-existing pain point
where clicking edges in neighborhood view drops the user back into
full-graph spaghetti.

**In scope:**

- New graph mode: explicit focus state with a focused entity + 1-hop
  neighborhood rendered.
- Focus chip / breadcrumb in the UI showing "Focused: {entity label}"
  with an explicit close affordance.
- Click semantics in focus mode: clicking a peripheral node *expands*
  focus to include it (default — addresses the user's original pain
  point of losing siblings in spaghetti). Esc key or chip close button
  exits focus mode.
- URL state: `?focus=<entity_id>` persists focus across reload. No
  focus param = full graph (current behavior).
- Visual treatment for "focused vs. unfocused" — leverages existing
  dimming infrastructure (`.neighborhood-dimmed` class or similar).
- Entry point: focus mode is entered by an explicit gesture
  (right-click → "Focus on this entity," or a dedicated button on the
  node detail panel). Plain left-click keeps current transient highlight
  behavior — don't break existing muscle memory.

**Out of scope (defer):**

- Multi-entity focus accumulation ({X, Y, Z} as focused set).
- On-demand neighborhood fetching for entities outside trending.json
  — C1 only works on entities already on the canvas. Universal focus
  is C2.

**Tests:**

- Playwright: enter focus, click peripheral node (focus expands), exit
  focus (returns to full graph), URL param round-trip.

**Acceptance:**

- User can navigate between connected nodes in focus mode without
  reverting to the full graph.
- The pre-existing pain point (clicking edge between multiply-connected
  nodes drops to spaghetti) is demonstrably fixed.
- Existing transient-highlight click behavior unchanged.

**Estimated size:** Small to moderate. All client-side, ~300-500 LOC
including tests.

---

### Workstream C2 — On-demand neighborhood endpoint + universal Movers deep-link

Makes Movers row → graph navigation work for *any* entity, not just the
top-50 ones already in trending.json.

**In scope:**

- New static export or endpoint serving 1-hop neighborhood for any
  entity_id. Two options:
  - **Static fan-out:** export per-entity neighborhood files at build
    time (`web/data/graphs/live/{domain}/neighborhoods/{entity_id}.json`).
    Simple, cacheable, no server. Cost: many small files. Probably the
    right call given the static-hosting model.
  - **Dynamic endpoint:** small backend service exposing
    `/neighborhood/{domain}/{entity_id}`. More flexible, requires
    hosting infra. Probably wrong for this project.
- Movers row "View in graph" link works universally — clicking deep-links
  to `index.html?domain=<slug>&focus=<entity_id>`. Graph page loads the
  on-demand neighborhood file, enters focus mode (C1).
- Reasonable cap on neighborhood size (e.g., top N neighbors by edge
  weight if neighborhood is huge).

**Out of scope (defer):**

- 2-hop or deeper neighborhood pre-export — only 1-hop in V2.
- Selective on-demand loading triggered by click within focus mode
  (i.e., "expand to also include X's neighbors"). Would require a
  per-click fetch; reasonable later but not V2.

**Tests:**

- Backend: neighborhood file generation script produces expected files
  for known fixture entities.
- Frontend Playwright: Movers row → graph → focus mode for an entity
  *not* in top 50.

**Acceptance:**

- Movers row "View in graph" link works for any entity in the domain.
- Graph enters focus mode showing the entity + its 1-hop neighbors.
- Page reload with `?focus=<id>` round-trips correctly.

**Estimated size:** Moderate. Most of the complexity is in deciding the
static-fan-out file structure and bounding the file count. ~400-600 LOC
including tests.

---

## Sequencing

The recommended order:

1. **Phase 1 — Parallel:** A (backend Movers) and C1 (locked-neighborhood)
   ship together. Independent, no shared files.
2. **Phase 2:** B (Movers frontend V1) — once A's `movers.json` exists.
   Can start during phase 1 with a fixture file if useful.
3. **Phase 3:** C2 — closes the loop. Universal "View in graph" from
   Movers. Best done after B is stable so the deep-link UX can be
   shaped against real data.

Each phase ships independent value:

- After phase 1: graph UX win + standalone Movers data feed.
- After phase 2: full Movers experience with graph integration for the
  top-50 case.
- After phase 3: universal Movers ↔ graph navigation.

Nothing is wasted if you stop after any phase.

---

## Open items to resolve before each workstream

**Before A:** *(decided 2026-05-10 — no further discussion needed)*

- Window length — **default 7d**, configurable via `--window-days` flag
  on `run_movers.py`.
- Rank Δ for just-appeared entities — **`is_new: true` flag in the row;
  `rank_delta` is null; UI renders a "NEW" badge instead of a numeric Δ.**
- Stored `rank` column vs. `ROW_NUMBER` — **compute via
  `ROW_NUMBER() OVER (ORDER BY trend_score DESC)` at query time. Do not
  add a `rank` column to `trend_history`.** Revisit only if query
  performance demands it.
- `movers.json` schema — **see Appendix A below for the field-level
  contract.** Any new field added during implementation must be appended
  to that schema.

**Before B:**

- Page navigation entry point — toolbar link from index.html? dashboard
  link? both?
- Detail panel behavior on mobile — collapse / overlay / not shown?
  (Defer if mobile is out of scope for V1.)

**Before C1:**

- Entry gesture — right-click menu? dedicated button? recommended:
  button on node detail panel (least disruptive).
- Click behavior in focus mode — expand vs. swap vs. pin. Recommended:
  expand (matches original pain point).

**Before C2:**

- Static fan-out vs. dynamic endpoint — recommended: static fan-out.
- Per-domain file count budget — sets the cap on which entities get
  neighborhood files. Probably: every entity that's ever been in
  `trend_history`. Numbers to be confirmed during impl.

---

## Out of scope (V1 of everything above)

These came up in the design conversation and are deliberately deferred:

- LLM-written Movers narratives (later, as a `--narratives` flag on
  `run_movers.py`).
- V2 length / density filter for chatter source extraction — V1 is
  blanket ingest-only for `bluesky` and `reddit`.
- Multi-entity focus accumulation in graph focus mode.
- Cross-domain Movers view (same entity moving in multiple domains).
- Removing or reworking the existing "What's Hot" panel — keep until
  Movers stabilizes, then revisit.
- Mobile-optimized Movers layout.
- Renaming "trending" → "Current Landscape" in code (terminology change
  is conventional; code references can rename opportunistically).

---

## Cross-cutting concerns

**Domain-agnostic boundary** — `src/` stays domain-agnostic. The
chatter source-type registry, `run_movers.py`, and graph focus mode all
go in `src/` and `web/`; no domain-specific logic. Per-domain weights
or thresholds (if any) belong in `domains/<slug>/domain.yaml`.

**Tests** — `tests/test_grep_audit.py` enforces the domain boundary. New
code must pass it. New backend tests follow the existing unit / network
/ llm_live marker pattern. New frontend tests use the Playwright
self-contained harness pattern from `docs/testing/playwright-guide.md`.

**Documentation** — after implementation, update CLAUDE.md's "Active
Domains," "Repository Layout," and "Developer Workflow" sections as
needed. The freeform working doc stays as historical context; this plan
gets folded into operational state once shipped.

---

## Appendix A — `movers.json` schema

Authoritative field-level contract for the Movers export. One file per
domain per export, written to:

- `data/graphs/{domain}/{date}/movers.json` (per-day snapshot)
- `web/data/graphs/live/{domain}/movers.json` (published live copy)

### Top-level structure

```json
{
  "meta": { ... },
  "rows": [ { ... }, { ... }, ... ]
}
```

### `meta` object

| Field | Type | Required | Description |
|---|---|---|---|
| `view` | string | ✓ | Literal `"movers"` |
| `domain` | string | ✓ | Domain slug (`ai`, `film`, `semiconductors`, `biosafety`) |
| `rank_window_days` | integer | ✓ | Window for rank Δ calculation (default 7) |
| `rowCount` | integer | ✓ | Number of entries in `rows` |
| `exportedAt` | string (ISO 8601) | ✓ | UTC timestamp of export |
| `dateRange.start` | string (ISO date) | ✓ | Earliest `first_seen` represented |
| `dateRange.end` | string (ISO date) | ✓ | Export date |
| `scoring.novelty_decay_lambda` | number | ✓ | Config snapshot from `domain.yaml` |
| `scoring.min_mentions_for_velocity` | integer | ✓ | Config snapshot from `domain.yaml` |

### `rows[]` element

Each row represents one scored entity. Sorted by `current_rank` ascending
in the file; the client re-sorts per preset.

| Field | Type | Required | Nullable | Description |
|---|---|---|---|---|
| `entity_id` | string | ✓ | no | Canonical ID (`org:rivian`, `tech:cowos`, etc.) |
| `label` | string | ✓ | no | Display label |
| `type` | string | ✓ | no | Entity type enum (`Org`, `Person`, `Tool`, `Model`, `Dataset`, `Benchmark`, `Paper`, `Repo`, `Tech`, `Topic`, `Event`, `Location`, `Program`, `Other`) |
| `current_rank` | integer | ✓ | no | 1-indexed rank by today's `trend_score` |
| `rank_prior` | integer | ✓ | yes | Rank `rank_window_days` ago. Null if entity had no `trend_history` row that day. |
| `rank_delta` | integer | ✓ | yes | `rank_prior - current_rank` (positive = climbed). Null when `rank_prior` is null. |
| `is_new` | boolean | ✓ | no | True iff `rank_prior` is null. Drives the "NEW" UI badge. |
| `velocity_raw` | number | ✓ | yes | Uncapped 7d / prior-7d mention ratio. Null when undefined (no prior-window mentions). |
| `mention_count_7d` | integer | ✓ | no | From `trend_history.mention_count_7d`. |
| `mention_count_30d` | integer | ✓ | no | From `trend_history.mention_count_30d`. |
| `first_seen` | string (ISO date) | ✓ | no | From `entities.first_seen`. |
| `days_since_first_seen` | integer | ✓ | no | `dateRange.end - first_seen`, in days. |
| `distinct_sources_7d` | integer | ✓ | no | Count of distinct source feeds mentioning this entity in last 7 days (count via join on `mentions` × `documents.source_id`). |
| `in_trending_view` | boolean | ✓ | no | True iff the entity is in today's Current Landscape top-N. Drives the "View in graph" link visibility in V1. |
| `trend_score` | number | ✓ | no | The composite score from `TrendScorer` (kept for sortable column and cross-view sanity reference). |

### Example row

```json
{
  "entity_id": "org:rivian",
  "label": "Rivian",
  "type": "Org",
  "current_rank": 75,
  "rank_prior": 140,
  "rank_delta": 65,
  "is_new": false,
  "velocity_raw": 8.5,
  "mention_count_7d": 17,
  "mention_count_30d": 42,
  "first_seen": "2026-03-15",
  "days_since_first_seen": 56,
  "distinct_sources_7d": 5,
  "in_trending_view": false,
  "trend_score": 0.412
}
```

### Just-appeared entity example

```json
{
  "entity_id": "tech:retentive_attention",
  "label": "Retentive Attention",
  "type": "Tech",
  "current_rank": 88,
  "rank_prior": null,
  "rank_delta": null,
  "is_new": true,
  "velocity_raw": null,
  "mention_count_7d": 4,
  "mention_count_30d": 4,
  "first_seen": "2026-05-06",
  "days_since_first_seen": 4,
  "distinct_sources_7d": 3,
  "in_trending_view": false,
  "trend_score": 0.218
}
```

### Empty-export shape

If no entities qualify (fresh DB, etc.), the file is still written with
`rowCount: 0` and an empty `rows` array. The client should render an
empty-state, not error.

### Validation

A JSON Schema mirror of this contract should live at
`schemas/movers.json` and be validated as part of the `run_movers.py`
export step (matching the convention of the existing four views).

### Forward compatibility

Adding new fields to either `meta` or `rows[]` is allowed without a
schema version bump *only if* all clients tolerate unknown fields
(current client should be written to do so). Removing or renaming a
field is a breaking change and requires coordination with the frontend.
