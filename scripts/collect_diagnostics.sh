#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# collect_diagnostics.sh — Gather VPS pipeline state for offline analysis
#
# Usage:
#   cd /opt/predictor_ingest   # or wherever the repo lives
#   bash scripts/collect_diagnostics.sh
#
# Output:
#   diagnostics/diag_YYYY-MM-DD_HHMMSS/  (timestamped directory)
#   diagnostics/diag_YYYY-MM-DD_HHMMSS.tar.gz  (compressed archive)
#
# The archive can be pushed to the repo for analysis in Claude Code:
#   git add diagnostics/diag_*.tar.gz
#   git commit -m "Add VPS diagnostics snapshot"
#   git push
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
DIAG_DIR="diagnostics/diag_${TIMESTAMP}"
DB="${DB:-data/db/predictor.db}"

mkdir -p "$DIAG_DIR"

log() { echo "[diag] $*"; }

# ── 0. Environment ────────────────────────────────────────────────────
log "Collecting environment info..."
{
    echo "=== System ==="
    echo "hostname: $(hostname 2>/dev/null || echo unknown)"
    echo "date_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "date_local: $(date +%Y-%m-%dT%H:%M:%S%z)"
    echo "uname: $(uname -a)"
    echo "python: $(python3 --version 2>&1 || python --version 2>&1 || echo 'NOT FOUND')"
    echo "pip_list:"
    pip list 2>/dev/null | head -50 || echo "  pip not available"
    echo ""
    echo "=== Working directory ==="
    echo "cwd: $(pwd)"
    echo "git_branch: $(git branch --show-current 2>/dev/null || echo 'not a git repo')"
    echo "git_HEAD: $(git rev-parse HEAD 2>/dev/null || echo 'n/a')"
    echo "git_status:"
    git status --short 2>/dev/null || echo "  n/a"
    echo ""
    echo "=== Environment variables (presence only) ==="
    echo "ANTHROPIC_API_KEY: $([ -n "${ANTHROPIC_API_KEY:-}" ] && echo SET || echo NOT_SET)"
    echo "OPENAI_API_KEY: $([ -n "${OPENAI_API_KEY:-}" ] && echo SET || echo NOT_SET)"
    echo "PRIMARY_MODEL: ${PRIMARY_MODEL:-NOT_SET}"
    echo "UNDERSTUDY_MODEL: ${UNDERSTUDY_MODEL:-NOT_SET}"
    echo ""
    echo "=== .env file ==="
    if [ -f .env ]; then
        # Show keys only, not values (security)
        echo "exists: yes"
        echo "keys:"
        grep -oP '^\s*[A-Z_]+(?=\s*=)' .env 2>/dev/null || echo "  (none or parse error)"
    else
        echo "exists: no"
    fi
} > "$DIAG_DIR/environment.txt" 2>&1

# ── 1. Database existence & size ──────────────────────────────────────
log "Checking database..."
{
    echo "=== Database file ==="
    if [ -f "$DB" ]; then
        echo "path: $DB"
        echo "size: $(du -h "$DB" | cut -f1)"
        echo "modified: $(stat -c '%y' "$DB" 2>/dev/null || stat -f '%Sm' "$DB" 2>/dev/null || echo 'unknown')"
    else
        echo "NOT FOUND: $DB"
        echo "Searched paths:"
        find . -name "predictor.db" -type f 2>/dev/null || echo "  none found"
    fi
} > "$DIAG_DIR/db_file.txt" 2>&1

