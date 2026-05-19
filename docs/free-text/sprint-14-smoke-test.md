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

*(fill in as you go)*

### Phase 1 — Data availability

| Domain | entities | trend_rows | latest_run |
|--------|----------|-----------|-----------|
| ai | | | |
| semiconductors | | | |
| film | | | |
| biosafety | | | |

### Phase 2 — Semis exporter run

- `rowCount`:
- Errors / warnings:

### Phase 3 — Content inspection

- Top 5 look right? (TSMC/NVIDIA/etc. expected):
- Number of `is_new` rows visible in sample:
- Notable climbers:
- Anything unexpected:

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

- [ ] Merge PR #256 as-is
- [ ] Fix something before merge — describe:
- [ ] Roll back / discard
- [ ] Defer merge, more investigation needed — describe:
