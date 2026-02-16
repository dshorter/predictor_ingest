"""Pipeline health report: critical mass tracking and source quality.

Answers "are we on track to a useful graph?" by measuring:
  - Ingestion volume and extraction coverage
  - Entity overlap rate (the key critical-mass metric)
  - Graph density (edges per node)
  - Per-source contribution quality
  - Source freshness
  - Trajectory projection

Output goes to both stdout and data/reports/health_YYYY-MM-DD.txt.

Usage:
    python scripts/health_report.py [--db data/db/predictor.db] [--days 30]
    python scripts/health_report.py --date 2026-02-16
    python scripts/health_report.py --summary  # one-liner for cron/grep

Grep recipes:
    # Entity overlap trend over time
    grep "Entity overlap rate" data/reports/health_*.txt

    # Extraction backlog trend
    grep "Backlog" data/reports/health_*.txt

    # Critical mass status
    grep "CRITICAL MASS" data/reports/health_*.txt

    # Source contribution rankings
    grep -A 20 "Source Contribution" data/reports/health_*.txt
"""

from __future__ import annotations

import argparse
import io
import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db import init_db

# --- Thresholds ---
# Minimum entity overlap rate for meaningful trend detection
OVERLAP_TARGET = 0.30  # 30% of entities appear in 2+ docs
# Minimum edges per node for connected graph
DENSITY_TARGET = 2.0
# Source freshness thresholds (days)
STALE_WARN_DAYS = 14
STALE_CRITICAL_DAYS = 30


class ReportWriter:
    """Tee output to both stdout and a file buffer."""

    def __init__(self) -> None:
        self.buffer = io.StringIO()

    def print(self, text: str = "") -> None:
        print(text)
        self.buffer.write(text + "\n")

    def get_text(self) -> str:
        return self.buffer.getvalue()


def section_ingestion(w: ReportWriter, conn: sqlite3.Connection, days: int | None) -> dict:
    """Ingestion volume and status breakdown."""
    date_clause = ""
    params: list = []
    if days:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        date_clause = " WHERE fetched_at >= ?"
        params = [cutoff]

    # Total docs by status
    cursor = conn.execute(
        f"""
        SELECT status, COUNT(*) as cnt
        FROM documents
        {date_clause}
        GROUP BY status
        ORDER BY cnt DESC
        """,
        params,
    )
    status_rows = cursor.fetchall()
    total = sum(r["cnt"] for r in status_rows)

    # Daily ingestion rate
    cursor = conn.execute(
        f"""
        SELECT DATE(fetched_at) as day, COUNT(*) as cnt
        FROM documents
        {date_clause}
        GROUP BY DATE(fetched_at)
        ORDER BY day DESC
        LIMIT 14
        """,
        params,
    )
    daily_rows = cursor.fetchall()

    w.print("Ingestion Summary")
    w.print("=" * 72)
    w.print(f"  Total documents: {total}")
    for r in status_rows:
        pct = r["cnt"] / total * 100 if total else 0
        w.print(f"    {r['status']:<20} {r['cnt']:>6}  ({pct:.0f}%)")

    if daily_rows:
        rates = [r["cnt"] for r in daily_rows]
        avg_daily = sum(rates) / len(rates) if rates else 0
        w.print(f"\n  Avg daily ingest (last {len(rates)} days): {avg_daily:.1f} docs/day")
        w.print(f"  {'Day':<12} {'Docs':>6}")
        w.print(f"  {'─' * 20}")
        for r in daily_rows[:7]:
            w.print(f"  {r['day']:<12} {r['cnt']:>6}")

    w.print()
    return {"total_docs": total, "avg_daily": avg_daily if daily_rows else 0}


