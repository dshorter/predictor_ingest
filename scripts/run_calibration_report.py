"""Daily calibration report — signals, anomaly flags, and tuning suggestions.

Reads from pipeline_runs, funnel_stats, feed_stats, source_extraction_quality,
doc_selection_log, and batch_jobs to produce a human-readable report with
flagged anomalies and concrete parameter suggestions.

Does NOT auto-apply anything. Suggestions are written to stdout and optionally
logged to the tuning_log table for Thursday review.

Usage:
    python scripts/run_calibration_report.py --db data/db/film.db --domain film
    python scripts/run_calibration_report.py --db data/db/film.db --domain film --log-suggestions
    python scripts/run_calibration_report.py --db data/db/film.db --domain film --days 14
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# ---------------------------------------------------------------------------
# Thresholds for anomaly detection
# ---------------------------------------------------------------------------

THRESHOLDS = {
    # Entity yield: flag if today's rate drops >30% below 7-day rolling avg
    "entity_yield_drop_pct": 0.30,
    # Orphan edge rate: flag if stripped orphans exceed this fraction of total edges
    "orphan_edge_rate_max": 0.05,
    # Feed consecutive errors: flag after this many days in a row
    "feed_error_days_max": 3,
    # Bench ratio: flag if >92% of qualified docs are benched (budget too tight)
    "bench_ratio_max": 0.92,
    # Batch latency: flag if median completion time exceeds this many hours
    "batch_latency_hours_max": 6.0,
    # Min days of history required before generating suggestions
    "min_history_days": 3,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _window_start(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Signal collectors
# ---------------------------------------------------------------------------


def collect_entity_yield(conn: sqlite3.Connection, domain: str, days: int) -> list[dict]:
    """Entities-new per extracted doc per day."""
    rows = conn.execute(
        """
        SELECT run_date,
               entities_new,
               docs_extracted,
               CASE WHEN docs_extracted > 0
                    THEN CAST(entities_new AS REAL) / docs_extracted
                    ELSE NULL END AS yield_per_doc
        FROM pipeline_runs
        WHERE domain = ? AND run_date >= ? AND docs_extracted > 0
        ORDER BY run_date DESC
        """,
        (domain, _window_start(days)),
    ).fetchall()
    return [dict(r) for r in rows]


def collect_orphan_rates(conn: sqlite3.Connection, domain: str, days: int) -> list[dict]:
    """Orphan edge strip counts from funnel_stats drop_reasons."""
    rows = conn.execute(
        """
        SELECT run_date, drop_reasons
        FROM funnel_stats
        WHERE domain = ? AND stage = 'trending' AND run_date >= ?
        ORDER BY run_date DESC
        """,
        (domain, _window_start(days)),
    ).fetchall()
    results = []
    for r in rows:
        reasons = {}
        if r["drop_reasons"]:
            try:
                reasons = json.loads(r["drop_reasons"])
            except (json.JSONDecodeError, TypeError):
                pass
        results.append({
            "run_date": r["run_date"],
            "orphan_edges": reasons.get("orphan_edges", 0),
        })
    return results


def collect_feed_errors(conn: sqlite3.Connection, domain: str, days: int) -> dict[str, int]:
    """Map feed_name → consecutive error days (most recent streak)."""
    rows = conn.execute(
        """
        SELECT feed_name, run_date, fetch_errors
        FROM feed_stats
        WHERE run_date >= ?
        ORDER BY feed_name, run_date DESC
        """,
        (_window_start(days),),
    ).fetchall()

    # Group by feed, count leading streak of error days
    from collections import defaultdict
    by_feed: dict[str, list] = defaultdict(list)
    for r in rows:
        by_feed[r["feed_name"]].append((r["run_date"], r["fetch_errors"] or 0))

    streaks = {}
    for feed, day_errors in by_feed.items():
        streak = 0
        for _, errors in day_errors:  # already sorted DESC
            if errors > 0:
                streak += 1
            else:
                break
        if streak > 0:
            streaks[feed] = streak
    return streaks


def collect_bench_ratio(conn: sqlite3.Connection, domain: str, days: int) -> list[dict]:
    """Fraction of qualified docs benched due to budget per day."""
    rows = conn.execute(
        """
        SELECT run_date,
               SUM(CASE WHEN outcome='selected' THEN 1 ELSE 0 END) AS selected,
               SUM(CASE WHEN outcome='benched'  THEN 1 ELSE 0 END) AS benched
        FROM doc_selection_log
        WHERE run_date >= ?
        GROUP BY run_date
        ORDER BY run_date DESC
        """,
        (_window_start(days),),
    ).fetchall()
    results = []
    for r in rows:
        total = (r["selected"] or 0) + (r["benched"] or 0)
        ratio = r["benched"] / total if total > 0 else 0.0
        results.append({
            "run_date": r["run_date"],
            "selected": r["selected"],
            "benched": r["benched"],
            "bench_ratio": ratio,
        })
    return results


def collect_batch_latency(conn: sqlite3.Connection, domain: str, days: int) -> list[dict]:
    """Hours between submitted_at and completed_at for finished batch jobs."""
    rows = conn.execute(
        """
        SELECT job_id, run_date, submitted_at, completed_at,
               json_array_length(doc_ids) AS doc_count
        FROM batch_jobs
        WHERE domain = ? AND status = 'complete' AND run_date >= ?
        ORDER BY submitted_at DESC
        """,
        (domain, _window_start(days)),
    ).fetchall()
    results = []
    for r in rows:
        latency_h = None
        if r["submitted_at"] and r["completed_at"]:
            try:
                submitted = datetime.fromisoformat(r["submitted_at"].replace("Z", "+00:00"))
                completed = datetime.fromisoformat(r["completed_at"].replace("Z", "+00:00"))
                latency_h = (completed - submitted).total_seconds() / 3600
            except (ValueError, AttributeError):
                pass
        results.append({
            "run_date": r["run_date"],
            "job_id": r["job_id"],
            "doc_count": r["doc_count"],
            "latency_hours": latency_h,
        })
    return results


def collect_source_quality(conn: sqlite3.Connection, domain: str, days: int) -> list[dict]:
    """Per-source entity yield over the window."""
    rows = conn.execute(
        """
        SELECT source, SUM(docs_extracted) AS docs, SUM(entities_produced) AS entities,
               SUM(relations_produced) AS relations
        FROM source_extraction_quality
        WHERE run_date >= ?
        GROUP BY source
        HAVING docs > 0
        ORDER BY CAST(entities AS REAL) / docs ASC
        """,
        (_window_start(days),),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Suggestion engine
# ---------------------------------------------------------------------------


def generate_suggestions(
    entity_yield: list[dict],
    orphan_rates: list[dict],
    feed_errors: dict[str, int],
    bench_ratios: list[dict],
    batch_latency: list[dict],
    source_quality: list[dict],
    days: int,
) -> list[dict]:
    """Return list of {signal, severity, suggestion, parameter, current, suggested}."""
    suggestions = []
    t = THRESHOLDS

    # --- Entity yield trend ---
    if len(entity_yield) >= t["min_history_days"]:
        yields = [r["yield_per_doc"] for r in entity_yield if r["yield_per_doc"] is not None]
        if len(yields) >= 2:
            baseline = mean(yields[1:])  # exclude today
            today = yields[0]
            if baseline > 0 and (baseline - today) / baseline > t["entity_yield_drop_pct"]:
                drop_pct = int((baseline - today) / baseline * 100)
                suggestions.append({
                    "signal": "entity_yield_drop",
                    "severity": "WARN",
                    "message": (
                        f"Entity yield today ({today:.1f}/doc) is {drop_pct}% below "
                        f"{len(yields)-1}-day avg ({baseline:.1f}/doc)"
                    ),
                    "suggestion": "Review extraction prompt or lower doc selection score threshold by 0.02",
                    "parameter": "selection_score_min",
                    "direction": "decrease",
                })

    # --- Orphan edges ---
    if orphan_rates:
        today_orphans = orphan_rates[0].get("orphan_edges", 0)
        if today_orphans > 0:
            # Estimate rate (need total edges for proper rate — use absolute count as proxy)
            severity = "CRITICAL" if today_orphans > 500 else "WARN" if today_orphans > 100 else "INFO"
            suggestions.append({
                "signal": "orphan_edges",
                "severity": severity,
                "message": f"{today_orphans} orphan edges stripped today",
                "suggestion": (
                    "If rate is growing week-over-week, tighten entity resolution "
                    "similarity_upper_bound by 0.05 to reduce false-non-merges"
                ),
                "parameter": "similarity_upper_bound",
                "direction": "decrease" if today_orphans > 200 else None,
            })

    # --- Feed errors ---
    for feed, streak in feed_errors.items():
        if streak >= t["feed_error_days_max"]:
            severity = "CRITICAL" if streak >= 7 else "WARN"
            suggestions.append({
                "signal": "feed_error_streak",
                "severity": severity,
                "message": f"Feed '{feed}' has errored for {streak} consecutive days",
                "suggestion": (
                    f"Remove or replace '{feed}' from feeds.yaml"
                    if streak >= 7 else
                    f"Investigate '{feed}' — may be temporarily down or URL changed"
                ),
                "parameter": "feeds.yaml",
                "direction": None,
            })

    # --- Bench ratio ---
    if len(bench_ratios) >= t["min_history_days"]:
        recent_ratios = [r["bench_ratio"] for r in bench_ratios[:7]]
        avg_ratio = mean(recent_ratios)
        if avg_ratio > t["bench_ratio_max"]:
            avg_benched = mean([r["benched"] for r in bench_ratios[:7]])
            suggestions.append({
                "signal": "high_bench_ratio",
                "severity": "INFO",
                "message": (
                    f"Budget benching {avg_ratio:.0%} of qualified docs "
                    f"(avg {avg_benched:.0f} benched/day)"
                ),
                "suggestion": (
                    "Consider increasing daily budget (Makefile BUDGET) from current value. "
                    "Batch API cost is low — benching good signal unnecessarily."
                ),
                "parameter": "BUDGET",
                "direction": "increase",
            })

    # --- Batch latency ---
    latencies = [r["latency_hours"] for r in batch_latency if r["latency_hours"] is not None]
    if latencies:
        median_latency = sorted(latencies)[len(latencies) // 2]
        if median_latency > t["batch_latency_hours_max"]:
            suggestions.append({
                "signal": "batch_latency",
                "severity": "INFO",
                "message": f"Median batch completion time is {median_latency:.1f}h",
                "suggestion": (
                    "Latency is within Anthropic SLA (24h) but consider splitting large "
                    "batches if latency increases further"
                ),
                "parameter": "batch_size",
                "direction": "decrease" if median_latency > 12 else None,
            })

    # --- Low-yield sources ---
    if source_quality:
        all_yields = [r["entities"] / r["docs"] for r in source_quality if r["docs"] > 2]
        if len(all_yields) >= 3:
            overall_avg = mean(all_yields)
            for src in source_quality:
                if src["docs"] < 3:
                    continue
                src_yield = src["entities"] / src["docs"]
                if overall_avg > 0 and (overall_avg - src_yield) / overall_avg > 0.50:
                    suggestions.append({
                        "signal": "low_yield_source",
                        "severity": "INFO",
                        "message": (
                            f"Source '{src['source']}' yields {src_yield:.1f} entities/doc "
                            f"vs avg {overall_avg:.1f} (over {days}-day window)"
                        ),
                        "suggestion": (
                            "Consider lowering tier or removing this source from feeds.yaml"
                        ),
                        "parameter": "feeds.yaml",
                        "direction": None,
                    })

    return suggestions


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------


SEVERITY_ORDER = {"CRITICAL": 0, "WARN": 1, "INFO": 2}


def print_report(
    domain: str,
    days: int,
    entity_yield: list[dict],
    orphan_rates: list[dict],
    bench_ratios: list[dict],
    batch_latency: list[dict],
    suggestions: list[dict],
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*60}")
    print(f"  CALIBRATION REPORT — {domain.upper()} — {now}")
    print(f"  Window: {days} days")
    print(f"{'='*60}\n")

    # --- Rolling signal summary ---
    print("SIGNAL SUMMARY (rolling window)")
    print("-" * 40)

    if entity_yield:
        yields = [r["yield_per_doc"] for r in entity_yield if r["yield_per_doc"]]
        if yields:
            print(f"  Entity yield/doc   : {yields[0]:.1f} today  |  "
                  f"avg {mean(yields):.1f}  |  "
                  f"{'↓' if len(yields) > 1 and yields[0] < mean(yields[1:]) else '↑'} trend")
        for r in entity_yield[:5]:
            print(f"    {r['run_date']}: {r['entities_new']} new entities, "
                  f"{r['docs_extracted']} docs, "
                  f"yield={r['yield_per_doc']:.1f}")

    print()

    if bench_ratios:
        avg_bench = mean(r["bench_ratio"] for r in bench_ratios[:7])
        print(f"  Bench ratio        : {avg_bench:.0%} of qualified docs benched (budget cap)")

    if batch_latency:
        latencies = [r["latency_hours"] for r in batch_latency if r["latency_hours"]]
        if latencies:
            print(f"  Batch latency      : {latencies[0]:.1f}h most recent  |  "
                  f"median {sorted(latencies)[len(latencies)//2]:.1f}h")

    if orphan_rates and orphan_rates[0].get("orphan_edges", 0) > 0:
        print(f"  Orphan edges       : {orphan_rates[0]['orphan_edges']} stripped today")

    print()

    # --- Suggestions ---
    if not suggestions:
        print("SUGGESTIONS: none — all signals within normal range ✓\n")
        return

    sorted_suggestions = sorted(suggestions, key=lambda s: SEVERITY_ORDER.get(s["severity"], 9))
    print(f"SUGGESTIONS ({len(suggestions)} flagged)")
    print("-" * 40)

    for i, s in enumerate(sorted_suggestions, 1):
        sev = s["severity"]
        marker = "🔴" if sev == "CRITICAL" else "🟡" if sev == "WARN" else "🔵"
        print(f"\n  [{i}] {marker} {sev} — {s['signal']}")
        print(f"      Observation : {s['message']}")
        print(f"      Suggestion  : {s['suggestion']}")
        if s.get("parameter"):
            direction = f" ({s['direction']})" if s.get("direction") else ""
            print(f"      Parameter   : {s['parameter']}{direction}")

    print()


# ---------------------------------------------------------------------------
# tuning_log persistence
# ---------------------------------------------------------------------------


def ensure_tuning_log(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tuning_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            domain          TEXT NOT NULL,
            logged_at       TEXT NOT NULL,
            parameter       TEXT NOT NULL,
            signal          TEXT NOT NULL,
            severity        TEXT NOT NULL,
            observation     TEXT,
            suggestion      TEXT,
            direction       TEXT,
            applied         INTEGER DEFAULT 0,
            applied_at      TEXT,
            applied_by      TEXT,
            notes           TEXT
        )
    """)
    conn.commit()


