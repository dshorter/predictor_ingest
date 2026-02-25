#!/usr/bin/env bash
# Collect pipeline metrics into text files and upload as a GitHub gist.
# Run from the project root:  bash scripts/collect_metrics_gist.sh
#
# Requires: python3, sqlite3, gh (GitHub CLI, authenticated)
set -euo pipefail

# Find python interpreter (some servers only have python3)
PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)
if [ -z "$PYTHON" ]; then
    echo "ERROR: No python3 or python found on PATH"
    exit 1
fi
echo "Using: $PYTHON"

DB="data/db/predictor.db"
OUTDIR="data/metrics_snapshot_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTDIR"

echo "=== Collecting metrics into $OUTDIR ==="

# 1. Shadow report (escalation stats, model split, quality distribution)
echo "[1/6] Shadow report..."
$PYTHON scripts/shadow_report.py --db "$DB" > "$OUTDIR/01_shadow_report.txt" 2>&1 || true

# 2. Health report (docs per source, stage counts, errors)
echo "[2/6] Health report..."
$PYTHON scripts/health_report.py --db "$DB" > "$OUTDIR/02_health_report.txt" 2>&1 || true

# 3. Worst quality scores (bottom 50 by score)
echo "[3/6] Quality metrics (worst 50)..."
sqlite3 -header -csv "$DB" "
SELECT qr.doc_id, qr.pipeline_stage, qr.model, qr.quality_score,
       qr.decision, qr.decision_reason
FROM quality_runs qr
WHERE qr.quality_score IS NOT NULL
ORDER BY qr.quality_score ASC
LIMIT 50;
" > "$OUTDIR/03_worst_quality_scores.csv" 2>&1 || echo "(no quality_runs data)" > "$OUTDIR/03_worst_quality_scores.csv"

# 4. Per-metric breakdown for escalated docs (orphans, evidence, density)
echo "[4/6] Gate failure details..."
sqlite3 -header -csv "$DB" "
SELECT qr.doc_id, qm.metric_name, qm.metric_value, qm.passed,
       qm.threshold_value, substr(qm.notes, 1, 300) as notes_trunc
FROM quality_metrics qm
JOIN quality_runs qr ON qm.run_id = qr.run_id
WHERE qm.passed = 0
ORDER BY qm.metric_name, qm.metric_value DESC
LIMIT 100;
" > "$OUTDIR/04_gate_failures.csv" 2>&1 || echo "(no quality_metrics data)" > "$OUTDIR/04_gate_failures.csv"

# 5. Escalation failures (docs where specialist failed, cheap result kept)
echo "[5/6] Escalation failures..."
sqlite3 -header -csv "$DB" "
SELECT doc_id, extracted_by, quality_score, escalation_failed
FROM documents
WHERE escalation_failed IS NOT NULL
ORDER BY quality_score ASC;
" > "$OUTDIR/05_escalation_failures.csv" 2>&1 || echo "(column not yet migrated — run import once first)" > "$OUTDIR/05_escalation_failures.csv"

# 6. Recent pipeline logs (last 7 days)
echo "[6/6] Pipeline logs..."
LOGDIR="data/logs"
if [ -d "$LOGDIR" ]; then
    # Grab the most recent 7 log files
    ls -1t "$LOGDIR"/pipeline_*.json 2>/dev/null | head -7 | while read -r f; do
        echo "--- $(basename "$f") ---"
        cat "$f"
        echo
    done > "$OUTDIR/06_pipeline_logs.txt"
else
    echo "(no pipeline logs found at $LOGDIR)" > "$OUTDIR/06_pipeline_logs.txt"
fi

echo
echo "=== Files collected ==="
ls -lh "$OUTDIR"/
echo

# --- Upload as gist(s) ---
# GitHub gist limit: 10 MB per file, 300 files per gist.
# Our files should be well under 10 MB total, so one gist suffices.
# If any single file is over 5 MB, we split into separate gists.

LARGE_THRESHOLD=$((5 * 1024 * 1024))  # 5 MB
NORMAL_FILES=()
LARGE_FILES=()

for f in "$OUTDIR"/*.txt "$OUTDIR"/*.csv; do
    size=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null || echo 0)
    if [ "$size" -gt "$LARGE_THRESHOLD" ]; then
        LARGE_FILES+=("$f")
    else
        NORMAL_FILES+=("$f")
    fi
done

if ! command -v gh &>/dev/null; then
    echo "ERROR: gh (GitHub CLI) not found. Install it or create the gist manually from $OUTDIR"
    exit 1
fi

if ! gh auth status &>/dev/null; then
    echo "ERROR: gh not authenticated. Run 'gh auth login' first."
    exit 1
fi

echo "Creating gist..."
if [ ${#NORMAL_FILES[@]} -gt 0 ]; then
    GIST_URL=$(gh gist create --public -d "predictor_ingest metrics $(date '+%Y-%m-%d %H:%M')" "${NORMAL_FILES[@]}")
    echo "Gist created: $GIST_URL"
fi

# Upload oversized files as separate gists (unlikely but handled)
for f in "${LARGE_FILES[@]}"; do
    echo "Large file $(basename "$f") — creating separate gist..."
    LARGE_URL=$(gh gist create --public -d "predictor_ingest $(basename "$f") $(date +%Y-%m-%d)" "$f")
    echo "  $LARGE_URL"
done

echo
echo "Done. Share the gist URL(s) above."
