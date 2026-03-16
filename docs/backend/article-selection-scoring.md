# Article Selection Scoring — Design & Change Log

**Last updated:** 2026-03-16

This document describes how the pipeline decides **which articles to extract**
when daily ingestion exceeds the extraction budget. All scoring is CPU-based
(zero LLM cost) and runs inside `src/doc_select/__init__.py`.

For **source selection** (which feeds to subscribe to), see
[source-selection-strategy.md](../source-selection-strategy.md). For
**post-extraction quality gates** (validating LLM output), see
[research/extract-quality-analysis.md](../research/extract-quality-analysis.md).

---

## How It Works

The pipeline ingests 30-60 articles per day across 10-14 feeds. The extraction
budget is typically 20 articles (stretch to 25 for high-quality overflow). The
selection algorithm:

1. **Scores** every candidate on 5 weighted signals (see below).
2. **Drops** candidates below `MIN_QUALITY_THRESHOLD` (0.20).
3. **Guarantees feed representation** — every feed gets at least 1 slot (if it
   has a qualifying doc), so no source is silently starved.
4. **Fills remaining budget** from the global quality ranking.
5. **Stretches** up to `stretch_max` (default 25) if remaining candidates score
   above `STRETCH_QUALITY_THRESHOLD` (0.55).
6. **Benches** qualified overflow — articles that scored well but got bumped by
   the budget cap are saved for backfill on light days (see Bench section).

---

## Scoring Signals

### Current weights (as of 2026-03-16)

| Signal | Weight | What it measures |
|--------|--------|-----------------|
| **word_count** | 30% | Article length in the extractable sweet spot |
| **metadata** | 20% | Title + published-date presence |
| **source_tier** | 20% | Feed tier (primary/secondary/echo) |
| **signal_type** | 15% | Feed signal category |
| **recency** | 15% | Article age relative to run date |

All signals produce a 0.0–1.0 score. The combined score is a weighted sum
clamped to [0.0, 1.0].

### Signal details

**word_count** — Article length quality curve:
- 0–200 words: linear ramp from 0 → 0.5 (too short for useful extraction)
- 200–800 words: linear ramp from 0.5 → 1.0
- 800–3000 words: 1.0 (ideal range)
- 3000+ words: gentle log decay, never below 0.7

**metadata** — Binary checks:
- Has title: +0.5
- Has published_at date: +0.5

**source_tier** — From `feeds.yaml` tier field:
- Tier 1 (primary/original research): 1.0
- Tier 2 (secondary/aggregator): 0.6
- Tier 3 (echo/mainstream): 0.3

**signal_type** — From `feeds.yaml` signal field:
- `primary`: 1.0
- `commentary`: 0.8
- `community`: 0.6
- `echo`: 0.4

**recency** — Age relative to the pipeline run date:
- 0–3 days: 1.0 (full credit)
- 3–7 days: linear decay from 1.0 → 0.5
- 7–14 days: linear decay from 0.5 → 0.3
- 14+ days: 0.3 (floor — old articles still have some value)
- No date available: 0.4 (modest penalty)

---

## Bench System

When the daily budget is exceeded, overflow articles that scored above
`MIN_QUALITY_THRESHOLD` are saved to the `bench` table for later backfill.

**How it works:**
- **Busy days** (candidates > budget): After selection, qualified overflow is
  written to the bench with their quality score and an expiry timestamp.
- **Light days** (candidates < budget): Remaining budget slots are filled from
  the bench, highest quality first. Bench entries are removed once picked.
- **Expiry**: Bench entries expire after **5 days** (`BENCH_EXPIRY_DAYS`).
  Expired entries are cleaned up at the start of each run.

**Why 5 days?** Trend detection value decays quickly. A 5-day window is long
enough to survive a quiet weekend but short enough that backfilled articles are
still timely for graph signals.

**Schema** (`schemas/sqlite.sql`):
```sql
CREATE TABLE bench (
  doc_id TEXT PRIMARY KEY,
  quality_score REAL NOT NULL,
  scored_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);
```

---

## Thresholds

| Constant | Value | Purpose |
|----------|-------|---------|
| `DEFAULT_BUDGET` | 20 | Target articles per daily run |
| `DEFAULT_STRETCH_MAX` | 25 | Hard cap when stretching for quality |
| `MIN_QUALITY_THRESHOLD` | 0.20 | Below this, article is excluded entirely |
| `STRETCH_QUALITY_THRESHOLD` | 0.55 | Minimum score for stretch slots |
| `BENCH_EXPIRY_DAYS` | 5 | Days before bench entries are discarded |

---

## Change Log

### 2026-03-16 — Recency boost + bench backfill

**Problem:** The scoring system had no time dimension. A 3-week-old article with
good metadata and word count scored identically to a fresh one. On busy days,
qualified articles were simply dropped with no second chance.

**Changes:**

1. **Added recency signal** (15% weight). Fresh articles (0–3 days) get full
   credit; score decays linearly through two bands (3–7 days → 0.5, 7–14 days
   → 0.3) and floors at 0.3. Articles with no published date get 0.4 (better
   than very old, worse than dated-and-recent).

2. **Rebalanced weights** to accommodate recency:
   - `word_count`: 40% → **30%** (still the strongest single signal)
   - `source_tier`: 25% → **20%**
   - `signal_type`: 15% → 15% (unchanged)
   - `metadata`: 20% → 20% (unchanged)
   - `recency`: new at **15%**

3. **Added bench system.** `select_for_extraction()` now returns
   `(selected, overflow)`. Overflow is persisted to the `bench` table with a
   5-day expiry. On light days, `build_docpack.py` pulls from the bench to fill
   remaining budget slots before writing the bundle.

**Rationale:** For trend detection, timeliness is a first-class concern — an
article about a new model release is far more valuable on day 1 than day 10.
The bench ensures that budget constraints don't permanently lose good articles;
they get a second chance within the recency window.

### 2026-02-28 — Initial implementation

Four-signal scoring (word_count 40%, metadata 20%, source_tier 25%,
signal_type 15%) with budget/stretch selection and per-feed representation
guarantees. No time dimension, no overflow persistence.
