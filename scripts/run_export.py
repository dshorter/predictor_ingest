"""Export graph views to Cytoscape.js JSON format.

Writes mentions.json, claims.json, and dependencies.json.
Supports date range filtering by article publication date.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _bootstrap_domain() -> None:
    """Set PREDICTOR_DOMAIN from --domain arg before any domain-aware imports."""
    for i, arg in enumerate(sys.argv):
        if arg == "--domain" and i + 1 < len(sys.argv):
            os.environ["PREDICTOR_DOMAIN"] = sys.argv[i + 1]
            return
        if arg.startswith("--domain="):
            os.environ["PREDICTOR_DOMAIN"] = arg.split("=", 1)[1]
            return


_bootstrap_domain()

from config import DEFAULT_DATE_WINDOW_DAYS
from db import get_latest_published_date, init_db
from domain import get_active_profile
from graph import GraphExporter


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export graph views to Cytoscape.js JSON."
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
        "--output-dir", default=None,
        help="Base output directory (default: data/graphs/{domain})",
    )
    parser.add_argument(
        "--date", default=date.today().isoformat(),
        help="Date for output subdirectory, YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--days", type=int, default=DEFAULT_DATE_WINDOW_DAYS,
        help=f"Number of days to include (default: {DEFAULT_DATE_WINDOW_DAYS}). "
             "0 = no date filter (all data).",
    )
    parser.add_argument(
        "--start-date", default=None,
        help="Explicit start date (ISO). Overrides --days.",
    )
    parser.add_argument(
        "--end-date", default=None,
        help="Explicit end date (ISO). Defaults to --date value.",
    )
    parser.add_argument(
        "--anchor", choices=["today", "latest"], default=None,
        help="Date anchor for the export window. 'today' uses --date (default for "
             "live domains). 'latest' pins end_date to MAX(documents.published_at) "
             "so the graph stays populated when ingestion is paused. If omitted, "
             "reads freshness_anchor from the domain profile (default: today).",
    )
    args = parser.parse_args()

    # Resolve domain-scoped defaults
    from util.paths import get_db_path, get_graphs_dir
    if args.db is None:
        args.db = str(get_db_path(args.domain))
    if args.output_dir is None:
        args.output_dir = str(get_graphs_dir(args.domain))

    # Resolve anchor: explicit CLI flag > domain profile > "today"
    if args.anchor is None:
        try:
            profile = get_active_profile()
            anchor = profile.get("freshness_anchor", "today")
        except Exception:
            anchor = "today"
    else:
        anchor = args.anchor

    output_dir = Path(args.output_dir) / args.date
    conn = init_db(Path(args.db))

    # Resolve date range. With anchor=latest, end_date pins to the most recent
    # article instead of today; this keeps demo graphs populated for paused
    # domains. Explicit --end-date / --start-date still win over anchor.
    if args.end_date:
        end_date = args.end_date
    elif anchor == "latest":
        latest = get_latest_published_date(conn)
        end_date = latest or args.date
        if latest:
            print(f"Anchor=latest: end_date pinned to {end_date} "
                  f"(MAX documents.published_at)")
        else:
            print("Anchor=latest: no documents with published_at; "
                  f"falling back to {args.date}")
    else:
        end_date = args.date

    if args.start_date:
        start_date = args.start_date
    elif args.days > 0:
        start_date = (date.fromisoformat(end_date) - timedelta(days=args.days)).isoformat()
    else:
        start_date = None  # No lower bound

    exporter = GraphExporter(conn)

    paths = exporter.export_all_views(
        output_dir,
        start_date=start_date,
        end_date=end_date,
    )

    date_desc = f"{start_date} to {end_date}" if start_date else f"all data through {end_date}"
    print(f"Exported {len(paths)} views to {output_dir}/ (date range: {date_desc}):")
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        meta = data.get("meta", {})
        node_count = meta.get("nodeCount", 0)
        edge_count = meta.get("edgeCount", 0)
        print(f"  - {path.name} ({node_count} nodes, {edge_count} edges)")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
