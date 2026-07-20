"""Export the Movers view in tabular form for the Movers frontend.

The Movers view is a sortable / filterable table of the full scored
entity population over a configurable rank window (default 7 days).
It surfaces emerging entities — climbers, just-appeared entities,
fast-accelerating low-volume entities — that don't break into the
top-N "Current Landscape" graph.

This script is the backend half of Workstream A in
docs/plans/movers-and-focus-mode.md. Output contract: schemas/movers.json
(Appendix A in the plan).

Reads from trend_history (the daily scored population) plus entities,
relations, and documents tables. Zero LLM cost — pure SQL + Python.

Run order: this script must run AFTER scripts/run_trending.py for the
same date, since it depends on today's trend_history rows.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def _bootstrap_domain() -> None:
    """Set PREDICTOR_DOMAIN from --domain arg before any domain-aware imports."""
    for i, arg in enumerate(sys.argv):
        if arg == "--domain" and i + 1 < len(sys.argv):
            os.environ["PREDICTOR_DOMAIN"] = sys.argv[i + 1]
            return
        if arg.startswith("--domain="):
            os.environ["PREDICTOR_DOMAIN"] = arg.split("=", 1)[1]
            return


_load_dotenv()
_bootstrap_domain()

from db import init_db
from domain import get_active_profile
from util import utc_now_iso


DEFAULT_WINDOW_DAYS: int = 7

# One-sided 95% lower bound (Sprint 20.7). The z, not the method, is the
# tunable — recorded in meta.scoring so exports are self-describing.
VELOCITY_CI_Z: float = 1.645


def _most_recent_run_date(conn: sqlite3.Connection) -> str | None:
    """Return the most recent run_date in trend_history, or None if empty."""
    row = conn.execute(
        "SELECT MAX(run_date) FROM trend_history"
    ).fetchone()
    return row[0] if row and row[0] else None


def _epoch_for_run(conn: sqlite3.Connection, run_date: str) -> int | None:
    """Epoch of a given run's rows; None when the column doesn't exist yet."""
    try:
        row = conn.execute(
            "SELECT MAX(epoch) FROM trend_history WHERE run_date = ?",
            (run_date,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return int(row[0]) if row and row[0] is not None else None


def _prior_run_date(
    conn: sqlite3.Connection,
    today_run_date: str,
    window_days: int,
    epoch: int | None = None,
) -> str | None:
    """Most recent run_date that is at least `window_days` before today.

    If no qualifying row exists (e.g. fresh install), returns None and
    every entity is treated as just-appeared.

    When `epoch` is given, only runs from that epoch qualify — velocity /
    persistence windows never span epochs (ADR-010 / Sprint 20.1b), so the
    first post-restart exports treat everything as just-appeared rather
    than diffing against a differently-scored past.
    """
    target = (date.fromisoformat(today_run_date) - timedelta(days=window_days)).isoformat()
    if epoch is None:
        row = conn.execute(
            "SELECT MAX(run_date) FROM trend_history WHERE run_date <= ?",
            (target,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT MAX(run_date) FROM trend_history WHERE run_date <= ? AND epoch = ?",
            (target, epoch),
        ).fetchone()
    return row[0] if row and row[0] else None


def _ranks_for_run(
    conn: sqlite3.Connection, run_date: str
) -> dict[str, dict[str, Any]]:
    """Compute current_rank (and pull other scoring fields) for a given run_date.

    Returns {entity_id: {rank, trend_score, in_trending_view, ...}}.
    """
    rows = conn.execute(
        """
        SELECT entity_id,
               trend_score,
               mention_count_7d,
               mention_count_30d,
               in_trending_view,
               velocity,
               bridge_score,
               ROW_NUMBER() OVER (ORDER BY trend_score DESC, entity_id ASC) AS rank
        FROM trend_history
        WHERE run_date = ?
        """,
        (run_date,),
    ).fetchall()
    return {
        r[0]: {
            "trend_score": r[1] or 0.0,
            "mention_count_7d": r[2] or 0,
            "mention_count_30d": r[3] or 0,
            "in_trending_view": bool(r[4]),
            "velocity": r[5],
            "bridge_score": r[6],
            "rank": int(r[7]),
        }
        for r in rows
    }


def _entities_metadata(
    conn: sqlite3.Connection, entity_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """Pull entity label, type, first_seen for the given IDs.

    Bulk query, indexed by entity_id.
    """
    if not entity_ids:
        return {}
    placeholders = ",".join("?" * len(entity_ids))
    rows = conn.execute(
        f"""
        SELECT entity_id, name, type, first_seen
        FROM entities
        WHERE entity_id IN ({placeholders})
        """,
        entity_ids,
    ).fetchall()
    return {r[0]: {"label": r[1], "type": r[2], "first_seen": r[3]} for r in rows}


def _mention_counts_window(
    conn: sqlite3.Connection,
    base_relation: str,
    start_date: str,
    end_date: str,
) -> dict[str, int]:
    """Count MENTIONS edges per entity where the source doc was published in [start, end].

    Mirrors src/trend/count_mentions but bulk over all entities.
    """
    rows = conn.execute(
        """
        SELECT r.target_id, COUNT(*)
        FROM relations r
        JOIN documents d ON r.doc_id = d.doc_id
        WHERE r.rel = ?
          AND d.published_at >= ?
          AND d.published_at <= ?
        GROUP BY r.target_id
        """,
        (base_relation, start_date, end_date),
    ).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def _distinct_sources_7d(
    conn: sqlite3.Connection,
    base_relation: str,
    start_date: str,
    end_date: str,
) -> dict[str, int]:
    """Count distinct documents.source values per entity in the 7d window."""
    rows = conn.execute(
        """
        SELECT r.target_id, COUNT(DISTINCT d.source)
        FROM relations r
        JOIN documents d ON r.doc_id = d.doc_id
        WHERE r.rel = ?
          AND d.published_at >= ?
          AND d.published_at <= ?
        GROUP BY r.target_id
        """,
        (base_relation, start_date, end_date),
    ).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def _compute_velocity_raw(
    recent: int, previous: int
) -> float | None:
    """Uncapped 7d / prior-7d ratio. Null when undefined."""
    if previous == 0:
        # No prior-window mentions — ratio is undefined. For just-appeared
        # entities this is the natural "null" case per Appendix A.
        return None
    return recent / previous


def _velocity_ci_lower(
    recent: int, previous: int, z: float = VELOCITY_CI_Z
) -> float | None:
    """One-sided lower confidence bound on the mention rate ratio (20.7).

    Velocity is an estimate from two small Poisson counts, and the point
    ratio rewards exactly the rows with the least evidence (3/1 "300%"
    risers). Ranking by the lower bound of the ratio's confidence interval
    makes uncertainty self-penalizing: small samples get wide intervals
    and sink; a rise that clears the bound is real at the stated
    confidence. Supersedes the planned Bayesian pseudocounts and
    multi-window blend — one mechanism, no tuning knobs beyond z.

    Katz log-ratio interval with a +0.5 continuity correction on both
    counts, so the bound is defined even for 0→N surges (where the point
    ratio is undefined/infinite) and stays honest about them:
        lower = RR_c × exp(−z · √(1/(recent+½) + 1/(previous+½)))
    Null only when both windows are empty (no signal at all).
    """
    if recent == 0 and previous == 0:
        return None
    r = recent + 0.5
    p = previous + 0.5
    ratio = r / p
    se = ((1.0 / r) + (1.0 / p)) ** 0.5
    return ratio * math.exp(-z * se)


def build_movers_rows(
    conn: sqlite3.Connection,
    window_days: int,
    base_relation: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the (rows, dateRange) tuple for movers.json.

    Returns:
        rows: list of dicts matching schemas/movers.json $defs/row
        dateRange: {start, end} for the meta block
    """
    today_run_date = _most_recent_run_date(conn)
    if not today_run_date:
        return [], {"start": None, "end": date.today().isoformat()}

    today_epoch = _epoch_for_run(conn, today_run_date)
    prior_run_date = _prior_run_date(conn, today_run_date, window_days,
                                     epoch=today_epoch)

    today = _ranks_for_run(conn, today_run_date)
    prior = _ranks_for_run(conn, prior_run_date) if prior_run_date else {}

    entity_ids = list(today.keys())
    metadata = _entities_metadata(conn, entity_ids)

    # Mention-count windows for uncapped velocity:
    # recent  = today_run - window_days .. today_run
    # earlier = today_run - 2*window_days .. today_run - window_days
    today_dt = date.fromisoformat(today_run_date)
    recent_start = (today_dt - timedelta(days=window_days)).isoformat()
    recent_end = today_run_date
    earlier_start = (today_dt - timedelta(days=2 * window_days)).isoformat()
    earlier_end = recent_start

    recent_counts = _mention_counts_window(conn, base_relation, recent_start, recent_end)
    earlier_counts = _mention_counts_window(conn, base_relation, earlier_start, earlier_end)
    sources_7d = _distinct_sources_7d(conn, base_relation, recent_start, recent_end)

    rows: list[dict[str, Any]] = []
    first_seen_dates: list[str] = []

    for entity_id, today_data in today.items():
        meta = metadata.get(entity_id, {})
        label = meta.get("label") or entity_id
        type_ = meta.get("type") or "Other"
        first_seen = meta.get("first_seen") or today_run_date

        prior_data = prior.get(entity_id)
        rank_prior: int | None = prior_data["rank"] if prior_data else None
        is_new = rank_prior is None
        rank_delta: int | None = (
            rank_prior - today_data["rank"] if rank_prior is not None else None
        )

        recent = recent_counts.get(entity_id, 0)
        earlier = earlier_counts.get(entity_id, 0)
        velocity_raw = _compute_velocity_raw(recent, earlier)
        velocity_ci_lower = _velocity_ci_lower(recent, earlier)

        # Persistence-of-rise (20.8): stored velocity above 1 in both this
        # run's window and the prior run's — two consecutive non-overlapping
        # windows. Small-N runs store gated velocity 1.0 and never qualify.
        today_velocity = today_data.get("velocity")
        prior_velocity = prior_data.get("velocity") if prior_data else None
        sustained = bool(
            today_velocity is not None and today_velocity > 1
            and prior_velocity is not None and prior_velocity > 1
        )

        # Structural emergence (20.9): 7d change in the daily-persisted
        # bridge_score, same prior-run pattern as rank_delta.
        today_bridge = today_data.get("bridge_score")
        prior_bridge = prior_data.get("bridge_score") if prior_data else None
        bridge_delta: float | None = (
            today_bridge - prior_bridge
            if today_bridge is not None and prior_bridge is not None
            else None
        )

        try:
            days_since = (today_dt - date.fromisoformat(first_seen[:10])).days
            days_since = max(0, days_since)
        except (TypeError, ValueError):
            days_since = 0

        rows.append({
            "entity_id": entity_id,
            "label": label,
            "type": type_,
            "current_rank": today_data["rank"],
            "rank_prior": rank_prior,
            "rank_delta": rank_delta,
            "is_new": is_new,
            "velocity_raw": velocity_raw,
            "velocity_ci_lower": velocity_ci_lower,
            "sustained": sustained,
            "bridge_delta": bridge_delta,
            "mention_count_7d": today_data["mention_count_7d"],
            "mention_count_30d": today_data["mention_count_30d"],
            "first_seen": first_seen[:10],
            "days_since_first_seen": days_since,
            "distinct_sources_7d": sources_7d.get(entity_id, 0),
            "in_trending_view": today_data["in_trending_view"],
            "trend_score": today_data["trend_score"],
        })

        if first_seen:
            first_seen_dates.append(first_seen[:10])

    rows.sort(key=lambda r: r["current_rank"])

    date_range = {
        "start": min(first_seen_dates) if first_seen_dates else None,
        "end": today_run_date,
    }
    return rows, date_range


