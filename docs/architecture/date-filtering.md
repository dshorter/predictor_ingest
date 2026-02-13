# Date Filtering Architecture

Date filtering controls which entities and relations appear in graph exports
and in the web client. It operates on **article publication dates**
(`documents.published_at`), not on pipeline fetch timestamps.

---

## Why Published Date, Not Fetch Date

The pipeline may crawl articles days or weeks after they are published (e.g.,
backfilling a new RSS feed, re-running after a crawl outage, or importing a
historical archive). If we used `fetched_at`, these late arrivals would appear
as "new" even though the underlying event happened earlier. Using the article's
own publication date ensures:

- **Trend scores reflect real-world timing.** A velocity spike corresponds to
  when articles were actually written, not when our cron job ran.
- **Retroactive imports don't distort the graph.** Backfilling 200 articles
  from last month puts them in the correct 30-day window, rather than flooding
  today's view.
- **Client date filtering matches user mental model.** When a user selects
  "last 30 days," they mean articles published in the last 30 days.

### Where the Semantic Is Enforced

| Location | What It Does |
|----------|--------------|
| `schemas/sqlite.sql` — `entities.first_seen` / `last_seen` | Comments document that these derive from `published_at` |
| `src/resolve/__init__.py` — `resolve_extraction()` | Docstring requires `observed_date` be the publication date |
| `src/db/__init__.py` — `list_entities_in_date_range()` | Filters on `first_seen` / `last_seen` (publication-derived) |
| `src/db/__init__.py` — `list_relations_in_date_range()` | JOINs `documents.published_at` |
| `src/graph/__init__.py` — `GraphExporter._get_relations()` | JOINs `documents.published_at` when date params are set |

---

## Default Window: 30 Days

The default date window is **30 days**, defined in one place on the backend
and mirrored in one place on the frontend:

| Layer | Location | Variable |
|-------|----------|----------|
| Backend (Python) | `src/config/__init__.py` | `DEFAULT_DATE_WINDOW_DAYS = 30` |
| Frontend (JS) | `web/js/app.js` | `const DEFAULT_DATE_WINDOW_DAYS = 30` |

When the dataset grows and 30 days yields too many or too few nodes, change
these two values. The CLI scripts (`run_export.py`, `run_trending.py`) also
accept a `--days` flag to override per-run.

### Why 30?

- Matches the `mention_count_30d` trend scoring window, so the graph shows
  exactly the entities that contribute to the 30-day mention count.
- Large enough to show trends and connections that develop over weeks.
- Small enough to keep node counts in the "render all" tier (< 500 nodes)
  during early operation with 3 RSS sources at ~10–20 articles/day.

---

## How Date Filtering Flows Through the Stack

### 1. Export Pipeline (Backend)

```
run_export.py
  --days 30         ←  DEFAULT_DATE_WINDOW_DAYS
  --start-date ...  ←  optional explicit override
  --end-date ...    ←  defaults to --date (today)
        │
        ▼
GraphExporter.export_all_views(
    output_dir,
    start_date="2026-01-14",
    end_date="2026-02-13",
)
        │
        ├─► _get_entities(start_date, end_date)
        │     WHERE last_seen >= start AND first_seen <= end
        │
        ├─► _get_relations(start_date, end_date)
        │     JOIN documents d ON r.doc_id = d.doc_id
        │     WHERE d.published_at >= start AND d.published_at <= end
        │
        └─► _build_meta(view, elements, start_date, end_date)
              Writes meta.dateRange into the JSON file
```

Every exported JSON file now contains a `meta` block:

```json
{
  "meta": {
    "view": "claims",
    "nodeCount": 127,
    "edgeCount": 243,
    "exportedAt": "2026-02-13T12:00:00Z",
    "dateRange": { "start": "2026-01-14", "end": "2026-02-13" }
  },
  "elements": { ... }
}
```

### 2. Web Client (Frontend)

```
loadGraphData(url)
  │
  ├─► handleGraphMeta(meta)
  │     Stores meta.dateRange in AppState.dateRange
  │     Displays date range in toolbar (#date-range-info)
  │
  └─► applyDefaultDateFilter(filter)
        Computes start = end - 30 days
        Calls filter.setDateRange(start, end)
        Calls filter.apply()
        Activates the "30d" preset button
```

The user can then change the window via the filter panel preset buttons
(7d / 30d / 90d / All). The "Apply" button re-runs `filter.apply()`, which
hides/shows nodes based on their `firstSeen` and `lastSeen` data attributes.

---

## Entity Date Semantics

An entity is considered **active in a window** if its observation range
overlaps the window:

```
Entity:     [first_seen ============= last_seen]
Window:              [start ---- end]
                        ↑ overlap → included
```

Formally: `last_seen >= start_date AND first_seen <= end_date`.

Entities with NULL dates are **included** (conservative — don't drop data
just because we lack date metadata).

---

## Relation Date Semantics

A relation is included if the **document that sourced it** was published
within the window. This uses a JOIN:

```sql
SELECT r.*
FROM relations r
JOIN documents d ON r.doc_id = d.doc_id
WHERE d.published_at >= ?   -- start_date
  AND d.published_at <= ?   -- end_date
```

This means the same entity pair can have a relation visible in one time
window and hidden in another, depending on which articles support it.

---

## CLI Usage

### Export with default 30-day window

```bash
python scripts/run_export.py
# Equivalent to: --days 30 --date $(date +%Y-%m-%d)
```

### Export all data (no date filter)

```bash
python scripts/run_export.py --days 0
```

### Export a specific date range

```bash
python scripts/run_export.py --start-date 2025-12-01 --end-date 2026-01-31
```

### Trending with custom window

```bash
python scripts/run_trending.py --days 14
```

---

## Test Coverage

| Test file | Tests | What they cover |
|-----------|-------|-----------------|
| `tests/test_db.py` — `TestDateRangeQueries` | 9 tests | `list_entities_in_date_range`, `list_relations_in_date_range`, NULL handling, combined type+date filters |
| `tests/test_graph.py` — `TestDateFiltering` | 5 tests | `export_all`, `export_claims` with date range, `meta` block generation, `export_all_views` date pass-through |

Run them with:

```bash
PYTHONPATH=src pytest tests/test_db.py::TestDateRangeQueries tests/test_graph.py::TestDateFiltering -v
```

---

## Future Considerations

- **Sliding window in daily cron.** The `Makefile` `export` target should
  pass `--days $(DEFAULT_DATE_WINDOW_DAYS)` so exports are always scoped.
- **Multiple windows per export.** A future enhancement could export
  7d, 30d, and 90d views simultaneously for the client to switch between
  without re-fetching.
- **Position stability across windows.** When V2 preset layout lands,
  node positions should be computed on the full dataset but filtered views
  should preserve those positions (don't re-layout just because a node
  fell out of the window).
