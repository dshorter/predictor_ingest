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

DOMAIN="${DOMAIN:-ai}"
DB="data/db/${DOMAIN}.db"
OUTDIR="data/metrics_snapshot_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTDIR"

echo "=== Collecting metrics into $OUTDIR (domain: $DOMAIN) ==="

# 1. Shadow report (escalation stats, model split, quality distribution)
echo "[1/10] Shadow report..."
$PYTHON scripts/shadow_report.py --db "$DB" --domain "$DOMAIN" > "$OUTDIR/01_shadow_report.txt" 2>&1 || true

# 2. Health report (docs per source, stage counts, errors)
echo "[2/10] Health report..."
$PYTHON scripts/health_report.py --db "$DB" --domain "$DOMAIN" > "$OUTDIR/02_health_report.txt" 2>&1 || true

# 3. Worst quality scores (bottom 50 by score)
echo "[3/10] Quality metrics (worst 50)..."
sqlite3 -header -csv "$DB" "
SELECT qr.doc_id, qr.pipeline_stage, qr.model, qr.quality_score,
       qr.decision, qr.decision_reason
FROM quality_runs qr
WHERE qr.quality_score IS NOT NULL
ORDER BY qr.quality_score ASC
LIMIT 50;
" > "$OUTDIR/03_worst_quality_scores.csv" 2>&1 || echo "(no quality_runs data)" > "$OUTDIR/03_worst_quality_scores.csv"

# 4. Per-metric breakdown for escalated docs (orphans, evidence, density)
echo "[4/10] Gate failure details..."
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
echo "[5/10] Escalation failures..."
sqlite3 -header -csv "$DB" "
SELECT doc_id, extracted_by, quality_score, escalation_failed
FROM documents
WHERE escalation_failed IS NOT NULL
ORDER BY quality_score ASC;
" > "$OUTDIR/05_escalation_failures.csv" 2>&1 || echo "(column not yet migrated — run import once first)" > "$OUTDIR/05_escalation_failures.csv"

# 6. Selection efficiency — from doc_selection_log table (DB-backed)
echo "[6/10] Selection efficiency (from DB)..."
sqlite3 -header -csv "$DB" "
SELECT run_date, source_type,
       COUNT(*) as candidates,
       SUM(CASE WHEN outcome='selected' THEN 1 ELSE 0 END) as selected,
       SUM(CASE WHEN outcome='benched' THEN 1 ELSE 0 END) as benched,
       SUM(CASE WHEN outcome='rejected' THEN 1 ELSE 0 END) as rejected,
       ROUND(AVG(combined_score), 3) as avg_score,
       ROUND(MIN(combined_score), 3) as min_score
FROM doc_selection_log
GROUP BY run_date, source_type
ORDER BY run_date DESC, source_type
LIMIT 100;
" > "$OUTDIR/06_selection_efficiency.csv" 2>&1 || echo "(doc_selection_log not yet populated)" > "$OUTDIR/06_selection_efficiency.csv"

# 7. Feed health — from feed_stats table (DB-backed)
echo "[7/10] Feed health (from DB)..."
sqlite3 -header -csv "$DB" "
SELECT run_date, feed_name, source_type,
       docs_fetched, docs_new, docs_skipped, fetch_errors, error_message
FROM feed_stats
ORDER BY run_date DESC, feed_name
LIMIT 200;
" > "$OUTDIR/07_feed_health.csv" 2>&1 || echo "(feed_stats not yet populated)" > "$OUTDIR/07_feed_health.csv"

# 8. Source extraction quality — from source_extraction_quality table
echo "[8/10] Source extraction quality (from DB)..."
sqlite3 -header -csv "$DB" "
SELECT run_date, source, source_type,
       docs_extracted, docs_escalated, docs_failed,
       ROUND(avg_quality_score, 3) as avg_quality,
       entities_produced, relations_produced
FROM source_extraction_quality
ORDER BY run_date DESC, source
LIMIT 200;
" > "$OUTDIR/08_source_quality.csv" 2>&1 || echo "(source_extraction_quality not yet populated)" > "$OUTDIR/08_source_quality.csv"

# 9. Pipeline run history — from pipeline_runs table
echo "[9/10] Pipeline run history (from DB)..."
sqlite3 -header -csv "$DB" "
SELECT run_date, status, ROUND(duration_sec, 0) as duration,
       docs_ingested, docs_selected, docs_excluded, docs_extracted,
       docs_escalated, entities_new, relations_added,
       nodes_exported, trending_nodes, error_message
FROM pipeline_runs
WHERE domain = '${DOMAIN}'
ORDER BY run_date DESC
LIMIT 30;
" > "$OUTDIR/09_pipeline_history.csv" 2>&1 || echo "(pipeline_runs not yet populated)" > "$OUTDIR/09_pipeline_history.csv"

# 10. Document funnel (last 7 days) — from funnel_stats table
echo "[10/10] Document funnel (from DB)..."
sqlite3 -header -csv "$DB" "
SELECT run_date, stage, docs_in, docs_out, docs_dropped, drop_reasons
FROM funnel_stats
WHERE domain = '${DOMAIN}'
ORDER BY run_date DESC, stage
LIMIT 100;
" > "$OUTDIR/10_document_funnel.csv" 2>&1 || echo "(funnel_stats not yet populated)" > "$OUTDIR/10_document_funnel.csv"

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
    [ -f "$f" ] || continue
    size=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null || echo 0)
    # gh gist create rejects blank files — write a placeholder if empty
    if [ "$size" -eq 0 ]; then
        echo "(no data)" > "$f"
        size=10
    fi
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
    GIST_URL=$(gh gist create --public -d "predictor_ingest ${DOMAIN} metrics $(date '+%Y-%m-%d %H:%M')" "${NORMAL_FILES[@]}")
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