def export_movers(
    db_path: Path,
    output_dir: Path,
    domain: str,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> Path:
    """Build and write movers.json to output_dir.

    Returns the path to the written file.
    """
    conn = init_db(db_path)
    profile = get_active_profile()
    base_relation: str = profile["base_relation"]
    trend_weights = profile["trend_weights"]

    rows, date_range = build_movers_rows(conn, window_days, base_relation)

    output = {
        "meta": {
            "view": "movers",
            "domain": domain,
            "rank_window_days": window_days,
            "rowCount": len(rows),
            "exportedAt": utc_now_iso(),
            "dateRange": date_range,
            "scoring": {
                "novelty_decay_lambda": float(
                    trend_weights.get("novelty_decay_lambda", 0.05)
                ),
                "min_mentions_for_velocity": int(
                    trend_weights.get("min_mentions_for_velocity", 3)
                ),
                "velocity_ci": {
                    "method": "katz-log",
                    "z": VELOCITY_CI_Z,
                    "one_sided": True,
                    "continuity_correction": 0.5,
                },
                "sustained_windows": 2,
            },
        },
        "rows": rows,
    }

    _validate_against_schema(output)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "movers.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Exported Movers view to {output_path}")
    print(f"  - {len(rows)} rows (window: {window_days} days)")

    conn.close()
    return output_path


