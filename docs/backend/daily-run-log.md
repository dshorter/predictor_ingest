# Daily Pipeline Run Log

Structured JSON log produced by `scripts/run_pipeline.py` for monitoring pipeline health.

---

## Log Format

One file per day: `data/logs/pipeline_YYYY-MM-DD.json`

```json
{
  "runDate": "2026-02-08",
  "runId": "20260208T060000Z",
  "startedAt": "2026-02-08T06:00:00Z",
  "completedAt": "2026-02-08T06:02:22Z",
  "durationSec": 142.3,
  "status": "success",

  "stages": {
    "ingest": {
      "status": "ok",
      "duration_sec": 28.4,
      "feedsChecked": 7,
      "feedsReachable": 7,
      "newDocsFound": 12,
      "duplicatesSkipped": 4,
      "fetchErrors": 0
    },
    "docpack": {
      "status": "ok",
      "duration_sec": 1.2,
      "docsBundled": 12
    },
    "extract": {
      "status": "ok",
      "duration_sec": 89.5,
      "docsExtracted": 11,
      "entitiesFound": 87,
      "relationsFound": 134,
      "validationErrors": 0,
      "escalated": 0
    },
    "import": {
      "status": "ok",
      "duration_sec": 3.1,
      "filesImported": 11,
      "entitiesNew": 23,
      "entitiesResolved": 64,
      "relations": 134,
      "evidenceRecords": 267
    },
    "resolve": {
      "status": "ok",
      "duration_sec": 1.8
    },
    "export": {
      "status": "ok",
      "duration_sec": 4.2,
      "totalNodes": 1432,
      "totalEdges": 2891
    },
    "trending": {
      "status": "ok",
      "duration_sec": 2.1,
      "trendingNodes": 50,
      "trendingEdges": 83
    }
  }
}
```

### Status values

| Status | Meaning |
|--------|---------|
| `success` | All stages completed without error |
| `partial` | Some non-fatal stages failed; pipeline continued |
| `failed` | A fatal stage (ingest) failed; pipeline aborted |

### Stage status values

| Status | Meaning |
|--------|---------|
| `ok` | Stage completed successfully |
| `error` | Stage failed (includes `error` field with details) |
| `timeout` | Stage exceeded time limit (600s default) |
| `skipped` | Stage was intentionally skipped (e.g., `--skip-extract`) |

**One-liner summary** (printed to stdout for cron capture):
```
OK 2026-02-08: 12 docs, 87 entities, 134 relations | 7/7 feeds | 142.3s
```

---

## Health Check Thresholds

| Check | Healthy | Investigate |
|-------|---------|-------------|
| `status` | `"success"` | `"partial"` or `"failed"` |
| `ingest.feedsReachable` | = `feedsChecked` (7) | Any less means source down |
| `ingest.newDocsFound` | 5-30 typical | 0 = stale or broken feeds |
| `extract.validationErrors` | 0 | > 0 = schema or prompt drift |
| `extract.escalated` | < 30% of docs (typical) | > 50% = cheap model underperforming |
| `import.filesImported` | > 0 | 0 = extraction produced no valid output |
| `durationSec` | < 600 (10 min) | Longer = investigate bottleneck |
| `failedStages` | absent | Present = check stage errors |

---

## Log Size Guidance

Daily summary is ~500-1000 bytes per run.

| Accumulated Size | Status | Notes |
|------------------|--------|-------|
| < 100 KB | Fine | Opens instantly, `jq` parses in ms |
| 100 KB - 1 MB | Fine | Still trivial for any tool |
| 1 - 10 MB | Caution | Text editors slow; `jq` still fast |
| > 10 MB | Too big | Stream parse only |

At one run per day:
- 1 year ~ 365 KB
- 10 years ~ 3.6 MB

No need for log rotation or aggregation infrastructure.

---

## Grep Recipes

Quick ad-hoc troubleshooting without any dependencies.

```bash
# Which days had failures?
grep -l '"status": "failed"' data/logs/pipeline_*.json

# Which days had partial failures?
grep -l '"status": "partial"' data/logs/pipeline_*.json

# Which days had zero new docs?
grep -l '"newDocsFound": 0' data/logs/pipeline_*.json

# Feed outages (fewer than 7 reachable)?
grep -rn '"feedsReachable": [0-6],' data/logs/pipeline_*.json

# Validation errors?
grep -l '"validationErrors": [1-9]' data/logs/pipeline_*.json

# Runs that took over 5 minutes?
grep -E '"durationSec": [3-9][0-9]{2,}' data/logs/pipeline_*.json

# Last 7 days summary
ls -t data/logs/pipeline_*.json | head -7 | xargs grep -h '"runDate"\|"status"\|"newDocsFound"'

# Count new docs per day (last 30 days)
ls -t data/logs/pipeline_*.json | head -30 | xargs grep '"newDocsFound"'

# Which stages failed on a given day?
python -c "
import json, sys
log = json.load(open(sys.argv[1]))
for name, stage in log['stages'].items():
    if stage.get('status') not in ('ok', 'skipped'):
        print(f'{name}: {stage}')
" data/logs/pipeline_2026-02-08.json

# Days with high escalation rate
grep -l '"escalated": [5-9]' data/logs/pipeline_*.json
```

---

## Implementation

The pipeline orchestrator (`scripts/run_pipeline.py`):

1. Creates `data/pipeline.lock` at run start (safe-reboot awareness)
2. Runs each stage as a subprocess, captures stdout/stderr
3. Parses stage output for structured stats
4. On fatal stage failure (ingest), aborts the pipeline
5. On non-fatal failure, records the error and continues
6. Writes `data/logs/pipeline_YYYY-MM-DD.json` on completion
7. Removes `data/pipeline.lock`
8. Prints one-liner summary to stdout

### Usage

```bash
# Full pipeline (all 7 stages, escalation mode by default)
python scripts/run_pipeline.py --copy-to-live

# Skip extraction (Mode B manual workflow)
python scripts/run_pipeline.py --skip-extract --copy-to-live

# Disable escalation (run primary model on all docs with shadow comparison)
python scripts/run_pipeline.py --no-escalate --copy-to-live

# Dry run (show what would execute)
python scripts/run_pipeline.py --dry-run

# Via Makefile
make daily          # full pipeline with --copy-to-live (escalation default)
make daily-manual   # skip extraction, --copy-to-live
```