def section_extraction_coverage(w: ReportWriter, conn: sqlite3.Connection, extractions_dir: Path) -> dict:
    """How much of the ingested corpus has been extracted."""
    cursor = conn.execute("SELECT COUNT(*) as cnt FROM documents WHERE status != 'error'")
    valid_docs = cursor.fetchone()["cnt"]

    cursor = conn.execute("SELECT COUNT(*) as cnt FROM documents WHERE status = 'extracted'")
    extracted_docs = cursor.fetchone()["cnt"]

    # Also count extraction files on disk (may differ from DB status)
    extraction_files = len(list(extractions_dir.glob("*.json"))) if extractions_dir.exists() else 0

    backlog = valid_docs - extracted_docs

    w.print("Extraction Coverage")
    w.print("=" * 72)
    w.print(f"  Valid documents:     {valid_docs:>6}")
    w.print(f"  Extracted (DB):      {extracted_docs:>6}")
    w.print(f"  Extraction files:    {extraction_files:>6}")
    w.print(f"  Backlog:             {backlog:>6}  {'<-- run extraction!' if backlog > 10 else ''}")
    if valid_docs:
        coverage_pct = extracted_docs / valid_docs * 100
        w.print(f"  Coverage:            {coverage_pct:>5.1f}%")
    w.print()
    return {
        "valid_docs": valid_docs,
        "extracted_docs": extracted_docs,
        "extraction_files": extraction_files,
        "backlog": backlog,
    }


def section_graph_density(w: ReportWriter, conn: sqlite3.Connection) -> dict:
    """Entity count, relation count, edges per node, type distribution."""
    cursor = conn.execute("SELECT COUNT(*) as cnt FROM entities")
    entity_count = cursor.fetchone()["cnt"]

    cursor = conn.execute("SELECT COUNT(*) as cnt FROM relations")
    relation_count = cursor.fetchone()["cnt"]

    density = relation_count / entity_count if entity_count else 0
    density_ok = density >= DENSITY_TARGET

    # Entity type distribution
    cursor = conn.execute(
        "SELECT type, COUNT(*) as cnt FROM entities GROUP BY type ORDER BY cnt DESC"
    )
    type_rows = cursor.fetchall()

    w.print("Graph Density")
    w.print("=" * 72)
    w.print(f"  Entities:            {entity_count:>6}")
    w.print(f"  Relations:           {relation_count:>6}")
    w.print(f"  Edges/node:          {density:>6.2f}  (target: {DENSITY_TARGET:.1f}) {'OK' if density_ok else 'LOW'}")
    if type_rows:
        w.print(f"\n  Entity types:")
        for r in type_rows:
            w.print(f"    {r['type']:<20} {r['cnt']:>5}")
    w.print()
    return {"entities": entity_count, "relations": relation_count, "density": density}


def section_entity_overlap(w: ReportWriter, conn: sqlite3.Connection) -> dict:
    """The critical mass metric: how many entities appear in 2+ documents."""
    # Count docs per entity via relations table (each relation has a doc_id)
    cursor = conn.execute(
        """
        SELECT entity_id,
               COUNT(DISTINCT doc_id) as doc_count
        FROM (
            SELECT source_id as entity_id, doc_id FROM relations WHERE doc_id IS NOT NULL
            UNION ALL
            SELECT target_id as entity_id, doc_id FROM relations WHERE doc_id IS NOT NULL
        )
        GROUP BY entity_id
        """
    )
    rows = cursor.fetchall()

    total_entities = len(rows)
    multi_doc = sum(1 for r in rows if r["doc_count"] >= 2)
    three_plus = sum(1 for r in rows if r["doc_count"] >= 3)
    five_plus = sum(1 for r in rows if r["doc_count"] >= 5)

    overlap_rate = multi_doc / total_entities if total_entities else 0
    overlap_ok = overlap_rate >= OVERLAP_TARGET

    w.print("Entity Overlap (Critical Mass Indicator)")
    w.print("=" * 72)
    w.print(f"  Entities with relations:  {total_entities:>5}")
    w.print(f"  In 2+ documents:          {multi_doc:>5}  ({overlap_rate:.0%})")
    w.print(f"  In 3+ documents:          {three_plus:>5}")
    w.print(f"  In 5+ documents:          {five_plus:>5}")
    w.print(f"  Overlap rate:             {overlap_rate:.0%}  (target: {OVERLAP_TARGET:.0%}) {'OK' if overlap_ok else 'LOW'}")

    # Top entities by document count
    if rows:
        top = sorted(rows, key=lambda r: r["doc_count"], reverse=True)[:10]
        w.print(f"\n  Top entities by document coverage:")
        w.print(f"  {'Entity':<40} {'Docs':>5}")
        w.print(f"  {'─' * 47}")
        for r in top:
            eid = r["entity_id"]
            # Truncate long IDs
            display = eid[:38] + ".." if len(eid) > 40 else eid
            w.print(f"  {display:<40} {r['doc_count']:>5}")

    w.print()

    # CRITICAL MASS status line (grep target)
    if overlap_rate >= OVERLAP_TARGET and total_entities >= 50:
        w.print("  CRITICAL MASS: approaching (overlap OK, building density)")
    elif total_entities < 20:
        w.print("  CRITICAL MASS: not started (too few extracted entities)")
    else:
        w.print(f"  CRITICAL MASS: building ({total_entities} entities, {overlap_rate:.0%} overlap)")
    w.print()

    return {
        "total_with_relations": total_entities,
        "multi_doc": multi_doc,
        "overlap_rate": overlap_rate,
    }


