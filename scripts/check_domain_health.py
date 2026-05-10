"""Domain health check: entity overlap rate and trend scoring readiness.

Computes the entity overlap rate (fraction of entities appearing in 2+ docs)
and outputs the overlap health table from the semiconductor design doc with
actual numbers. Flags domains below the 20% minimum threshold.

Usage:
    python scripts/check_domain_health.py --domain ai
    python scripts/check_domain_health.py --domain semiconductors --days 30
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def check_overlap(conn: sqlite3.Connection, days: int | None = None) -> dict:
    """Compute entity overlap rate.

    Returns dict with total_entities, multi_doc_entities, overlap_rate.
    """
    window_clause = ""
    params: tuple = ()
    if days:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        window_clause = "AND d.published_at >= ?"
        params = (cutoff,)

    # Total entities with at least one mention
    total = conn.execute(
        f"""SELECT COUNT(DISTINCT r.target_id) as cnt
            FROM relations r
            JOIN documents d ON r.doc_id = d.doc_id
            WHERE r.rel = 'MENTIONS' {window_clause}""",
        params,
    ).fetchone()["cnt"]

    # Entities mentioned in 2+ docs
    multi = conn.execute(
        f"""SELECT COUNT(*) as cnt FROM (
                SELECT r.target_id, COUNT(DISTINCT r.doc_id) as doc_count
                FROM relations r
                JOIN documents d ON r.doc_id = d.doc_id
                WHERE r.rel = 'MENTIONS' {window_clause}
                GROUP BY r.target_id
                HAVING doc_count >= 2
            )""",
        params,
    ).fetchone()["cnt"]

    rate = multi / total if total > 0 else 0.0
    return {"total_entities": total, "multi_doc_entities": multi, "overlap_rate": rate}


def check_trend_readiness(conn: sqlite3.Connection) -> dict:
    """Check if trend scoring has run and report latest stats."""
    try:
        row = conn.execute(
            "SELECT MAX(run_date) as latest, COUNT(DISTINCT run_date) as runs FROM trend_history"
        ).fetchone()
        latest = row["latest"]
        runs = row["runs"]
    except Exception:
        return {"trend_runs": 0, "latest_run": None}

    if not latest:
        return {"trend_runs": 0, "latest_run": None}

    # Latest run stats
    stats = conn.execute(
        """SELECT COUNT(*) as scored,
                  SUM(CASE WHEN in_trending_view = 1 THEN 1 ELSE 0 END) as trending,
                  AVG(trend_score) as avg_score
           FROM trend_history WHERE run_date = ?""",
        (latest,),
    ).fetchone()

    return {
        "trend_runs": runs,
        "latest_run": latest,
        "entities_scored": stats["scored"],
        "entities_trending": stats["trending"],
        "avg_trend_score": round(stats["avg_score"] or 0, 3),
    }


def main() -> int:
    _load_dotenv()

    parser = argparse.ArgumentParser(description="Domain health check: overlap rate and trend readiness")
    parser.add_argument("--domain", default=None, help="Domain slug")
    parser.add_argument("--db", default=None, help="Path to SQLite database")
    parser.add_argument("--days", type=int, default=None, help="Limit to last N days of data")
    args = parser.parse_args()

    # Resolve domain
    if args.domain:
        os.environ["PREDICTOR_DOMAIN"] = args.domain

    from db import init_db
    from util.paths import get_db_path

    db_path = Path(args.db) if args.db else get_db_path(args.domain)
    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}")
        return 1

    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row

    domain_name = args.domain or os.environ.get("PREDICTOR_DOMAIN", "ai")
    window = f"last {args.days} days" if args.days else "all time"

    print(f"\n{'='*60}")
    print(f"  DOMAIN HEALTH CHECK — {domain_name.upper()}")
    print(f"  Window: {window}")
    print(f"{'='*60}\n")

    # --- Overlap rate ---
    overlap = check_overlap(conn, args.days)
    print("Entity Overlap Rate")
    print("-" * 40)
    print(f"  Total entities (with mentions): {overlap['total_entities']}")
    print(f"  In 2+ documents:                {overlap['multi_doc_entities']}")
    print(f"  Overlap rate:                   {overlap['overlap_rate']:.1%}")

    if overlap["overlap_rate"] < 0.20:
        print(f"  ⚠  WARNING: Below 20% minimum — graph not yet useful for trend detection")
        print(f"     Target: 30%+ for meaningful cross-document signal")
    elif overlap["overlap_rate"] < 0.30:
        print(f"  ℹ  Approaching target (30%) — graph is gaining critical mass")
    else:
        print(f"  ✓  Above 30% target — graph has critical mass for trend detection")

    # --- Overlap by entity type ---
    try:
        rows = conn.execute(
            """SELECT e.type,
                      COUNT(DISTINCT e.entity_id) as total,
                      COUNT(DISTINCT CASE WHEN sub.doc_count >= 2 THEN e.entity_id END) as multi
               FROM entities e
               LEFT JOIN (
                   SELECT r.target_id, COUNT(DISTINCT r.doc_id) as doc_count
                   FROM relations r WHERE r.rel = 'MENTIONS'
                   GROUP BY r.target_id
               ) sub ON sub.target_id = e.entity_id
               GROUP BY e.type
               ORDER BY total DESC"""
        ).fetchall()
        if rows:
            print(f"\n  {'Type':<15} {'Total':>6} {'Multi':>6} {'Rate':>7}")
            print(f"  {'─'*36}")
            for r in rows:
                rate = r["multi"] / r["total"] * 100 if r["total"] > 0 else 0
                print(f"  {r['type']:<15} {r['total']:>6} {r['multi']:>6} {rate:>6.0f}%")
    except Exception:
        pass

    print()

    # --- Trend readiness ---
    trend = check_trend_readiness(conn)
    print("Trend Scoring Readiness")
    print("-" * 40)
    if trend["trend_runs"] == 0:
        print("  No trend scoring runs yet")
        print("  Run: python scripts/run_trending.py --domain", domain_name)
    else:
        print(f"  Total scoring runs:   {trend['trend_runs']}")
        print(f"  Latest run:           {trend['latest_run']}")
        print(f"  Entities scored:      {trend['entities_scored']}")
        print(f"  In trending view:     {trend['entities_trending']}")
        print(f"  Avg trend score:      {trend['avg_trend_score']}")

    print()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
