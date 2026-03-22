"""Export trending view in Cytoscape.js format.

Bridges the gap between TrendScorer (flat scores) and the web client
(Cytoscape elements format with meta object).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
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
from db import init_db
from graph import GraphExporter, build_node, build_edge
from trend import TrendScorer
from util import utc_now_iso


def export_trending(
    db_path: Path,
    output_dir: Path,
    top_n: int,
    generate_narratives: bool = False,
    narrative_model: str = "gpt-5-nano",
) -> Path:
    """Export trending entities in Cytoscape.js format.

    Args:
        db_path: Path to SQLite database
        output_dir: Directory to write trending.json
        top_n: Maximum trending entities
        generate_narratives: If True, add LLM-generated "WHY" narratives
        narrative_model: Model for narrative generation

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

    # Step 2: Get relations where BOTH source and target are trending,
    # then aggregate cross-document edges into single logical edges
    all_relations = exporter._get_relations()
    filtered_relations = [
        r for r in all_relations
        if r["source_id"] in trending_ids and r["target_id"] in trending_ids
    ]

    # Step 2b: Find isolated trending entities (no edges to other trending
    # entities) and pull in bridge entities that reconnect them.
    # This counters the entity-suppression effect where generic hub nodes
    # (e.g. "AI", "machine learning") were removed from extraction, leaving
    # specific entities with no direct relations to each other.
    connected_ids = set()
    for r in filtered_relations:
        connected_ids.add(r["source_id"])
        connected_ids.add(r["target_id"])
    isolated_ids = trending_ids - connected_ids

    bridge_ids: set[str] = set()
    bridge_relations: list[dict] = []
    if isolated_ids:
        # For each non-trending entity, check if it connects an isolated
        # trending entity to ANY other trending entity (isolated or not).
        # Candidate edges: one endpoint is an isolated trending entity,
        # the other endpoint is a non-trending entity.
        candidate_bridges: dict[str, set[str]] = {}  # bridge_id → {trending ids it touches}
        for r in all_relations:
            src, tgt = r["source_id"], r["target_id"]
            # Case 1: isolated trending → non-trending
            if src in isolated_ids and tgt not in trending_ids:
                candidate_bridges.setdefault(tgt, set()).add(src)
            # Case 2: non-trending → isolated trending
            if tgt in isolated_ids and src not in trending_ids:
                candidate_bridges.setdefault(src, set()).add(tgt)
            # Case 3: non-trending connects to a non-isolated trending entity
            if src not in trending_ids and tgt in trending_ids:
                candidate_bridges.setdefault(src, set()).add(tgt)
            if tgt not in trending_ids and src in trending_ids:
                candidate_bridges.setdefault(tgt, set()).add(src)

        # Keep bridge entities that connect at least one isolated entity
        # to at least one OTHER trending entity (isolated or connected).
        for b_id, touched in candidate_bridges.items():
            has_isolated = bool(touched & isolated_ids)
            connects_multiple = len(touched) >= 2
            if has_isolated and connects_multiple:
                bridge_ids.add(b_id)

        # Collect relations that involve bridge entities and trending entities
        for r in all_relations:
            src, tgt = r["source_id"], r["target_id"]
            if src in bridge_ids and tgt in trending_ids:
                bridge_relations.append(r)
            elif tgt in bridge_ids and src in trending_ids:
                bridge_relations.append(r)

        if bridge_ids:
            print(f"  - {len(isolated_ids)} isolated trending entities, "
                  f"added {len(bridge_ids)} bridge entities to reconnect")

    all_view_relations = filtered_relations + bridge_relations
    merged_relations = exporter._aggregate_relations(all_view_relations)

    # Step 3: Build Cytoscape nodes with trend scores
    all_entities = exporter._get_entities()
    included_ids = trending_ids | bridge_ids
    filtered_entities = [e for e in all_entities if e["entity_id"] in included_ids]

    nodes = []
    first_seen_dates = []
    last_seen_dates = []

    for entity in filtered_entities:
        node = build_node(entity)
        eid = entity["entity_id"]
        # Enrich with trend scores (bridge entities get zeroes)
        scores = trend_lookup.get(eid, {})
        node["data"]["velocity"] = scores.get("velocity", 0)
        node["data"]["novelty"] = scores.get("novelty", 0)
        node["data"]["trend_score"] = scores.get("trend_score", 0)
        node["data"]["mention_count_7d"] = scores.get("mention_count_7d", 0)
        node["data"]["mention_count_30d"] = scores.get("mention_count_30d", 0)
        if eid in bridge_ids:
            node["data"]["bridge"] = True
        nodes.append(node)

        # Collect dates for meta range
        if entity.get("first_seen"):
            first_seen_dates.append(entity["first_seen"][:10])
        if entity.get("last_seen"):
            last_seen_dates.append(entity["last_seen"][:10])

    edges = exporter._build_aggregated_edges(merged_relations)
    edges = GraphExporter._strip_orphan_edges(nodes, edges)

    # Step 3b: Generate trend narratives ("What's Hot and WHY")
    if generate_narratives and trending:
        try:
            from trend.narratives import generate_narratives as _gen_narratives
            narratives = _gen_narratives(conn, trending, model=narrative_model)
            for node in nodes:
                eid = node["data"]["id"]
                narrative = narratives.get(eid)
                if narrative:
                    node["data"]["narrative"] = narrative
            if narratives:
                print(f"  - Generated narratives for {len(narratives)} entities")
        except Exception as e:
            print(f"  - Narrative generation failed (non-fatal): {e}")

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
        "--domain", default=None,
        help="Domain slug (default: ai or PREDICTOR_DOMAIN env var)",
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
        "--top-n", type=int, default=50,
        help="Maximum trending entities (default: 50)",
    )
    parser.add_argument(
        "--days", type=int, default=DEFAULT_DATE_WINDOW_DAYS,
        help=f"Date window for meta.dateRange (default: {DEFAULT_DATE_WINDOW_DAYS}). "
             "0 = compute range from entity dates.",
    )
    parser.add_argument(
        "--narratives", action="store_true",
        help="Generate LLM-powered trend narratives (What's Hot and WHY)",
    )
    parser.add_argument(
        "--narrative-model", default="gpt-5-nano",
        help="Model for narrative generation (default: gpt-5-nano)",
    )
    args = parser.parse_args()

    from util.paths import get_db_path, get_graphs_dir
    if args.db is None:
        args.db = str(get_db_path(args.domain))
    output_dir = Path(args.output_dir) if args.output_dir else get_graphs_dir(args.domain) / date.today().isoformat()

    export_trending(
        db_path=Path(args.db),
        output_dir=output_dir,
        top_n=args.top_n,
        generate_narratives=args.narratives,
        narrative_model=args.narrative_model,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
