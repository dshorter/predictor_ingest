"""Export graph views to Cytoscape.js JSON format.

Writes mentions.json, claims.json, and dependencies.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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
    args = parser.parse_args()

    output_dir = Path(args.output_dir) / args.date
    conn = init_db(Path(args.db))
    exporter = GraphExporter(conn)

    paths = exporter.export_all_views(output_dir)

    print(f"Exported {len(paths)} views to {output_dir}/:")
    for path in paths:
        # Read back to get node/edge counts
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        elements = data.get("elements", {})
        node_count = len(elements.get("nodes", []))
        edge_count = len(elements.get("edges", []))
        print(f"  - {path.name} ({node_count} nodes, {edge_count} edges)")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
