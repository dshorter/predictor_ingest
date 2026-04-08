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

# 1. Batch jobs summary (ADR-008: Anthropic Batch API replaced two-tier escalation)
echo "[1/12] Batch jobs summary..."
sqlite3 -header -csv "$DB" "
SELECT run_date, status,
       COUNT(*) as job_count,
       SUM(json_array_length(doc_ids)) as total_docs,
       MIN(submitted_at) as first_submitted,
       MAX(completed_at) as last_completed
FROM batch_jobs
WHERE domain = '${DOMAIN}'
GROUP BY run_date, status
ORDER BY run_date DESC, status;
" > "$OUTDIR/01_batch_jobs.csv" 2>&1 || echo "(no batch_jobs data yet)" > "$OUTDIR/01_batch_jobs.csv"

# 2. Health report (docs per source, stage counts, errors)
echo "[2/12] Health report..."
$PYTHON scripts/health_report.py --db "$DB" --domain "$DOMAIN" > "$OUTDIR/02_health_report.txt" 2>&1 || true

# 3. Batch job details — pending vs complete breakdown
echo "[3/12] Batch job detail..."
sqlite3 -header -csv "$DB" "
SELECT job_id, run_date, status,
       json_array_length(doc_ids) as doc_count,
       submitted_at, completed_at,
       CASE WHEN result_file IS NOT NULL THEN 'yes' ELSE 'no' END as has_results
FROM batch_jobs
WHERE domain = '${DOMAIN}'
ORDER BY submitted_at DESC
LIMIT 50;
" > "$OUTDIR/03_batch_job_detail.csv" 2>&1 || echo "(no batch_jobs data)" > "$OUTDIR/03_batch_job_detail.csv"

# 4. Extracted document stats — entity and relation counts per doc
echo "[4/12] Extraction output per document..."
sqlite3 -header -csv "$DB" "
SELECT d.doc_id, d.source, d.source_type, d.status, d.extracted_by,
       COUNT(DISTINCT e.id) as entity_count,
       COUNT(DISTINCT r.id) as relation_count
FROM documents d
LEFT JOIN entities e ON e.doc_id = d.doc_id
LEFT JOIN relations r ON r.doc_id = d.doc_id
WHERE d.status = 'extracted'
GROUP BY d.doc_id
ORDER BY entity_count ASC
LIMIT 100;
" > "$OUTDIR/04_extraction_output.csv" 2>&1 || echo "(no extracted documents)" > "$OUTDIR/04_extraction_output.csv"

# 5. Pending batch docs — doc_ids waiting for collection
echo "[5/12] Pending batch docs..."
sqlite3 -header -csv "$DB" "
SELECT job_id, run_date, submitted_at,
       json_array_length(doc_ids) as pending_docs
FROM batch_jobs
WHERE domain = '${DOMAIN}' AND status = 'pending'
ORDER BY submitted_at DESC;
" > "$OUTDIR/05_pending_batches.csv" 2>&1 || echo "(no pending batches)" > "$OUTDIR/05_pending_batches.csv"

# 6. Selection efficiency — from doc_selection_log table (DB-backed)
echo "[6/12] Selection efficiency (from DB)..."
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
echo "[7/12] Feed health (from DB)..."
sqlite3 -header -csv "$DB" "
SELECT run_date, feed_name, source_type,
       docs_fetched, docs_new, docs_skipped, fetch_errors, error_message
FROM feed_stats
ORDER BY run_date DESC, feed_name
LIMIT 200;
" > "$OUTDIR/07_feed_health.csv" 2>&1 || echo "(feed_stats not yet populated)" > "$OUTDIR/07_feed_health.csv"

# 8. Source extraction quality — from source_extraction_quality table
echo "[8/12] Source extraction quality (from DB)..."
sqlite3 -header -csv "$DB" "
SELECT run_date, source, source_type,
       docs_extracted, docs_failed,
       entities_produced, relations_produced
FROM source_extraction_quality
ORDER BY run_date DESC, source
LIMIT 200;
" > "$OUTDIR/08_source_quality.csv" 2>&1 || echo "(source_extraction_quality not yet populated)" > "$OUTDIR/08_source_quality.csv"

# 9. Pipeline run history — from pipeline_runs table
echo "[9/12] Pipeline run history (from DB)..."
sqlite3 -header -csv "$DB" "
SELECT run_date, status, ROUND(duration_sec, 0) as duration,
       docs_ingested, docs_selected, docs_excluded, docs_extracted,
       entities_new, relations_added,
       nodes_exported, trending_nodes, error_message
FROM pipeline_runs
WHERE domain = '${DOMAIN}'
ORDER BY run_date DESC
LIMIT 30;
" > "$OUTDIR/09_pipeline_history.csv" 2>&1 || echo "(pipeline_runs not yet populated)" > "$OUTDIR/09_pipeline_history.csv"

# 10. Document funnel (last 7 days) — from funnel_stats table
echo "[10/12] Document funnel (from DB)..."
sqlite3 -header -csv "$DB" "
SELECT run_date, stage, docs_in, docs_out, docs_dropped, drop_reasons
FROM funnel_stats
WHERE domain = '${DOMAIN}'
ORDER BY run_date DESC, stage
LIMIT 100;
" > "$OUTDIR/10_document_funnel.csv" 2>&1 || echo "(funnel_stats not yet populated)" > "$OUTDIR/10_document_funnel.csv"

# 11. Trend scoring — from trend_history (Sprint 13)
echo "[11/12] Trend scoring history..."
sqlite3 -header -csv "$DB" "
SELECT entity_id, run_date, velocity, novelty, trend_score,
       velocity_gated, corpus_entity_count, novelty_decay_lambda,
       mention_count_7d, mention_count_30d, in_trending_view
FROM trend_history
WHERE run_date >= DATE('now', '-7 days')
ORDER BY run_date DESC, trend_score DESC
LIMIT 500;
" > "$OUTDIR/11_trend_scoring.csv" 2>&1 || echo "(trend_history not yet populated)" > "$OUTDIR/11_trend_scoring.csv"

# 12. Trend config history — from pipeline_runs.trend_config (Sprint 13)
echo "[12/12] Trend config history..."
sqlite3 -header -csv "$DB" "
SELECT run_date, trend_config
FROM pipeline_runs
WHERE domain = '${DOMAIN}' AND trend_config IS NOT NULL
ORDER BY run_date DESC
LIMIT 30;
" > "$OUTDIR/12_trend_config_history.csv" 2>&1 || echo "(no trend_config data yet)" > "$OUTDIR/12_trend_config_history.csv"

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
