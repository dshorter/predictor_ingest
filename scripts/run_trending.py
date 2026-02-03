#!/usr/bin/env python3
"""
Trending Export Script

Exports trending entities and their relationships in Cytoscape.js format.
Bridges the format gap between TrendScorer (flat scores) and web client
(Cytoscape elements format).
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from db import init_db
from graph import GraphExporter, build_node, build_edge
from trend import TrendScorer
from util import utc_now_iso


def get_date_range(entities):
    """
    Calculate date range from entity first_seen and last_seen.

    Args:
        entities: List of entity dicts with first_seen and last_seen

    Returns:
        Dict with start and end dates, or None
    """
    if not entities:
        return None

    first_seen_dates = [e.get('first_seen') for e in entities if e.get('first_seen')]
    last_seen_dates = [e.get('last_seen') for e in entities if e.get('last_seen')]

    if not first_seen_dates or not last_seen_dates:
        return None

    return {
        "start": min(first_seen_dates),
        "end": max(last_seen_dates)
    }


def main():
    parser = argparse.ArgumentParser(
        description="Export trending entities in Cytoscape.js format"
    )
    parser.add_argument(
        '--db',
        default='data/db/predictor.db',
        help='Database path (default: data/db/predictor.db)'
    )
    parser.add_argument(
        '--output-dir',
        default=f'data/graphs/{date.today()}',
        help='Output directory (default: data/graphs/YYYY-MM-DD)'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=50,
        help='Maximum trending entities to export (default: 50)'
    )

    args = parser.parse_args()

    # Resolve paths
    repo_root = Path(__file__).parent.parent
    db_path = repo_root / args.db
    output_dir = repo_root / args.output_dir

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
        # Create scorer and exporter
        scorer = TrendScorer(conn)
        exporter = GraphExporter(conn)

        # Step 1: Get trending entity IDs
        print("Computing trend scores...", file=sys.stderr)
        trending = scorer.get_trending(limit=args.top_n)
        trending_ids = {t["entity_id"] for t in trending}
        trend_lookup = {t["entity_id"]: t for t in trending}

        if not trending:
            print("No trending entities found", file=sys.stderr)
            sys.exit(0)

        print(f"Found {len(trending)} trending entities", file=sys.stderr)

        # Step 2: Get all relations and filter to trending-only
        all_relations = exporter._get_relations()
        filtered_relations = [
            r for r in all_relations
            if r["source_id"] in trending_ids and r["target_id"] in trending_ids
        ]

        print(f"Found {len(filtered_relations)} relations between trending entities", file=sys.stderr)

        # Step 3: Get entities and build Cytoscape nodes
        all_entities = exporter._get_entities()
        filtered_entities = [e for e in all_entities if e["entity_id"] in trending_ids]

        nodes = []
        for entity in filtered_entities:
            node = build_node(entity)

            # Enrich with trend scores
            scores = trend_lookup.get(entity["entity_id"], {})
            node["data"]["velocity"] = scores.get("velocity", 0)
            node["data"]["novelty"] = scores.get("novelty", 0)
            node["data"]["trend_score"] = scores.get("trend_score", 0)
            node["data"]["mention_count_7d"] = scores.get("mention_count_7d", 0)
            node["data"]["mention_count_30d"] = scores.get("mention_count_30d", 0)

            nodes.append(node)

        # Step 4: Build Cytoscape edges
        edges = [build_edge(r) for r in filtered_relations]

        # Step 5: Calculate date range
        date_range = get_date_range(filtered_entities)

        # Step 6: Write Cytoscape format with meta object
        output = {
            "meta": {
                "view": "trending",
                "nodeCount": len(nodes),
                "edgeCount": len(edges),
                "exportedAt": utc_now_iso(),
                "dateRange": date_range or {"start": None, "end": None}
            },
            "elements": {
                "nodes": nodes,
                "edges": edges
            }
        }

        output_path = output_dir / "trending.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\nExported trending view to {output_path}")
        print(f"  - {len(nodes)} nodes, {len(edges)} edges (top {args.top_n} by trend score)")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