def section_source_contribution(w: ReportWriter, conn: sqlite3.Connection) -> dict:
    """Which sources produce the most extractable entities and relations."""
    cursor = conn.execute(
        """
        SELECT d.source,
               COUNT(DISTINCT d.doc_id) as docs,
               COUNT(DISTINCT r.source_id) + COUNT(DISTINCT r.target_id) as entity_mentions,
               COUNT(r.relation_id) as relations
        FROM documents d
        LEFT JOIN relations r ON d.doc_id = r.doc_id
        WHERE d.status != 'error'
        GROUP BY d.source
        ORDER BY relations DESC
        """
    )
    rows = cursor.fetchall()

    w.print("Source Contribution")
    w.print("=" * 72)
    w.print(f"  {'Source':<30} {'Docs':>5} {'Entities':>9} {'Relations':>10} {'Rel/Doc':>8}")
    w.print(f"  {'─' * 64}")
    for r in rows:
        rel_per_doc = r["relations"] / r["docs"] if r["docs"] else 0
        source = r["source"][:28] + ".." if len(r["source"]) > 30 else r["source"]
        w.print(
            f"  {source:<30} {r['docs']:>5} {r['entity_mentions']:>9} "
            f"{r['relations']:>10} {rel_per_doc:>8.1f}"
        )
    w.print()
    return {"sources": len(rows)}


def section_source_freshness(w: ReportWriter, conn: sqlite3.Connection) -> dict:
    """Per-source content freshness."""
    cursor = conn.execute(
        """
        SELECT source,
               COUNT(*) as total_docs,
               MAX(published_at) as latest_published,
               MIN(published_at) as earliest_published
        FROM documents
        WHERE status != 'error'
        GROUP BY source
        ORDER BY latest_published DESC
        """
    )
    rows = cursor.fetchall()
    today_str = date.today().isoformat()

    w.print("Source Freshness")
    w.print("=" * 72)
    w.print(f"  {'Source':<30} {'Docs':>5} {'Latest':>12} {'Status'}")
    w.print(f"  {'─' * 64}")

    stale_count = 0
    for r in rows:
        source = r["source"][:28] + ".." if len(r["source"] or "") > 30 else (r["source"] or "unknown")
        latest = (r["latest_published"] or "")[:10] or "--"
        status = ""
        if latest != "--":
            try:
                days_ago = (date.fromisoformat(today_str) - date.fromisoformat(latest)).days
                if days_ago > STALE_CRITICAL_DAYS:
                    status = f"STALE ({days_ago}d)"
                    stale_count += 1
                elif days_ago > STALE_WARN_DAYS:
                    status = f"WARN ({days_ago}d)"
                else:
                    status = f"active ({days_ago}d)"
            except ValueError:
                status = "bad date"
        w.print(f"  {source:<30} {r['total_docs']:>5} {latest:>12} {status}")

    w.print()
    return {"stale_sources": stale_count}