# ── 2. Database table counts & schema ─────────────────────────────────
if [ -f "$DB" ]; then
    log "Querying database..."
    {
        echo "=== Table row counts ==="
        for table in documents entities relations evidence entity_aliases extraction_comparison; do
            count=$(sqlite3 "$DB" "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "ERROR")
            printf "  %-25s %s\n" "$table" "$count"
        done

        echo ""
        echo "=== Documents by status ==="
        sqlite3 -header -column "$DB" \
            "SELECT status, COUNT(*) as cnt FROM documents GROUP BY status ORDER BY cnt DESC;" 2>&1

        echo ""
        echo "=== Documents by source ==="
        sqlite3 -header -column "$DB" \
            "SELECT source, status, COUNT(*) as cnt FROM documents GROUP BY source, status ORDER BY source, status;" 2>&1

        echo ""
        echo "=== Documents date range ==="
        sqlite3 -header -column "$DB" \
            "SELECT MIN(published_at) as earliest_published, MAX(published_at) as latest_published,
                    MIN(fetched_at) as earliest_fetched, MAX(fetched_at) as latest_fetched
             FROM documents;" 2>&1

        echo ""
        echo "=== Recent documents (last 20) ==="
        sqlite3 -header -column "$DB" \
            "SELECT doc_id, source, status, published_at, substr(fetched_at,1,19) as fetched
             FROM documents ORDER BY fetched_at DESC LIMIT 20;" 2>&1

        echo ""
        echo "=== Documents with NULL/missing text_path ==="
        sqlite3 -header -column "$DB" \
            "SELECT doc_id, status, text_path
             FROM documents WHERE text_path IS NULL OR text_path = ''
             LIMIT 20;" 2>&1

        echo ""
        echo "=== Documents with errors ==="
        sqlite3 -header -column "$DB" \
            "SELECT doc_id, source, status, error
             FROM documents WHERE status = 'error' OR error IS NOT NULL
             ORDER BY fetched_at DESC LIMIT 20;" 2>&1

        echo ""
        echo "=== Entities by type ==="
        sqlite3 -header -column "$DB" \
            "SELECT type, COUNT(*) as cnt FROM entities GROUP BY type ORDER BY cnt DESC;" 2>&1

        echo ""
        echo "=== Entities date range ==="
        sqlite3 -header -column "$DB" \
            "SELECT MIN(first_seen) as earliest, MAX(last_seen) as latest FROM entities;" 2>&1

        echo ""
        echo "=== Top 20 entities by relation count ==="
        sqlite3 -header -column "$DB" \
            "SELECT e.entity_id, e.name, e.type,
                    COUNT(DISTINCT r.relation_id) as rel_count
             FROM entities e
             LEFT JOIN relations r ON e.entity_id = r.source_id OR e.entity_id = r.target_id
             GROUP BY e.entity_id
             ORDER BY rel_count DESC LIMIT 20;" 2>&1

        echo ""
        echo "=== Relations by type ==="
        sqlite3 -header -column "$DB" \
            "SELECT rel, kind, COUNT(*) as cnt FROM relations GROUP BY rel, kind ORDER BY cnt DESC;" 2>&1

        echo ""
        echo "=== Relations by kind ==="
        sqlite3 -header -column "$DB" \
            "SELECT kind, COUNT(*) as cnt FROM relations GROUP BY kind ORDER BY cnt DESC;" 2>&1

        echo ""
        echo "=== MENTIONS relation count ==="
        sqlite3 "$DB" "SELECT COUNT(*) FROM relations WHERE rel = 'MENTIONS';" 2>&1

        echo ""
        echo "=== Evidence coverage ==="
        sqlite3 -header -column "$DB" \
            "SELECT
                (SELECT COUNT(*) FROM relations) as total_relations,
                (SELECT COUNT(DISTINCT relation_id) FROM evidence) as relations_with_evidence,
                (SELECT COUNT(*) FROM evidence) as total_evidence_records;" 2>&1

        echo ""
        echo "=== Entity aliases count ==="
        sqlite3 "$DB" "SELECT COUNT(*) FROM entity_aliases;" 2>&1

        echo ""
        echo "=== Extraction comparison summary ==="
        sqlite3 -header -column "$DB" \
            "SELECT understudy_model,
                    COUNT(*) as docs,
                    SUM(schema_valid) as valid,
                    ROUND(AVG(entity_overlap_pct), 1) as avg_entity_overlap,
                    ROUND(AVG(relation_overlap_pct), 1) as avg_rel_overlap
             FROM extraction_comparison
             GROUP BY understudy_model;" 2>&1

    } > "$DIAG_DIR/db_queries.txt" 2>&1

    # ── 2b. Orphan check (text files referenced but missing) ──────────
    log "Checking for orphaned text_path references..."
    {
        echo "=== text_path files: exist vs missing ==="
        sqlite3 "$DB" "SELECT text_path FROM documents WHERE text_path IS NOT NULL;" 2>/dev/null | while read -r tp; do
            if [ -n "$tp" ] && [ ! -f "$tp" ]; then
                echo "MISSING: $tp"
            fi
        done
        echo "(end of check)"
    } > "$DIAG_DIR/orphan_check.txt" 2>&1
fi

# ── 3. Data directory structure ───────────────────────────────────────
log "Scanning data directory..."
{
    echo "=== data/ disk usage ==="
    du -sh data/ 2>/dev/null || echo "data/ not found"
    du -sh data/*/ 2>/dev/null || echo "  no subdirectories"

    echo ""
    echo "=== File counts per directory ==="
    for subdir in raw text docpacks extractions graphs logs reports; do
        dir="data/$subdir"
        if [ -d "$dir" ]; then
            count=$(find "$dir" -type f 2>/dev/null | wc -l)
            printf "  %-20s %s files\n" "$subdir/" "$count"
        else
            printf "  %-20s MISSING\n" "$subdir/"
        fi
    done

    echo ""
    echo "=== Graph export directories ==="
    ls -la data/graphs/ 2>/dev/null || echo "  data/graphs/ not found"

    echo ""
    echo "=== Latest graph export ==="
    latest_graph=$(ls -td data/graphs/20*/ 2>/dev/null | head -1)
    if [ -n "$latest_graph" ]; then
        echo "dir: $latest_graph"
        ls -la "$latest_graph" 2>/dev/null
        # Show meta from each view
        for f in "$latest_graph"/*.json; do
            if [ -f "$f" ]; then
                echo ""
                echo "--- $(basename "$f") meta ---"
                python3 -c "
import json, sys
with open('$f') as fh:
    d = json.load(fh)
m = d.get('meta', {})
for k,v in m.items():
    print(f'  {k}: {v}')
" 2>&1 || echo "  (parse error)"
            fi
        done
    else
        echo "  no graph exports found"
    fi

    echo ""
    echo "=== web/data/graphs/live/ ==="
    if [ -d web/data/graphs/live ]; then
        ls -la web/data/graphs/live/ 2>/dev/null
    else
        echo "  NOT FOUND"
    fi

    echo ""
    echo "=== Docpack files ==="
    ls -la data/docpacks/ 2>/dev/null || echo "  data/docpacks/ not found"

    echo ""
    echo "=== Extraction files (count + sample) ==="
    ext_count=$(ls data/extractions/*.json 2>/dev/null | wc -l)
    echo "  total: $ext_count"
    if [ "$ext_count" -gt 0 ]; then
        echo "  newest 5:"
        ls -t data/extractions/*.json 2>/dev/null | head -5 | while read -r f; do
            size=$(du -h "$f" | cut -f1)
            echo "    $f ($size)"
        done
        echo "  oldest 5:"
        ls -tr data/extractions/*.json 2>/dev/null | head -5 | while read -r f; do
            size=$(du -h "$f" | cut -f1)
            echo "    $f ($size)"
        done
    fi

    echo ""
    echo "=== Pipeline lock ==="
    if [ -f data/pipeline.lock ]; then
        echo "LOCKED (pipeline may be running)"
        ls -la data/pipeline.lock
    else
        echo "not locked"
    fi
} > "$DIAG_DIR/data_structure.txt" 2>&1

# ── 4. Pipeline logs ──────────────────────────────────────────────────
log "Collecting pipeline logs..."
{
    echo "=== Pipeline log files ==="
    ls -la data/logs/pipeline_*.json 2>/dev/null || echo "  no pipeline logs found"
} > "$DIAG_DIR/pipeline_log_list.txt" 2>&1

# Copy last 7 pipeline logs
mkdir -p "$DIAG_DIR/logs"
for logfile in $(ls -t data/logs/pipeline_*.json 2>/dev/null | head -7); do
    cp "$logfile" "$DIAG_DIR/logs/" 2>/dev/null
done

# ── 5. Health reports ─────────────────────────────────────────────────
log "Collecting health reports..."
mkdir -p "$DIAG_DIR/reports"
for report in $(ls -t data/reports/health_*.txt 2>/dev/null | head -3); do
    cp "$report" "$DIAG_DIR/reports/" 2>/dev/null
done

# ── 6. Config files ──────────────────────────────────────────────────
log "Collecting config..."
mkdir -p "$DIAG_DIR/config"
cp config/feeds.yaml "$DIAG_DIR/config/" 2>/dev/null || echo "(no feeds.yaml)" > "$DIAG_DIR/config/feeds_yaml_missing.txt"
cp pyproject.toml "$DIAG_DIR/config/" 2>/dev/null || true
cp Makefile "$DIAG_DIR/config/" 2>/dev/null || true

# ── 7. Sample extraction files (first & last 2, not the full set) ────
log "Collecting sample extractions..."
mkdir -p "$DIAG_DIR/sample_extractions"
{
    # Newest 2
    ls -t data/extractions/*.json 2>/dev/null | head -2 | while read -r f; do
        cp "$f" "$DIAG_DIR/sample_extractions/"
    done
    # Oldest 2
    ls -tr data/extractions/*.json 2>/dev/null | head -2 | while read -r f; do
        cp "$f" "$DIAG_DIR/sample_extractions/"
    done
} 2>/dev/null

# ── 8. Live test: dry-run each pipeline stage ─────────────────────────
log "Running pipeline stage checks..."
{
    echo "=== Module import check ==="
    python3 -c "import ingest.rss; print('ingest.rss: OK')" 2>&1 || echo "ingest.rss: FAIL"
    python3 -c "import extract; print('extract: OK')" 2>&1 || echo "extract: FAIL"
    python3 -c "import db; print('db: OK')" 2>&1 || echo "db: FAIL"
    python3 -c "import graph; print('graph: OK')" 2>&1 || echo "graph: FAIL"
    python3 -c "import resolve; print('resolve: OK')" 2>&1 || echo "resolve: FAIL"
    python3 -c "import trend; print('trend: OK')" 2>&1 || echo "trend: FAIL"
    python3 -c "import schema; print('schema: OK')" 2>&1 || echo "schema: FAIL"
    python3 -c "import config; print('config: OK')" 2>&1 || echo "config: FAIL"

    echo ""
    echo "=== pip install -e . status ==="
    pip show predictor-ingest 2>&1 || echo "NOT INSTALLED"

    echo ""
    echo "=== Schema validation check ==="
    if [ -f data/extractions/*.json ] 2>/dev/null; then
        first_ext=$(ls data/extractions/*.json 2>/dev/null | head -1)
        python3 -c "
from schema import validate_extraction
import json
with open('$first_ext') as f:
    data = json.load(f)
validate_extraction(data)
print(f'Schema validation: PASS ({first_ext})')
" 2>&1 || echo "Schema validation: FAIL"
    else
        echo "No extraction files to validate"
    fi

    echo ""
    echo "=== Feed connectivity (quick check, first 3 feeds) ==="
    python3 -c "
import yaml, feedparser, sys
with open('config/feeds.yaml') as f:
    cfg = yaml.safe_load(f)
feeds = cfg.get('feeds', [])[:3]
for feed in feeds:
    url = feed.get('url', '')
    name = feed.get('name', url)
    try:
        d = feedparser.parse(url)
        bozo = getattr(d, 'bozo', False)
        n = len(d.entries)
        status = getattr(d, 'status', None)
        if bozo and n == 0:
            print(f'  {name}: UNREACHABLE (bozo={bozo}, status={status})')
        else:
            print(f'  {name}: OK ({n} entries, status={status})')
    except Exception as e:
        print(f'  {name}: ERROR ({e})')
" 2>&1

    echo ""
    echo "=== Docpack dry-run (count available docs) ==="
    python3 -c "
import sqlite3
conn = sqlite3.connect('$DB')
conn.row_factory = sqlite3.Row
cleaned = conn.execute(\"SELECT COUNT(*) as n FROM documents WHERE status = 'cleaned' AND text_path IS NOT NULL\").fetchone()
extracted = conn.execute(\"SELECT COUNT(*) as n FROM documents WHERE status = 'extracted'\").fetchone()
error = conn.execute(\"SELECT COUNT(*) as n FROM documents WHERE status = 'error'\").fetchone()
print(f'  Ready for docpack (cleaned+text_path): {cleaned[\"n\"]}')
print(f'  Already extracted: {extracted[\"n\"]}')
print(f'  Errored: {error[\"n\"]}')
conn.close()
" 2>&1

    echo ""
    echo "=== Import dry-run ==="
    python3 scripts/import_extractions.py --db "$DB" --dry-run 2>&1 || echo "  import dry-run failed"

} > "$DIAG_DIR/stage_checks.txt" 2>&1

# ── 9. Recent cron / systemd status (if applicable) ──────────────────
log "Checking scheduled tasks..."
{
    echo "=== crontab ==="
    crontab -l 2>/dev/null || echo "  no crontab or permission denied"

    echo ""
    echo "=== systemd timers ==="
    systemctl list-timers 2>/dev/null | grep -i predict 2>/dev/null || echo "  no matching timers"

    echo ""
    echo "=== recent pipeline-related processes ==="
    ps aux 2>/dev/null | grep -i "pipeline\|ingest\|extract\|predictor" | grep -v grep || echo "  none running"
} > "$DIAG_DIR/scheduling.txt" 2>&1

# ── 10. Quick consistency checks ─────────────────────────────────────
if [ -f "$DB" ]; then
    log "Running consistency checks..."
    {
        echo "=== Consistency checks ==="

        echo ""
        echo "--- Extracted docs without extraction files ---"
        sqlite3 "$DB" "SELECT doc_id FROM documents WHERE status = 'extracted';" 2>/dev/null | while read -r docid; do
            if [ ! -f "data/extractions/${docid}.json" ]; then
                echo "  MISSING extraction: $docid"
            fi
        done
        echo "(done)"

        echo ""
        echo "--- Extraction files without matching doc in DB ---"
        for f in data/extractions/*.json 2>/dev/null; do
            [ -f "$f" ] || continue
            docid=$(basename "$f" .json)
            found=$(sqlite3 "$DB" "SELECT COUNT(*) FROM documents WHERE doc_id = '$docid';" 2>/dev/null)
            if [ "$found" = "0" ]; then
                echo "  ORPHAN extraction: $f"
            fi
        done
        echo "(done)"

        echo ""
        echo "--- Entities without any relations ---"
        sqlite3 -header -column "$DB" \
            "SELECT e.entity_id, e.name, e.type
             FROM entities e
             LEFT JOIN relations r ON e.entity_id = r.source_id OR e.entity_id = r.target_id
             WHERE r.relation_id IS NULL
             LIMIT 20;" 2>&1
        echo "(done)"

        echo ""
        echo "--- Relations referencing missing entities ---"
        sqlite3 "$DB" \
            "SELECT r.relation_id, r.source_id, r.rel, r.target_id
             FROM relations r
             LEFT JOIN entities es ON r.source_id = es.entity_id
             LEFT JOIN entities et ON r.target_id = et.entity_id
             WHERE (es.entity_id IS NULL AND r.source_id NOT LIKE 'doc:%')
                OR  et.entity_id IS NULL
             LIMIT 20;" 2>&1
        echo "(done)"

        echo ""
        echo "--- Asserted relations without evidence ---"
        sqlite3 -header -column "$DB" \
            "SELECT r.relation_id, r.source_id, r.rel, r.target_id
             FROM relations r
             LEFT JOIN evidence ev ON r.relation_id = ev.relation_id
             WHERE r.kind = 'asserted'
               AND r.rel != 'MENTIONS'
               AND ev.evidence_id IS NULL
             LIMIT 20;" 2>&1
        echo "(done)"

        echo ""
        echo "--- Duplicate MENTIONS edges ---"
        sqlite3 -header -column "$DB" \
            "SELECT source_id, target_id, COUNT(*) as cnt
             FROM relations WHERE rel = 'MENTIONS'
             GROUP BY source_id, target_id
             HAVING cnt > 1
             LIMIT 20;" 2>&1
        echo "(done)"

    } > "$DIAG_DIR/consistency_checks.txt" 2>&1
fi

# ── Package it up ─────────────────────────────────────────────────────
log "Creating archive..."
tar czf "${DIAG_DIR}.tar.gz" -C diagnostics "diag_${TIMESTAMP}" 2>/dev/null

echo ""
echo "============================================"
echo "  Diagnostics collected: ${DIAG_DIR}/"
echo "  Archive: ${DIAG_DIR}.tar.gz"
echo ""
echo "  To push to repo (diagnostics/ is gitignored,"
echo "  so use git add --force):"
echo ""
echo "    git checkout -b claude/debug-daily-process-AVGNa origin/claude/debug-daily-process-AVGNa 2>/dev/null || git checkout claude/debug-daily-process-AVGNa"
echo "    git add --force ${DIAG_DIR}.tar.gz"
echo "    git commit -m 'Add VPS diagnostics ${TIMESTAMP}'"
echo "    git push origin claude/debug-daily-process-AVGNa"
echo ""
echo "  The --force overrides .gitignore for this one file."
echo "  It stays on the feature branch, never reaches main."
echo "============================================"
