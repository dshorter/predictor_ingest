"""Shadow mode comparison report.

Shows understudy model performance vs Sonnet primary, with promotion
criteria tracking per docs/llm-selection.md.

Usage:
    python scripts/shadow_report.py [--db data/db/predictor.db] [--days 7]
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db import init_db, list_understudy_models, get_understudy_summary

# Promotion thresholds from docs/llm-selection.md
PROMOTE_SCHEMA_PASS = 95.0
PROMOTE_ENTITY_OVERLAP = 85.0
PROMOTE_RELATION_OVERLAP = 80.0
PROMOTE_MIN_DOCS = 100


def grade(value: float | None, threshold: float) -> str:
    """Return a pass/fail marker for a metric."""
    if value is None:
        return "  --"
    return " OK " if value >= threshold else "MISS"


def run_report(db_path: Path, days: int | None) -> int:
    conn = init_db(db_path)
    models = list_understudy_models(conn)

    if not models:
        print("No shadow comparison data found.")
        print("Run: make shadow-only  (or make extract --shadow)")
        return 0

    min_date = None
    if days:
        min_date = (date.today() - timedelta(days=days)).isoformat()

    window_label = f"last {days} days" if days else "all time"
    print(f"Shadow Mode Report ({window_label})")
    print(f"Promotion: schema >= {PROMOTE_SCHEMA_PASS}%, "
          f"entity >= {PROMOTE_ENTITY_OVERLAP}%, "
          f"relation >= {PROMOTE_RELATION_OVERLAP}%, "
          f"docs >= {PROMOTE_MIN_DOCS}")
    print("=" * 80)

    for model in models:
        summary = get_understudy_summary(conn, model, min_date=min_date)
        total = summary["total_docs"]
        schema = summary["schema_pass_rate"]
        entity = summary["avg_entity_overlap_pct"]
        relation = summary["avg_relation_overlap_pct"]
        duration = summary["avg_duration_ms"]

        # Per-day breakdown
        cursor = conn.execute(
            """
            SELECT run_date,
                   COUNT(*) as docs,
                   SUM(schema_valid) as valid,
                   AVG(entity_overlap_pct) as entity_pct,
                   AVG(relation_overlap_pct) as relation_pct,
                   AVG(understudy_duration_ms) as avg_ms
            FROM extraction_comparison
            WHERE understudy_model = ?
            """ + (" AND run_date >= ?" if min_date else "") + """
            GROUP BY run_date
            ORDER BY run_date DESC
            """,
            (model, min_date) if min_date else (model,),
        )
        daily_rows = cursor.fetchall()

        # Promotion check
        schema_ok = schema >= PROMOTE_SCHEMA_PASS
        entity_ok = entity is not None and entity >= PROMOTE_ENTITY_OVERLAP
        relation_ok = relation is not None and relation >= PROMOTE_RELATION_OVERLAP
        docs_ok = total >= PROMOTE_MIN_DOCS
        promotable = schema_ok and entity_ok and relation_ok and docs_ok

        print(f"\n  {model}")
        print(f"  {'─' * 60}")
        print(f"  Docs processed:    {total:>6}       [{grade(total, PROMOTE_MIN_DOCS)}] need {PROMOTE_MIN_DOCS}+")
        print(f"  Schema pass rate:  {schema:>6.1f}%      [{grade(schema, PROMOTE_SCHEMA_PASS)}] need {PROMOTE_SCHEMA_PASS}%+")
        if entity is not None:
            print(f"  Entity overlap:    {entity:>6.1f}%      [{grade(entity, PROMOTE_ENTITY_OVERLAP)}] need {PROMOTE_ENTITY_OVERLAP}%+")
        else:
            print(f"  Entity overlap:       --         [  --] need {PROMOTE_ENTITY_OVERLAP}%+")
        if relation is not None:
            print(f"  Relation overlap:  {relation:>6.1f}%      [{grade(relation, PROMOTE_RELATION_OVERLAP)}] need {PROMOTE_RELATION_OVERLAP}%+")
        else:
            print(f"  Relation overlap:     --         [  --] need {PROMOTE_RELATION_OVERLAP}%+")
        if duration is not None:
            print(f"  Avg latency:       {duration:>6.0f}ms")

        if promotable:
            print(f"  >>> READY FOR PROMOTION <<<")
        elif total > 0:
            gaps = []
            if not docs_ok:
                gaps.append(f"{PROMOTE_MIN_DOCS - total} more docs needed")
            if not schema_ok:
                gaps.append(f"schema {schema:.0f}% < {PROMOTE_SCHEMA_PASS}%")
            if not entity_ok:
                gaps.append(f"entity {entity or 0:.0f}% < {PROMOTE_ENTITY_OVERLAP}%")
            if not relation_ok:
                gaps.append(f"relation {relation or 0:.0f}% < {PROMOTE_RELATION_OVERLAP}%")
            print(f"  Gaps: {'; '.join(gaps)}")

        # Daily breakdown
        if daily_rows:
            print(f"\n  Daily breakdown:")
            print(f"  {'Date':<12} {'Docs':>5} {'Schema%':>8} {'Entity%':>8} {'Rel%':>8} {'Avg ms':>8}")
            for row in daily_rows:
                d_schema = (row["valid"] / row["docs"] * 100) if row["docs"] else 0
                d_entity = f"{row['entity_pct']:>7.0f}%" if row["entity_pct"] is not None else f"{'--':>8}"
                d_relation = f"{row['relation_pct']:>7.0f}%" if row["relation_pct"] is not None else f"{'--':>8}"
                d_ms = f"{row['avg_ms']:>8.0f}" if row["avg_ms"] is not None else f"{'--':>8}"
                print(f"  {row['run_date']:<12} {row['docs']:>5} {d_schema:>7.0f}% {d_entity} {d_relation} {d_ms}")

    print("\n" + "=" * 80)
    conn.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Shadow mode comparison report.")
    parser.add_argument("--db", default="data/db/predictor.db",
                        help="Path to SQLite database")
    parser.add_argument("--days", type=int, default=None,
                        help="Limit to last N days (default: all time)")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        print("Run the pipeline first to create it.")
        return 1

    return run_report(db_path, args.days)


if __name__ == "__main__":
    raise SystemExit(main())