def section_trajectory(
    w: ReportWriter,
    ingestion: dict,
    extraction: dict,
    density: dict,
    overlap: dict,
) -> None:
    """Project time to critical mass at current rates."""
    w.print("Trajectory Projection")
    w.print("=" * 72)

    avg_daily = ingestion.get("avg_daily", 0)
    current_entities = density.get("entities", 0)
    current_overlap = overlap.get("overlap_rate", 0)
    backlog = extraction.get("backlog", 0)

    if avg_daily > 0:
        w.print(f"  Current rate: {avg_daily:.0f} docs/day")
        w.print(f"  Current entities: {current_entities}")
        w.print(f"  Current overlap: {current_overlap:.0%}")

        # Rough projections (assuming ~8 unique entities per doc after dedup)
        entities_per_doc = 8
        if current_entities > 0 and extraction.get("extracted_docs", 0) > 0:
            entities_per_doc = current_entities / extraction["extracted_docs"]
            w.print(f"  Observed entities/doc: {entities_per_doc:.1f}")

        # Days to 500 entities
        if current_entities < 500 and avg_daily > 0:
            remaining = 500 - current_entities
            days_to_500 = remaining / (avg_daily * entities_per_doc)
            w.print(f"  Est. days to 500 entities: {days_to_500:.0f}")
        elif current_entities >= 500:
            w.print(f"  500 entity milestone: REACHED")

        if backlog > 0:
            w.print(f"\n  Immediate win: extracting {backlog} backlog docs could yield ~{backlog * entities_per_doc:.0f} entities")
    else:
        w.print("  Insufficient data for projection")

    w.print()


def section_summary_line(
    w: ReportWriter,
    report_date: str,
    ingestion: dict,
    extraction: dict,
    density: dict,
    overlap: dict,
) -> str:
    """One-liner summary for cron/grep."""
    line = (
        f"HEALTH {report_date}: "
        f"{ingestion.get('total_docs', 0)} docs, "
        f"{extraction.get('extracted_docs', 0)} extracted, "
        f"{extraction.get('backlog', 0)} backlog | "
        f"{density.get('entities', 0)} entities, "
        f"{density.get('relations', 0)} relations, "
        f"{density.get('density', 0):.2f} e/n | "
        f"overlap {overlap.get('overlap_rate', 0):.0%}"
    )
    w.print(line)
    return line


def run_report(db_path: Path, days: int | None, summary_only: bool = False) -> int:
    """Generate the full health report."""
    conn = init_db(db_path)
    w = ReportWriter()
    report_date = date.today().isoformat()
    extractions_dir = db_path.parent.parent / "extractions"

    window = f"last {days} days" if days else "all time"
    w.print(f"Pipeline Health Report — {report_date} ({window})")
    w.print("=" * 72)
    w.print()

    ingestion = section_ingestion(w, conn, days)
    extraction = section_extraction_coverage(w, conn, extractions_dir)
    graph = section_graph_density(w, conn)
    overlap = section_entity_overlap(w, conn)
    section_source_contribution(w, conn)
    section_source_freshness(w, conn)
    section_trajectory(w, ingestion, extraction, graph, overlap)

    w.print("─" * 72)
    summary = section_summary_line(w, report_date, ingestion, extraction, graph, overlap)

    # Write report to file
    report_dir = db_path.parent.parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"health_{report_date}.txt"
    report_path.write_text(w.get_text(), encoding="utf-8")
    print(f"\nReport saved: {report_path}")

    conn.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pipeline health report: critical mass tracking and source quality."
    )
    parser.add_argument("--db", default="data/db/predictor.db",
                        help="Path to SQLite database")
    parser.add_argument("--days", type=int, default=None,
                        help="Limit ingestion stats to last N days (default: all time)")
    parser.add_argument("--date", default=None,
                        help="Report for a specific date (default: today)")
    parser.add_argument("--summary", action="store_true",
                        help="Print only the one-liner summary")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        print("Run the pipeline first to create it.")
        return 1

    return run_report(db_path, args.days, args.summary)


if __name__ == "__main__":
    raise SystemExit(main())
