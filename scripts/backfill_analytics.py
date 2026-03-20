"""Backfill operational analytics tables from historic pipeline JSON logs.

Run this ONCE on the production machine after deploying the new schema.
It reads existing pipeline_*.json files from data/logs/{domain}/ and
populates:
  - pipeline_runs
  - funnel_stats

It also reads existing trending.json exports from data/graphs/{domain}/
and populates:
  - trend_history

Tables that require live pipeline data (doc_selection_log, feed_stats,
source_extraction_quality) cannot be backfilled from logs alone and will
populate naturally on the next pipeline run.

Usage:
    python scripts/backfill_analytics.py                    # default: ai domain
    python scripts/backfill_analytics.py --domain biosafety
    python scripts/backfill_analytics.py --domain film
    python scripts/backfill_analytics.py --dry-run          # preview only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def backfill_pipeline_runs(conn, log_dir: Path, domain: str, dry_run: bool) -> int:
    """Backfill pipeline_runs and funnel_stats from pipeline JSON logs."""
    log_files = sorted(log_dir.glob("pipeline_*.json"))
    if not log_files:
        print(f"  No pipeline logs found in {log_dir}")
        return 0

    count = 0
    for log_file in log_files:
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                run_log = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  SKIP {log_file.name}: {e}")
            continue

        run_date = run_log.get("runDate", "")
        if not run_date:
            print(f"  SKIP {log_file.name}: no runDate")
            continue

        stages = run_log.get("stages", {})
        ingest = stages.get("ingest", {})
        docpack = stages.get("docpack", {})
        extract = stages.get("extract", {})
        imp = stages.get("import", {})
        export = stages.get("export", {})
        trending = stages.get("trending", {})

        if dry_run:
            status = run_log.get("status", "?")
            new_docs = ingest.get("newDocsFound", "?")
            print(f"  {log_file.name}: {status}, {new_docs} docs ingested")
            count += 1
            continue

        # pipeline_runs
        conn.execute(
            """INSERT OR IGNORE INTO pipeline_runs
               (run_date, domain, status, duration_sec, started_at, completed_at,
                docs_ingested, docs_selected, docs_excluded, docs_extracted,
                docs_escalated, entities_new, entities_resolved, relations_added,
                nodes_exported, edges_exported, trending_nodes, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_date, domain, run_log.get("status", "unknown"),
             run_log.get("durationSec"), run_log.get("startedAt"),
             run_log.get("completedAt"),
             ingest.get("newDocsFound", 0),
             docpack.get("docsBundled", 0),
             docpack.get("qualifiedExcluded", 0),
             extract.get("docsExtracted", 0),
             extract.get("escalated", 0),
             imp.get("entitiesNew", 0),
             imp.get("entitiesResolved", 0),
             imp.get("relations", 0),
             export.get("totalNodes", 0),
             export.get("totalEdges", 0),
             trending.get("trendingNodes", 0),
             "; ".join(run_log.get("failedStages", []))),
        )

        # funnel_stats
        funnel_data = [
            ("ingest",
             ingest.get("newDocsFound", 0) + ingest.get("duplicatesSkipped", 0),
             ingest.get("newDocsFound", 0),
             ingest.get("duplicatesSkipped", 0) + ingest.get("fetchErrors", 0),
             json.dumps({"duplicates": ingest.get("duplicatesSkipped", 0),
                         "fetch_errors": ingest.get("fetchErrors", 0)})),
            ("select", docpack.get("qualifiedTotal", 0),
             docpack.get("docsBundled", 0),
             docpack.get("qualifiedExcluded", 0),
             json.dumps({"budget_exceeded": docpack.get("qualifiedExcluded", 0)})),
            ("extract", docpack.get("docsBundled", 0),
             extract.get("docsExtracted", 0),
             extract.get("validationErrors", 0),
             json.dumps({"validation_errors": extract.get("validationErrors", 0),
                         "escalated": extract.get("escalated", 0)})),
            ("import", extract.get("docsExtracted", 0),
             imp.get("filesImported", 0),
             imp.get("errors", 0) if isinstance(imp.get("errors"), int) else 0,
             None),
            ("export", imp.get("filesImported", 0),
             export.get("totalNodes", 0), 0, None),
            ("trending", export.get("totalNodes", 0),
             trending.get("trendingNodes", 0), 0, None),
        ]
        for stage, docs_in, docs_out, docs_dropped, drop_reasons in funnel_data:
            conn.execute(
                """INSERT OR IGNORE INTO funnel_stats
                   (run_date, domain, stage, docs_in, docs_out,
                    docs_dropped, drop_reasons)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (run_date, domain, stage, docs_in, docs_out,
                 docs_dropped, drop_reasons),
            )

        count += 1

    if not dry_run:
        conn.commit()
    return count


def backfill_trend_history(conn, graphs_dir: Path, dry_run: bool) -> int:
    """Backfill trend_history from historic trending.json exports."""
    # trending.json files are at data/graphs/{domain}/{date}/trending.json
    trending_files = sorted(graphs_dir.glob("*/trending.json"))
    if not trending_files:
        print(f"  No trending.json files found in {graphs_dir}")
        return 0

    count = 0
    for trending_file in trending_files:
        run_date = trending_file.parent.name  # directory name is the date

        try:
            with open(trending_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  SKIP {trending_file}: {e}")
            continue

        entities = data.get("entities", [])
        if not entities:
            continue

        if dry_run:
            print(f"  {run_date}/trending.json: {len(entities)} entities")
            count += 1
            continue

        for ent in entities:
            entity_id = ent.get("entity_id", "")
            if not entity_id:
                continue
            conn.execute(
                """INSERT OR IGNORE INTO trend_history
                   (entity_id, run_date, mention_count_7d, mention_count_30d,
                    velocity, novelty, bridge_score, trend_score, in_trending_view)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (entity_id, run_date,
                 ent.get("mention_count_7d", 0),
                 ent.get("mention_count_30d", 0),
                 ent.get("velocity", 0),
                 ent.get("novelty", 0),
                 ent.get("bridge_score", 0),
                 ent.get("trend_score", 0),
                 1),  # if it's in trending.json, it was in the view
            )

        count += 1

    if not dry_run:
        conn.commit()
    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill analytics tables from historic pipeline logs."
    )
    parser.add_argument(
        "--domain", default=None,
        help="Domain slug (default: ai or PREDICTOR_DOMAIN env var)",
    )
    parser.add_argument(
        "--db", default=None,
        help="Path to SQLite database (default: data/db/{domain}.db)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would be backfilled without writing to DB",
    )
    args = parser.parse_args()

    from util.paths import get_db_path
    import os

    domain = args.domain or os.environ.get("PREDICTOR_DOMAIN", "ai")
    db_path = Path(args.db) if args.db else get_db_path(domain)

    project_root = Path(__file__).resolve().parents[1]
    log_dir = project_root / "data" / "logs" / domain
    graphs_dir = project_root / "data" / "graphs" / domain

    print(f"=== Backfill analytics for domain: {domain} ===")
    print(f"  DB: {db_path}")
    print(f"  Logs: {log_dir}")
    print(f"  Graphs: {graphs_dir}")
    if args.dry_run:
        print("  MODE: dry-run (no writes)")
    print()

    if not args.dry_run:
        from db import init_db
        conn = init_db(db_path)
    else:
        conn = None

    # 1. Pipeline runs + funnel stats from JSON logs
    print("1. Pipeline runs + funnel stats:")
    if log_dir.exists():
        n = backfill_pipeline_runs(conn, log_dir, domain, args.dry_run)
        print(f"   → {n} pipeline runs backfilled")
    else:
        print(f"   → No log directory: {log_dir}")

    # 2. Trend history from trending.json exports
    print("2. Trend history:")
    if graphs_dir.exists():
        n = backfill_trend_history(conn, graphs_dir, args.dry_run)
        print(f"   → {n} trending snapshots backfilled")
    else:
        print(f"   → No graphs directory: {graphs_dir}")

    # 3. Source extraction quality — can be partially recovered from DB
    print("3. Source extraction quality:")
    if not args.dry_run and conn:
        try:
            cursor = conn.execute("""
                SELECT substr(d.fetched_at, 1, 10) as run_date,
                       d.source, d.source_type,
                       COUNT(*) as docs_extracted,
                       SUM(CASE WHEN d.escalation_failed IS NOT NULL THEN 1 ELSE 0 END) as docs_failed,
                       AVG(d.quality_score) as avg_quality_score
                FROM documents d
                WHERE d.status = 'extracted'
                  AND d.fetched_at IS NOT NULL
                GROUP BY substr(d.fetched_at, 1, 10), d.source
            """)
            rows = cursor.fetchall()
            for row in rows:
                conn.execute(
                    """INSERT OR IGNORE INTO source_extraction_quality
                       (run_date, source, source_type, docs_extracted,
                        docs_escalated, docs_failed, avg_quality_score,
                        entities_produced, relations_produced)
                       VALUES (?, ?, ?, ?, 0, ?, ?, 0, 0)""",
                    (row[0], row[1], row[2], row[3], row[4], row[5]),
                )
            conn.commit()
            print(f"   → {len(rows)} source-date combos recovered from documents table")
        except Exception as e:
            print(f"   → Error: {e}")
    else:
        print("   → Will recover from documents table (skipped in dry-run)")

    print()
    print("Tables that populate on next pipeline run:")
    print("  - doc_selection_log (requires live scoring)")
    print("  - feed_stats (requires live ingest)")
    print()

    if conn:
        conn.close()

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
