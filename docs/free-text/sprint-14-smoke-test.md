# Sprint 14 Smoke Test Runbook

Self-contained reference for validating the Backend Movers
implementation (PR #256) on the VPS. Use during the SSH smoke test;
fill in the Findings section as you go.

**Branch:** `claude/trends-view-analysis-otaeu`
**Created:** 2026-05-19. Keep as reference for future smoke tests
(Sprint 14B will reuse the structure).

---

## Setup (one-time, skip if already done)

```bash
git fetch origin claude/trends-view-analysis-otaeu
git checkout claude/trends-view-analysis-otaeu
pip install -e .   # safe to re-run; no-op if already installed
```

---

## Phase 0 — Bootstrap stale domains (one-time, optional)

> **CLOSED — do not rerun (2026-07-19, Sprint 20.1).** This bootstrap was
> executed 2026-05-19 and its synthetic rows were deleted per ADR-010 D5
> (receipts: `diagnostics/synthetic-trend-history-dump-20260719.tar.gz`).
> Operator decision, Sprint 20: synthetic trend data will not be created
> again, and if it ever were, it would never coexist with real data.
> `trend_history` now carries an `epoch` column (1 = pre-restart, 2 = post);
> windows never span epochs. The SQL below is preserved as history only.

Skip if every domain already has recent `trend_history`. As of
2026-05-19, three of four domains lack the data Movers needs to
produce non-empty output:

| Domain         | trend_history rows | latest run_date            |
|----------------|-------------------:|----------------------------|
| ai             |                  0 | —                          |
| biosafety      |                  0 | —                          |
| film           |             98,228 | 2026-04-06 (43 days stale) |
| semiconductors |             36,264 | 2026-05-11 (live)          |

To exercise the Movers *infrastructure* across all four domains
without waiting for the underlying extraction pipelines to catch up,
synthesize two `trend_history` snapshots per stale domain (today and
today−7d) via pure SQL. Zero LLM cost; no `run_trending.py`
invocation.

### Why pure SQL and not `run_trending.py`?

`TrendScorer._save_trend_history` (src/trend/__init__.py:368-372)
skips any entity with `mention_count_30d == 0`. ai/biosafety/film
have zero documents in the last 30 days, so every entity is filtered
out and nothing is persisted — `trending.json` gets exported but
`trend_history` stays empty. The SQL below sidesteps that gate by
inserting synthesized rows directly, with a deterministic provenance
(specific run_date) that makes cleanup trivial.

### Bootstrap SQL (per stale domain)

```bash
DOMAIN=ai                                          # change: ai | biosafety | film
TODAY=2026-05-19
PRIOR=2026-05-12

sqlite3 data/db/$DOMAIN.db <<SQL
-- Step 1: synthesize TODAY snapshot from existing entities + MENTIONS counts.
INSERT INTO trend_history (
  entity_id, run_date, mention_count_7d, mention_count_30d,
  velocity, novelty, bridge_score, trend_score, in_trending_view,
  novelty_decay_lambda, min_mentions_for_velocity,
  corpus_entity_count, velocity_gated
)
SELECT
  e.entity_id,
  '$TODAY' AS run_date,
  COALESCE(m.cnt, 0) AS mention_count_7d,
  COALESCE(m.cnt, 0) AS mention_count_30d,
  0 AS velocity, 0 AS novelty, 0 AS bridge_score,
  COALESCE(m.cnt, 0) * 1.0 AS trend_score,
  CASE WHEN COALESCE(m.cnt, 0) >= 3 THEN 1 ELSE 0 END AS in_trending_view,
  0.05 AS novelty_decay_lambda,
  3    AS min_mentions_for_velocity,
  (SELECT COUNT(*) FROM entities) AS corpus_entity_count,
  0    AS velocity_gated
FROM entities e
LEFT JOIN (
  SELECT target_id, COUNT(*) AS cnt
  FROM relations
  WHERE rel = 'MENTIONS'
  GROUP BY target_id
) m ON m.target_id = e.entity_id
WHERE COALESCE(m.cnt, 0) > 0;

-- Step 2: clone TODAY into PRIOR with a deterministic rank perturbation,
-- so Movers has a non-trivial rank_delta / is_new signal.
INSERT INTO trend_history (
  entity_id, run_date, mention_count_7d, mention_count_30d,
  velocity, novelty, bridge_score, trend_score, in_trending_view,
  novelty_decay_lambda, min_mentions_for_velocity,
  corpus_entity_count, velocity_gated
)
SELECT
  entity_id,
  '$PRIOR' AS run_date,
  mention_count_7d, mention_count_30d,
  velocity, novelty, bridge_score,
  trend_score * (0.7 + (abs(random()) % 60) / 100.0) AS trend_score,
  0 AS in_trending_view,
  novelty_decay_lambda, min_mentions_for_velocity,
  corpus_entity_count, velocity_gated
FROM trend_history
WHERE run_date = '$TODAY';
SQL
```

### What this proves and what it doesn't

- **Proves:** Movers exporter, schema validation, and the JSON
  contract all work across every domain's entity-type taxonomy and
  for both populated and previously-empty `trend_history` tables.
- **Does NOT prove:** the qualitative "does Movers earn its keep on
  film?" question from the Status doc. The synthetic prior snapshot
  is a perturbed clone with no real entity churn under it, so
  `rank_delta` and `is_new` will look mechanically correct but
  carry no real signal.

### Cleanup

Drops both synthesized snapshots across all three domains in one shot:

```bash
TODAY=2026-05-19
PRIOR=2026-05-12
for d in ai biosafety film; do
  sqlite3 data/db/$d.db "
    DELETE FROM trend_history
    WHERE run_date IN ('$TODAY', '$PRIOR');
  "
done
```

For ai + biosafety (zero pre-existing rows) the DELETE leaves the
table empty again. For film, only the two new run_dates are dropped;
the legitimate 2026-04-06 and earlier rows are untouched.

---

## Phase 1 — Inspect available domain data

Movers reads from `trend_history`. Check which domains have recent
trending runs:

```bash
for d in ai semiconductors film biosafety; do
  echo "=== $d ==="
  sqlite3 data/db/$d.db "SELECT
    (SELECT COUNT(*) FROM entities) as entities,
    (SELECT COUNT(*) FROM trend_history) as trend_rows,
    (SELECT MAX(run_date) FROM trend_history) as latest_run
  ;" 2>/dev/null || echo "no db"
done
```

**Expected:** at least one domain with `trend_rows > 0` and a recent
`latest_run`. As of the test date, only **semiconductors** had recent
data; other domains are empty or stale.

---

## Phase 2 — Run the exporter

```bash
make movers DOMAIN=semiconductors
```

**Expected output (two lines):**

```
Exported Movers view to data/graphs/semiconductors/<today>/movers.json
  - N rows (window: 7 days)
```

- `N > 50` is the success signal (Movers includes more than the
  trending top-50, which is the point).
- `N == 0`: `trend_history` for that domain has fewer than 1 day of
  data, or `_most_recent_run_date` found nothing. Not a bug, just
  insufficient input.
- Traceback / error: paste it in Findings.

---

## Phase 3 — Inspect content

```bash
python3 - <<'EOF'
import json, glob
path = sorted(glob.glob('data/graphs/semiconductors/*/movers.json'))[-1]
d = json.load(open(path))
m = d['meta']
print(f"file: {path}")
print(f"rowCount: {m['rowCount']}, window: {m['rank_window_days']}d, "
      f"range: {m['dateRange']['start']}..{m['dateRange']['end']}")

print('--- top 5 by current_rank ---')
for r in d['rows'][:5]:
    print(f"  #{r['current_rank']:>3} {r['label'][:40]:<40} "
          f"({r['type']:<8}) Δ={r['rank_delta']} new={r['is_new']} "
          f"vel={r['velocity_raw']} src={r['distinct_sources_7d']}")

print('--- 3 is_new rows (just-appeared) ---')
news = [r for r in d['rows'] if r['is_new']][:3]
for r in news:
    print(f"  #{r['current_rank']:>3} {r['label'][:40]:<40} "
          f"first_seen={r['first_seen']} mc7={r['mention_count_7d']}")

print('--- 3 biggest climbers (rank_delta desc, hiding top 50) ---')
climbers = sorted(
    [r for r in d['rows'] if r['rank_delta'] and not r['in_trending_view']],
    key=lambda r: -r['rank_delta'])[:3]
for r in climbers:
    print(f"  {r['label'][:40]:<40} prior={r['rank_prior']} "
          f"→ now={r['current_rank']} (Δ={r['rank_delta']:+d})")
EOF
```

**What's good:**
- **Top 5:** established semi names — TSMC, NVIDIA, ASML, AMD, Intel,
  etc. They dominate because they have high `trend_score`. This is the
  sanity reference.
- **`is_new` rows present.** At least a few entities without prior
  trend_history. If *every* row is `is_new`, the prior-run-date lookup
  failed — investigate.
- **Climbers list non-empty.** Entities not in today's top-50 but with
  substantial positive `rank_delta`. This is the headline Movers signal.

**What's bad:**
- Top 5 looks like random / unfamiliar entities → trend_score ordering
  is wrong. Cross-check with `data/graphs/semiconductors/<today>/trending.json`
  to see if rankings agree.
- All `velocity_raw` is null → mentions join isn't finding rows. Check
  that `relations` table has `rel='MENTIONS'` rows for entities in the
  movers list.

---

## Phase 4 — Optional: full daily integration

Tests that the Makefile / `run_pipeline.py` correctly inserts the
movers stage into the daily flow. **This publishes to `web/data/`**,
so backup first if conservative:

```bash
cp -r web/data/graphs/live web/data/graphs/live.backup-pre-movers
make daily DOMAIN=semiconductors
ls -la web/data/graphs/live/semiconductors/movers.json
```

**Expected:** `movers.json` appears in the live folder alongside the
other view JSONs. Existing UI on the deployed site is unchanged (no
page consumes `movers.json` yet — that's Sprint 15).

Rollback if needed:

```bash
rm -rf web/data/graphs/live
mv web/data/graphs/live.backup-pre-movers web/data/graphs/live
```

---

## Phase 5 — Optional: chatter source verification

Confirms Bluesky/Reddit feeds keep ingesting but skip extraction
(the 14.1 + 14.2 behavior change):

```bash
sqlite3 data/db/semiconductors.db "
  SELECT source_type, status, COUNT(*) as docs
  FROM documents
  WHERE fetched_at >= date('now', '-7 day')
  GROUP BY source_type, status
  ORDER BY source_type, status;
"
```

**Expected after running with the new policy:**
- Bluesky / Reddit rows have status `cleaned` only — they never advance
  to `extracted` or any extraction-related state.
- RSS rows have a mix of statuses including `extracted`.

If Bluesky/Reddit rows show `extracted` status from runs **before** PR
#256 merged, that's historical and fine. New ingests after merge should
stop at `cleaned`.

---

## Phase 6 — Optional: film proof-point

Film is the qualitative proof that Movers solves a real problem. Film
has high entity churn (every week brings new productions and festival
entries that appear once and never recur). Movers should surface those.

Requires recent trend_history for film. If empty:

```bash
make trending DOMAIN=film
make movers DOMAIN=film
```

Then re-run the Phase 3 inspection script (swap the glob path).
Compare:
- **Ratio of `is_new` rows** — film should have substantially more than
  semis (high churn).
- **Top by rank_delta** — film should show entities that wouldn't be
  recognisable from the trending top-50.

If film's Movers looks much like semis (low is_new, persistent top), the
new lens isn't earning its keep. Worth a longer conversation before
merging.

---

## Findings

### Phase 0 — Bootstrap (executed 2026-05-19)

| Domain    | trend_history before | TODAY (2026-05-19) | PRIOR (2026-05-12) |
|-----------|---------------------:|-------------------:|-------------------:|
| ai        | 0                    | 6,899              | 6,899              |
| biosafety | 0                    | 2,553              | 2,553              |
| film      | 98,228 @ 2026-04-06  | 8,641              | 8,641              |

Quirk surfaced: the synthesis inserts the *same* entity set into both
TODAY and PRIOR, so `is_new=0` for every row in bootstrapped domains.
Real `is_new` signal requires either real churn (semis) or a
synthesis variant that randomly excludes ~10% from PRIOR. Acceptable
for an infrastructure smoke; not for the qualitative proof-point.

### Phase 1 — Data availability (pre-bootstrap)

| Domain         | entities | trend_rows | latest_run            |
|----------------|---------:|-----------:|-----------------------|
| ai             |    6,902 |          0 | —                     |
| semiconductors |    5,052 |     36,264 | 2026-05-11 (live)     |
| film           |    8,641 |     98,228 | 2026-04-06 (stale)    |
| biosafety      |    2,559 |          0 | —                     |

### Phase 2 — Exporter runs (all four domains, post-bootstrap)

| Domain         | rowCount | source data                  |
|----------------|---------:|------------------------------|
| semiconductors |    3,468 | real (2026-05-11 → 2026-05-19) |
| ai             |    6,899 | synthetic                    |
| biosafety      |    2,553 | synthetic                    |
| film           |    8,641 | synthetic                    |

All four passed schema validation. The schema fix
(`fix(schema): open movers.json entityType for domain-specific types`)
was the blocker; it has been committed.

### Phase 3 — Content inspection

| Domain         | top entity            | type        | is_new | climbers |
|----------------|-----------------------|-------------|-------:|---------:|
| semiconductors | Tom's Hardware (Org)  | Org/Company |    869 |      491 |
| ai             | Simons Foundation     | Org         |      0 |    3,416 |
| biosafety      | CDC                   | Org         |      0 |    1,260 |
| film           | Project Hail Mary     | Production  |      0 |    4,322 |

- **Semis top-5** had Intel/Nvidia/TSMC at #2/#3/#5 (expected), but
  publishers `Tom's Hardware` (#1) and `Future US` (#4) ranked
  unreasonably high — pre-existing extraction noise, not a Movers
  bug. Backlog item.
- **Film** correctly surfaced domain-specific types `Production`
  and `Agency` through the schema, confirming the multi-domain
  taxonomy works end-to-end.
- **Climbers** for synthetic domains all look ~similar in magnitude
  because the perturbation is the only signal — expected.

### Decision

- [x] Schema fix landed (commit `c387ddc`)
- [x] Bootstrap proven against all four domains
- [ ] Real film proof-point — deferred, needs fresh extractions
- [ ] Cleanup bootstrap rows after Sprint 14B / 15 frontend work
      can reference live data

### Phase 4 — Daily integration (if run)

- `movers.json` in live folder:
- Any pipeline stage errors:
- UI unchanged on existing pages:

### Phase 5 — Chatter verification (if run)

- Bluesky status distribution (last 7 days):
- Reddit status distribution (last 7 days):
- RSS for comparison:

### Phase 6 — Film proof-point (if run)

- Film `rowCount`:
- Ratio of `is_new` rows (film vs semis):
- Qualitative impression — does Movers earn its keep on film:

### Decision

### Original decision checkboxes (kept for reference)

- [ ] Merge PR #256 as-is
- [ ] Fix something before merge — describe:
- [ ] Roll back / discard
- [ ] Defer merge, more investigation needed — describe:
