"""Export trending view in Cytoscape.js format.

Bridges the gap between TrendScorer (flat scores) and the web client
(Cytoscape elements format with meta object).
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
from graph import GraphExporter, build_node, build_edge
from trend import TrendScorer
from util import utc_now_iso


def export_trending(
    db_path: Path,
    output_dir: Path,
    top_n: int,
) -> Path:
    """Export trending entities in Cytoscape.js format.

    Args:
        db_path: Path to SQLite database
        output_dir: Directory to write trending.json
        top_n: Maximum trending entities

    Returns:
        Path to created file
    """
    conn = init_db(db_path)
    scorer = TrendScorer(conn)
    exporter = GraphExporter(conn)

    # Step 1: Get trending entity IDs and scores
    trending = scorer.get_trending(limit=top_n)
    trending_ids = {t["entity_id"] for t in trending}
    trend_lookup = {t["entity_id"]: t for t in trending}

    if not trending_ids:
        print("No trending entities found")
        conn.close()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "trending.json"
        empty = {
            "meta": {
                "view": "trending",
                "nodeCount": 0,
                "edgeCount": 0,
                "exportedAt": utc_now_iso(),
                "dateRange": {"start": None, "end": None},
            },
            "elements": {"nodes": [], "edges": []},
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(empty, f, indent=2, ensure_ascii=False)
        return output_path

    # Step 2: Get relations where BOTH source and target are trending
    all_relations = exporter._get_relations()
    filtered_relations = [
        r for r in all_relations
        if r["source_id"] in trending_ids and r["target_id"] in trending_ids
    ]

    # Step 3: Build Cytoscape nodes with trend scores
    all_entities = exporter._get_entities()
    filtered_entities = [e for e in all_entities if e["entity_id"] in trending_ids]

    nodes = []
    first_seen_dates = []
    last_seen_dates = []

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

        # Collect dates for meta range
        if entity.get("first_seen"):
            first_seen_dates.append(entity["first_seen"][:10])
        if entity.get("last_seen"):
            last_seen_dates.append(entity["last_seen"][:10])

    edges = [build_edge(r) for r in filtered_relations]

    # Step 4: Compute date range
    date_start = min(first_seen_dates) if first_seen_dates else None
    date_end = max(last_seen_dates) if last_seen_dates else date.today().isoformat()

    # Step 5: Write Cytoscape format with meta object
    output_dir.mkdir(parents=True, exist_ok=True)
    output = {
        "meta": {
            "view": "trending",
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
            "exportedAt": utc_now_iso(),
            "dateRange": {"start": date_start, "end": date_end},
        },
        "elements": {
            "nodes": nodes,
            "edges": edges,
        },
    }

    output_path = output_dir / "trending.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Exported trending view to {output_path}")
    print(f"  - {len(nodes)} nodes, {len(edges)} edges (top {top_n} by trend score)")

    conn.close()
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export trending view in Cytoscape.js format."
    )
    parser.add_argument(
        "--db", default="data/db/predictor.db",
        help="Path to SQLite database (default: data/db/predictor.db)",
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="Output directory (default: data/graphs/{today})",
    )
    parser.add_argument(
        "--top-n", type=int, default=50,
        help="Maximum trending entities (default: 50)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else Path("data/graphs") / date.today().isoformat()

    export_trending(
        db_path=Path(args.db),
        output_dir=output_dir,
        top_n=args.top_n,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
