"""Export graph views to Cytoscape.js JSON format.

Writes mentions.json, claims.json, and dependencies.json.
Supports date range filtering by article publication date.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import DEFAULT_DATE_WINDOW_DAYS
from db import init_db
from graph import GraphExporter


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export graph views to Cytoscape.js JSON."
    )
    parser.add_argument(
        "--db", default="data/db/predictor.db",
        help="Path to SQLite database (default: data/db/predictor.db)",
    )
    parser.add_argument(
        "--output-dir", default="data/graphs",
        help="Base output directory (default: data/graphs)",
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
    args = parser.parse_args()

    # Resolve date range
    end_date = args.end_date or args.date
    if args.start_date:
        start_date = args.start_date
    elif args.days > 0:
        start_date = (date.fromisoformat(end_date) - timedelta(days=args.days)).isoformat()
    else:
        start_date = None  # No lower bound

    output_dir = Path(args.output_dir) / args.date
    conn = init_db(Path(args.db))
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