def _validate_against_schema(payload: dict[str, Any]) -> None:
    """Validate the output against schemas/movers.json before write.

    Errors are fatal — better to fail loudly than to publish an invalid
    contract. Skipped silently if jsonschema isn't installed (matches the
    pattern used by tests for environments without the dep).
    """
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "movers.json"
    if not schema_path.exists():
        return
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        msgs = "; ".join(
            f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in errors[:5]
        )
        raise ValueError(f"movers.json failed schema validation: {msgs}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the Movers view in tabular JSON form."
    )
    parser.add_argument(
        "--domain", default=None,
        help="Domain slug (default: PREDICTOR_DOMAIN env or active profile)",
    )
    parser.add_argument(
        "--db", default=None,
        help="Path to SQLite database (default: data/db/{domain}.db)",
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="Output directory (default: data/graphs/{domain}/{today})",
    )
    parser.add_argument(
        "--window-days", type=int, default=DEFAULT_WINDOW_DAYS,
        help=f"Days back for rank_prior / velocity comparison "
             f"(default: {DEFAULT_WINDOW_DAYS})",
    )
    args = parser.parse_args()

    from util.paths import get_db_path, get_graphs_dir

    domain = args.domain or os.environ.get("PREDICTOR_DOMAIN") \
        or get_active_profile().get("slug", "ai")
    if args.db is None:
        args.db = str(get_db_path(domain))
    output_dir = (
        Path(args.output_dir) if args.output_dir
        else get_graphs_dir(domain) / date.today().isoformat()
    )

    export_movers(
        db_path=Path(args.db),
        output_dir=output_dir,
        domain=domain,
        window_days=args.window_days,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