def log_suggestions(conn: sqlite3.Connection, domain: str, suggestions: list[dict]) -> int:
    """Write suggestions to tuning_log. Returns count inserted."""
    ensure_tuning_log(conn)
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    for s in suggestions:
        conn.execute(
            """
            INSERT INTO tuning_log
              (domain, logged_at, parameter, signal, severity,
               observation, suggestion, direction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                domain, now,
                s.get("parameter", ""),
                s.get("signal", ""),
                s.get("severity", "INFO"),
                s.get("message", ""),
                s.get("suggestion", ""),
                s.get("direction"),
            ),
        )
        count += 1
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily pipeline calibration report")
    parser.add_argument("--db", required=True, help="Path to SQLite DB")
    parser.add_argument("--domain", default="ai", help="Domain slug")
    parser.add_argument("--days", type=int, default=7, help="Rolling window in days")
    parser.add_argument(
        "--log-suggestions",
        action="store_true",
        help="Persist suggestions to tuning_log table for review",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 1

    conn = _connect(str(db_path))

    entity_yield = collect_entity_yield(conn, args.domain, args.days)
    orphan_rates = collect_orphan_rates(conn, args.domain, args.days)
    feed_errors = collect_feed_errors(conn, args.domain, args.days)
    bench_ratios = collect_bench_ratio(conn, args.domain, args.days)
    batch_latency = collect_batch_latency(conn, args.domain, args.days)
    source_quality = collect_source_quality(conn, args.domain, args.days)

    suggestions = generate_suggestions(
        entity_yield, orphan_rates, feed_errors,
        bench_ratios, batch_latency, source_quality,
        args.days,
    )

    print_report(
        args.domain, args.days,
        entity_yield, orphan_rates, bench_ratios, batch_latency,
        suggestions,
    )

    if args.log_suggestions and suggestions:
        n = log_suggestions(conn, args.domain, suggestions)
        print(f"  → {n} suggestion(s) logged to tuning_log table\n")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
