# Daily Pipeline Run Log

Lightweight summary stats for smoke-testing each pipeline run.

---

## Log Format

One file per day: `data/logs/pipeline_YYYY-MM-DD.json`

```json
{
  "runDate": "2026-02-08",
  "runId": "20260208T060000Z",
  "durationSec": 142,
  "status": "success",

  "ingest": {
    "feedsChecked": 3,
    "feedsReachable": 3,
    "newDocsFound": 12,
    "duplicatesSkipped": 4,
    "fetchErrors": 0
  },

  "clean": {
    "docsProcessed": 12,
    "docsSucceeded": 11,
    "docsFailed": 1,
    "avgTextLength": 2847
  },

  "extract": {
    "docsExtracted": 11,
    "entitiesFound": 87,
    "relationsFound": 134,
    "validationErrors": 0
  },

  "export": {
    "totalNodes": 1432,
    "totalEdges": 2891,
    "newNodesAdded": 23,
    "newEdgesAdded": 56
  },

  "deltas": {
    "docsVsYesterday": "+12",
    "nodesVsYesterday": "+23",
    "edgesVsYesterday": "+56"
  }
}
```

**One-liner summary** (optional, for cron email or Slack):
```
✓ 2026-02-08: 12 docs → 87 entities, 134 relations | 3/3 feeds | 142s
```

---

## Health Check Thresholds

| Check | Healthy | Investigate |
|-------|---------|-------------|
| `feedsReachable` | = `feedsChecked` | Any less means source down |
| `newDocsFound` | 5-30 typical | 0 = stale or broken feeds |
| `docsFailed / docsProcessed` | < 10% | Higher = parsing issues |
| `validationErrors` | 0 | > 0 = schema or prompt drift |
| `status` | `"success"` | Anything else |
| `durationSec` | < 600 (10 min) | Longer = investigate bottleneck |

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
- 1 year ≈ 365 KB
- 10 years ≈ 3.6 MB

No need for log rotation or aggregation infrastructure.

---

## Grep Recipes

Quick ad-hoc troubleshooting without any dependencies.

```bash
# Which days had failures?
grep -l '"status": "failed"' data/logs/*.json

# Which days had zero new docs?
grep -l '"newDocsFound": 0' data/logs/*.json

# Feed outages (fewer than 3 reachable)?
grep -rn '"feedsReachable": [012],' data/logs/

# Validation errors?
grep -l '"validationErrors": [1-9]' data/logs/*.json

# Runs that took over 5 minutes?
grep -E '"durationSec": [3-9][0-9]{2,}' data/logs/*.json

# Last 7 days summary
ls -t data/logs/pipeline_*.json | head -7 | xargs grep -h '"runDate"\|"status"\|"newDocsFound"'

# Count new docs per day (last 30 days)
ls -t data/logs/pipeline_*.json | head -30 | xargs grep '"newDocsFound"'
```

---

## Integration

The pipeline orchestrator should:

1. Initialize the log dict at run start
2. Update counts after each stage
3. Write to `data/logs/pipeline_YYYY-MM-DD.json` on completion
4. On failure, set `"status": "failed"` and include `"error": "..."` field

Optional: append one-liner to stdout for cron capture.
