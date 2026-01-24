"""Graph export module for Cytoscape.js format.

Exports entities and relations to Cytoscape.js-compatible JSON.
Supports multiple views: mentions, claims, dependencies, trending.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
import sqlite3


# Dependency relations per AGENTS.md
DEPENDENCY_RELATIONS = frozenset([
    "USES_TECH", "USES_MODEL", "USES_DATASET",
    "TRAINED_ON", "EVALUATED_ON",
    "INTEGRATES_WITH", "DEPENDS_ON", "REQUIRES",
    "PRODUCES",
])

# Document relations (not semantic entity-to-entity)
DOCUMENT_RELATIONS = frozenset([
    "MENTIONS", "CITES", "ANNOUNCES", "REPORTED_BY",
])


def build_node(entity: dict[str, Any]) -> dict[str, Any]:
    """Build a Cytoscape node from an entity dict.

    Args:
        entity: Entity dict with entity_id, name, type, etc.

    Returns:
        Cytoscape node dict with data property
    """
    data = {
        "id": entity["entity_id"],
        "label": entity["name"],
        "type": entity["type"],
    }

    # Optional fields
    if entity.get("aliases"):
        data["aliases"] = entity["aliases"]
    if entity.get("first_seen"):
        data["firstSeen"] = entity["first_seen"]
    if entity.get("last_seen"):
        data["lastSeen"] = entity["last_seen"]
    if entity.get("external_ids"):
        data["externalIds"] = entity["external_ids"]

    return {"data": data}


def build_document_node(doc: dict[str, Any]) -> dict[str, Any]:
    """Build a Cytoscape node from a document dict.

    Args:
        doc: Document dict with doc_id, title, url, etc.

    Returns:
        Cytoscape node dict with data property
    """
    data = {
        "id": f"doc:{doc['doc_id']}",
        "label": doc.get("title") or doc["doc_id"],
        "type": "Document",
    }

    # Optional fields
    if doc.get("url"):
        data["url"] = doc["url"]
    if doc.get("source"):
        data["source"] = doc["source"]
    if doc.get("published_at"):
        data["publishedAt"] = doc["published_at"]

    return {"data": data}


def build_edge(relation: dict[str, Any]) -> dict[str, Any]:
    """Build a Cytoscape edge from a relation dict.

    Args:
        relation: Relation dict with source_id, target_id, rel, etc.

    Returns:
        Cytoscape edge dict with data property
    """
    source = relation["source_id"]
    target = relation["target_id"]
    rel_id = relation.get("relation_id", 0)

    data = {
        "id": f"e:{rel_id}:{source}->{target}",
        "source": source,
        "target": target,
        "rel": relation["rel"],
        "kind": relation["kind"],
        "confidence": relation["confidence"],
    }

    # Optional fields
    if relation.get("doc_id"):
        data["docId"] = relation["doc_id"]
    if relation.get("verb_raw"):
        data["verbRaw"] = relation["verb_raw"]

    return {"data": data}


class GraphExporter:
    """Export graph data to Cytoscape.js format.

    Supports multiple views:
    - mentions: Document ↔ Entity mentions
    - claims: Semantic entity-to-entity relations (excludes MENTIONS)
    - dependencies: Dependency relations (USES_*, DEPENDS_ON, etc.)
    - all: Everything combined
    """

    def __init__(self, conn: sqlite3.Connection):
        """Initialize exporter with database connection.

        Args:
            conn: SQLite database connection
        """
        self.conn = conn

    def _get_entities(self) -> list[dict[str, Any]]:
        """Get all entities from database."""
        cursor = self.conn.execute("SELECT * FROM entities")
        entities = []
        for row in cursor.fetchall():
            entity = dict(row)
            # Parse JSON fields
            if entity.get("aliases"):
                import json as json_mod
                entity["aliases"] = json_mod.loads(entity["aliases"])
            if entity.get("external_ids"):
                import json as json_mod
                entity["external_ids"] = json_mod.loads(entity["external_ids"])
            entities.append(entity)
        return entities

    def _get_documents(self) -> list[dict[str, Any]]:
        """Get all documents from database."""
        cursor = self.conn.execute("SELECT * FROM documents")
        return [dict(row) for row in cursor.fetchall()]

    def _get_relations(
        self,
        relation_filter: Optional[set[str]] = None,
        exclude_relations: Optional[set[str]] = None,
        kinds: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Get relations from database with optional filtering.

        Args:
            relation_filter: If set, only include these relation types
            exclude_relations: If set, exclude these relation types
            kinds: If set, only include these kinds (asserted, inferred, hypothesis)

        Returns:
            List of relation dicts
        """
        cursor = self.conn.execute("SELECT * FROM relations")
        relations = []

        for row in cursor.fetchall():
            rel = dict(row)

            # Apply filters
            if relation_filter and rel["rel"] not in relation_filter:
                continue
            if exclude_relations and rel["rel"] in exclude_relations:
                continue
            if kinds and rel["kind"] not in kinds:
                continue

            relations.append(rel)

        return relations

    def _get_referenced_entity_ids(
        self,
        relations: list[dict[str, Any]]
    ) -> set[str]:
        """Get entity IDs referenced in relations."""
        ids = set()
        for rel in relations:
            ids.add(rel["source_id"])
            ids.add(rel["target_id"])
        return ids

    def _filter_nodes_by_ids(
        self,
        nodes: list[dict[str, Any]],
        ids: set[str],
    ) -> list[dict[str, Any]]:
        """Filter nodes to only include those with matching IDs."""
        return [n for n in nodes if n["data"]["id"] in ids]

    def export_all(
        self,
        kinds: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Export all entities and relations.

        Args:
            kinds: Optional filter for relation kinds

        Returns:
            Cytoscape elements dict
        """
        entities = self._get_entities()
        relations = self._get_relations(kinds=kinds)

        nodes = [build_node(e) for e in entities]
        edges = [build_edge(r) for r in relations]

        return {
            "elements": {
                "nodes": nodes,
                "edges": edges,
            }
        }

    def export_mentions(
        self,
        kinds: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Export mentions view (Document ↔ Entity).

        Includes document nodes and MENTIONS edges.

        Args:
            kinds: Optional filter for relation kinds

        Returns:
            Cytoscape elements dict
        """
        # Get MENTIONS relations
        relations = self._get_relations(
            relation_filter={"MENTIONS"},
            kinds=kinds,
        )

        # Get documents
        documents = self._get_documents()
        doc_nodes = [build_document_node(d) for d in documents]

        # Get referenced entities
        entities = self._get_entities()
        entity_nodes = [build_node(e) for e in entities]

        # Combine and filter to referenced nodes only
        all_nodes = doc_nodes + entity_nodes
        referenced_ids = self._get_referenced_entity_ids(relations)
        nodes = self._filter_nodes_by_ids(all_nodes, referenced_ids)

        # Include document nodes that have mentions
        doc_ids = {f"doc:{d['doc_id']}" for d in documents}
        for doc_node in doc_nodes:
            if doc_node["data"]["id"] in referenced_ids:
                if doc_node not in nodes:
                    nodes.append(doc_node)

        edges = [build_edge(r) for r in relations]

        return {
            "elements": {
                "nodes": nodes,
                "edges": edges,
            }
        }

    def export_claims(
        self,
        kinds: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Export claims view (semantic entity-to-entity relations).

        Excludes document relations like MENTIONS.

        Args:
            kinds: Optional filter for relation kinds

        Returns:
            Cytoscape elements dict
        """
        # Get semantic relations (exclude document relations)
        relations = self._get_relations(
            exclude_relations=DOCUMENT_RELATIONS,
            kinds=kinds,
        )

        # Get entities
        entities = self._get_entities()
        entity_nodes = [build_node(e) for e in entities]

        # Filter to only nodes referenced in relations
        referenced_ids = self._get_referenced_entity_ids(relations)
        nodes = self._filter_nodes_by_ids(entity_nodes, referenced_ids)

        edges = [build_edge(r) for r in relations]

        return {
            "elements": {
                "nodes": nodes,
                "edges": edges,
            }
        }

    def export_dependencies(
        self,
        kinds: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Export dependencies view (USES_*, DEPENDS_ON, REQUIRES, etc.).

        Args:
            kinds: Optional filter for relation kinds

        Returns:
            Cytoscape elements dict
        """
        # Get dependency relations only
        relations = self._get_relations(
            relation_filter=DEPENDENCY_RELATIONS,
            kinds=kinds,
        )

        # Get entities
        entities = self._get_entities()
        entity_nodes = [build_node(e) for e in entities]

        # Filter to only nodes referenced in relations
        referenced_ids = self._get_referenced_entity_ids(relations)
        nodes = self._filter_nodes_by_ids(entity_nodes, referenced_ids)

        edges = [build_edge(r) for r in relations]

        return {
            "elements": {
                "nodes": nodes,
                "edges": edges,
            }
        }

    def export_to_file(
        self,
        output_dir: Path,
        view: str,
        kinds: Optional[list[str]] = None,
    ) -> Path:
        """Export a view to a JSON file.

        Args:
            output_dir: Directory to write to
            view: View name (mentions, claims, dependencies, all)
            kinds: Optional filter for relation kinds

        Returns:
            Path to created file
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        if view == "mentions":
            data = self.export_mentions(kinds=kinds)
        elif view == "claims":
            data = self.export_claims(kinds=kinds)
        elif view == "dependencies":
            data = self.export_dependencies(kinds=kinds)
        elif view == "all":
            data = self.export_all(kinds=kinds)
        else:
            raise ValueError(f"Unknown view: {view}")

        output_path = output_dir / f"{view}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path

    def export_all_views(
        self,
        output_dir: Path,
        kinds: Optional[list[str]] = None,
    ) -> list[Path]:
        """Export all standard views to files.

        Args:
            output_dir: Directory to write to
            kinds: Optional filter for relation kinds

        Returns:
            List of created file paths
        """
        views = ["mentions", "claims", "dependencies"]
        paths = []

        for view in views:
            path = self.export_to_file(output_dir, view, kinds=kinds)
            paths.append(path)

        return paths
