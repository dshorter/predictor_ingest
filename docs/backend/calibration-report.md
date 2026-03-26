# Calibration Report — Design & Auto-Tuning Spec

**Created:** 2026-03-25
**Review date:** 2026-04-02 (Thursday)
**Status:** Phase 1 (report only) deployed; Phase 2 (bounded auto-tuning) pending review

---

## Purpose

The calibration report (`scripts/run_calibration_report.py`) reads daily pipeline
metrics from the database and produces:

1. A rolling signal summary (entity yield, bench ratio, batch latency, orphan edges)
2. Flagged anomalies with severity levels (CRITICAL / WARN / INFO)
3. Concrete parameter suggestions — human-readable, never auto-applied in Phase 1

Run daily after `make daily`:

```bash
make calibration-report DOMAIN=film          # print only
make calibration-report-log DOMAIN=film      # print + log to tuning_log table
```

---

## Signals Monitored

| Signal | Source table | Flag condition |
|--------|-------------|----------------|
| Entity yield drop | `pipeline_runs` | Today >30% below 7-day avg |
| Orphan edge spike | `funnel_stats.drop_reasons` | >100 stripped in one run |
| Feed error streak | `feed_stats` | ≥3 consecutive error days |
| High bench ratio | `doc_selection_log` | >92% of qualified docs benched |
| Batch latency | `batch_jobs` | Median completion >6h |
| Low-yield source | `source_extraction_quality` | Source yield >50% below avg |

---

## tuning_log Table (Phase 2 scaffold)

Suggestions from `--log-suggestions` are written here. In Phase 2, an
auto-apply path can read this table and apply bounded changes.

```sql
CREATE TABLE IF NOT EXISTS tuning_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    domain          TEXT NOT NULL,
    logged_at       TEXT NOT NULL,        -- ISO datetime suggestion was generated
    parameter       TEXT NOT NULL,        -- 'BUDGET', 'similarity_upper_bound', etc.
    signal          TEXT NOT NULL,        -- signal name that triggered this
    severity        TEXT NOT NULL,        -- CRITICAL | WARN | INFO
    observation     TEXT,                 -- human-readable metric description
    suggestion      TEXT,                 -- recommended action
    direction       TEXT,                 -- 'increase' | 'decrease' | NULL
    applied         INTEGER DEFAULT 0,    -- 0=suggested, 1=applied, 2=rejected
    applied_at      TEXT,
    applied_by      TEXT,                 -- 'auto' | 'manual' | NULL
    notes           TEXT                  -- free-form context
);
```

---

## Phase 2 — Bounded Auto-Tuning (Thursday review)

### Parameters eligible for auto-tuning

| Parameter | Location | Allowed range | Max delta/day | Trigger signal |
|-----------|----------|---------------|---------------|----------------|
| `BUDGET` (daily doc cap) | `Makefile` | 20–60 | +5 | bench_ratio >92% for 5d |
| `similarity_upper_bound` | `domain.yaml` | 0.70–0.95 | ±0.05 | orphan rate trend |
| `similarity_lower_bound` | `domain.yaml` | 0.30–0.55 | ±0.05 | merge rate too high/low |

### Parameters that stay manual

| Parameter | Reason |
|-----------|--------|
| Extraction prompts | Too much leverage; silent quality drift is hard to detect |
| `gate_thresholds` | Evidence fidelity gates should only change with deliberate review |
| Feed additions/removals | Requires editorial judgment about source quality |
| `trend_weights` | Affects graph topology; needs visual inspection to validate |

### Auto-apply safety rules (Phase 2)

1. **One parameter per day maximum** — no cascading changes
2. **All changes logged** to `tuning_log` with `applied_by='auto'` before applying
3. **Hard floors/ceilings** enforced — auto-tuner cannot exceed the allowed range
4. **Rollback**: set `applied=2` (rejected) in `tuning_log` and re-run pipeline —
   parameter reads from DB override, not domain.yaml, so rollback is instant
5. **3-day minimum signal window** — no suggestions from fewer than 3 data points
6. **Monotonic guard** — if the same parameter was adjusted yesterday, skip today

---

## Review Checklist for 2026-04-02

- [ ] Review `tuning_log` table — how many suggestions logged in first week?
- [ ] Were any CRITICAL flags triggered? What was the root cause?
- [ ] Bench ratio trend: is 25 docs/day the right budget given batch API cost?
- [ ] Entity yield: is 485 entities/25 docs (~19/doc) representative or a one-day spike?
- [ ] Orphan edge rate: is 331 today vs baseline acceptable?
- [ ] Decide: enable Phase 2 auto-tuning for `BUDGET` parameter only (lowest risk)?
- [ ] Feed audit: `go-into-the-story` and SC Film Commission still erroring?

---

## Operational Notes

- The report uses a 7-day rolling window by default (`--days 7`)
- Requires at least `min_history_days=3` before generating suggestions (avoids noise on day 1)
- CRITICAL suggestions should be actioned same day; WARN within the week; INFO at Thursday review
- The `tuning_log` table is created on first `--log-suggestions` run (safe to run multiple times)
