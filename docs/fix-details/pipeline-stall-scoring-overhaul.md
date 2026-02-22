# Pipeline Debugging: Daily Process Stall & Quality Scoring Overhaul

**Date:** 2026-02-22
**Scope:** `scripts/build_docpack.py`, `scripts/run_pipeline.py`, `src/extract/__init__.py`
**Branch:** `claude/debug-daily-process-AVGNa`

---

## Symptoms

The daily pipeline was stuck in a loop processing the same 3 TechCrunch articles
on every run. Despite 368 documents sitting in `status='cleaned'` and 12 RSS feeds
being checked, zero new articles were being extracted. The extraction log showed:

```
Loaded 3 documents from data/docpacks/daily_bundle_2026-02-21.jsonl
  [1/3] 2026-02-21_techcrunch_ai_b78885cd: SKIPPED (exists)
  [2/3] 2026-02-21_techcrunch_ai_00b2cb02: SKIPPED (exists)
  [3/3] 2026-02-21_techcrunch_ai_f2dd956f: SKIPPED (exists)
```

Separately, the quality scoring for the cheap model (gpt-5-nano) was outputting
suspiciously high scores (q=0.82–1.00), causing zero escalations to the specialist
model (claude-sonnet-4-5-20250929) even on clearly shallow extractions.

---

## Root Cause 1: Docpack Date Filter Stranding Documents

### The mechanism

`build_docpack.py` filters documents by **exact publication date**:

```sql
WHERE status = 'cleaned'
  AND published_at IS NOT NULL
  AND substr(published_at, 1, 10) = ?   -- e.g., '2026-02-21'
```

This query only returns documents published **on the pipeline's target date**.
The 368 cleaned documents had `published_at` values from older dates (days to
weeks prior). They entered the system via RSS feed ingestion but their publication
dates didn't match any subsequent daily run. Result: permanently stranded in
`status='cleaned'`.

### The cascade

1. **Docpack stage** finds 0 docs for today's date → prints diagnostic, returns 0
2. **Extract stage** receives the docpack file path (`daily_bundle_2026-02-21.jsonl`)
   which still exists from a **previous run** containing 3 already-extracted docs
3. Extractor loads the stale file → all 3 are SKIPPED (extraction `.json` already exists)
4. Next pipeline run → same cycle repeats

### Fix: Backlog fallback with 6-month cutoff

After the date-specific query, `build_docpack.py` now runs a second query for any
remaining `status='cleaned'` docs from other dates, up to `max_docs`:

```sql
WHERE status = 'cleaned'
  AND text_path IS NOT NULL
  AND (published_at IS NULL OR substr(published_at, 1, 10) != ?)
  AND COALESCE(substr(published_at, 1, 10), substr(fetched_at, 1, 10)) >= ?  -- 180-day cutoff
ORDER BY fetched_at DESC
```

Today's articles get priority; the remaining capacity fills with backlog.
Documents older than 6 months are excluded — stale content isn't worth the API cost.

`run_pipeline.py` was also updated to track the docpack count and skip the extract
stage entirely when docpack bundles 0 docs (preventing stale-file processing).

---

## Root Cause 2: RSS Deduplication Showing 0 New Articles

### Analysis

The pipeline log showed 883 duplicates skipped across 11 reachable feeds with 0
new articles. Investigation via `diagnose_feeds.py` confirmed the dedup mechanism
is **filesystem-based** (`rss.py:200`):

```python
if skip_existing and raw_path.exists() and text_path.exists():
    skipped += 1
    continue
```

This is correct — if both files exist, the article was already fetched. The 883
entries were legitimately already in the system from earlier runs. The specific
pipeline run at 03:51 UTC was early enough that feeds hadn't rotated to include
new articles.

### Diagnostic tool

Added `scripts/diagnose_feeds.py` for on-VPS debugging. Shows per-feed breakdown
of entries currently in the RSS feed vs what already has files on disk, with date
distribution of existing articles.

```bash
python scripts/diagnose_feeds.py
```

---

## Root Cause 3: Quality Scoring Too Lenient for Cheap Model

### The problem

The quality scoring function (`score_extraction_quality`) used thresholds so low
that the cheap model trivially maxed every component:

| Component | Old Threshold | Cheap Model Typical | Score |
|-----------|--------------|-------------------|-------|
| Entity density | 3.0/1K chars | 5+ | **1.0** (capped) |
| Evidence coverage | 80% asserted with evidence | 100% | **1.0** |
| Avg confidence | 0.6 | ~0.9 (flat) | **1.0** (capped) |
| Relation/entity ratio | 0.1 (1 per 10 entities!) | 0.5+ | **1.0** (capped) |
| Tech terms | ≥1 | 1+ | **1.0** |

Combined: 0.82–1.00. Escalation threshold: 0.6. Result: **zero escalations.**

### The fix: raised thresholds + new signals

**Threshold changes:**

| Component | Old | New | Rationale |
|-----------|-----|-----|-----------|
| Entity density target | 3.0 | 5.0 | Proportional scoring, not binary |
| Confidence target | 0.6 | 0.85 | Cheap models cluster at 0.9 |
| Relation/entity ratio | 0.1 | 0.5 | 1:2 is realistic for good extraction |
| Tech terms min | 1 | 2 | AI articles should have ≥2 |

**New signals:**

1. **Relation type diversity (25% weight):** Count distinct semantic relation
   types (excluding MENTIONS). Cheap models emit 2-3 types (USES_TECH, CREATED).
   Good models use 6+ distinct types. Target: 6 types for full score. This is the
   hardest signal for a cheap model to game.

2. **Confidence variance penalty:** If confidence stddev < 0.05 and avg > 0.8,
   apply 30% penalty. A model outputting 0.9 for everything isn't calibrating —
   it's guessing confidently.

**New weights:**

| Component | Old Weight | New Weight |
|-----------|-----------|-----------|
| Entity density | 30% | 15% |
| Evidence coverage | 25% | 15% |
| Avg confidence | 20% | 10% |
| Connectivity (ratio) | 15% | 20% |
| **Diversity (new)** | — | **25%** |
| Tech terms | 10% | 15% |

**Before/After on realistic cheap model output:**

| Scenario | Old Score | New Score | Escalates? |
|----------|----------|----------|------------|
| 9 semantic, 3 types, flat confidence | **1.00** | **0.73** | No (borderline) |
| 4 semantic + 5 MENTIONS, 2 types | ~0.85 | **0.58** | **Yes** |
| 10 semantic, 10 types, varied confidence | 1.00 | **0.97** | No |

---

## Files Changed

| File | Change |
|------|--------|
| `scripts/build_docpack.py` | Backlog fallback with 180-day cutoff |
| `scripts/run_pipeline.py` | Track docpack count; skip extract on empty |
| `scripts/diagnose_feeds.py` | New diagnostic tool for RSS dedup |
| `src/extract/__init__.py` | Quality scoring overhaul: thresholds, diversity, variance penalty |

## Related Documentation

- [docs/llm-selection.md](../llm-selection.md) — Escalation mode architecture and cost model
- [docs/backend/daily-run-log.md](../backend/daily-run-log.md) — Pipeline log format and health thresholds
- [docs/architecture/date-filtering.md](../architecture/date-filtering.md) — Date handling in the pipeline
- [docs/source-selection-strategy.md](../source-selection-strategy.md) — Feed tier model and coverage targets
