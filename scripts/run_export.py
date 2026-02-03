#!/usr/bin/env python3
"""
Graph Export Runner

Exports graph data in Cytoscape.js format for visualization.
Generates three views: mentions, claims, and dependencies.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from db import init_db
from graph import GraphExporter


def count_elements(json_path):
    """Count nodes and edges in a Cytoscape JSON file."""
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)

        elements = data.get('elements', {})
        node_count = len(elements.get('nodes', []))
        edge_count = len(elements.get('edges', []))

        return node_count, edge_count
    except Exception:
        return 0, 0


def main():
    parser = argparse.ArgumentParser(
        description="Export graph data in Cytoscape.js format"
    )
    parser.add_argument(
        '--db',
        default='data/db/predictor.db',
        help='Database path (default: data/db/predictor.db)'
    )
    parser.add_argument(
        '--output-dir',
        default='data/graphs',
        help='Output base directory (default: data/graphs)'
    )
    parser.add_argument(
        '--date',
        default=str(date.today()),
        help='Export date for subdirectory name (default: today YYYY-MM-DD)'
    )

    args = parser.parse_args()

    # Resolve paths
    repo_root = Path(__file__).parent.parent
    db_path = repo_root / args.db
    output_dir = repo_root / args.output_dir / args.date

    # Validate database
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        print("Run 'make init-db' and 'make ingest' first.", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Connect to database
    conn = init_db(str(db_path))

    try:
        # Create exporter
        exporter = GraphExporter(conn)

        # Export all views
        paths = exporter.export_all_views(output_dir)

        # Print results
        print(f"\nExported 3 views to {output_dir}/:")

        for view_name in ['mentions', 'claims', 'dependencies']:
            json_path = output_dir / f"{view_name}.json"
            if json_path.exists():
                node_count, edge_count = count_elements(json_path)
                print(f"  - {view_name}.json ({node_count} nodes, {edge_count} edges)")
            else:
                print(f"  - {view_name}.json (not created)", file=sys.stderr)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
