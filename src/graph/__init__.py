"""Graph export module for Cytoscape.js format.

Exports entities and relations to Cytoscape.js-compatible JSON.
Supports multiple views: mentions, claims, dependencies, trending.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
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


def build_edge(relation: dict[str, Any], evidence: list[dict[str, Any]] = None) -> dict[str, Any]:
    """Build a Cytoscape edge from a relation dict.

    Args:
        relation: Relation dict with source_id, target_id, rel, etc.
        evidence: List of evidence records for this relation

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

    # Include evidence if provided
    if evidence:
        data["evidence"] = [
            {
                "docId": ev.get("doc_id"),
                "url": ev.get("url"),
                "published": ev.get("published"),
                "snippet": ev.get("snippet"),
            }
            for ev in evidence
        ]

    return {"data": data}


class GraphExporter:
    """Export graph data to Cytoscape.js format.

    Supports multiple views:
    - mentions: Document ↔ Entity mentions
    - claims: Semantic entity-to-entity relations (excludes MENTIONS)
    - dependencies: Dependency relations (USES_*, DEPENDS_ON, etc.)
    - all: Everything combined

    All views accept optional start_date / end_date parameters that filter
    by article publication date (not pipeline fetch date).
    """

    def __init__(self, conn: sqlite3.Connection):
        """Initialize exporter with database connection.

        Args:
            conn: SQLite database connection
        """
        self.conn = conn

    def _get_entities(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get entities from database, optionally filtered by date range.

        An entity is included if it was active during the window:
        last_seen >= start_date AND first_seen <= end_date.

        Args:
            start_date: Earliest published date (ISO). None = no lower bound.
            end_date: Latest published date (ISO). None = no upper bound.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if start_date:
            clauses.append("(last_seen IS NULL OR last_seen >= ?)")
            params.append(start_date)
        if end_date:
            clauses.append("(first_seen IS NULL OR first_seen <= ?)")
            params.append(end_date)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        cursor = self.conn.execute(f"SELECT * FROM entities{where}", params)

        entities = []
        for row in cursor.fetchall():
            entity = dict(row)
            if entity.get("aliases"):
                entity["aliases"] = json.loads(entity["aliases"])
            if entity.get("external_ids"):
                entity["external_ids"] = json.loads(entity["external_ids"])
            entities.append(entity)
        return entities

    def _get_documents(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get documents from database, optionally filtered by published_at.

        Args:
            start_date: Earliest published date (ISO). None = no lower bound.
            end_date: Latest published date (ISO). None = no upper bound.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if start_date:
            clauses.append("published_at >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("published_at <= ?")
            params.append(end_date)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        cursor = self.conn.execute(f"SELECT * FROM documents{where}", params)
        return [dict(row) for row in cursor.fetchall()]

    def _get_relations(
        self,
        relation_filter: Optional[set[str]] = None,
        exclude_relations: Optional[set[str]] = None,
        kinds: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get relations from database with optional filtering.

        Args:
            relation_filter: If set, only include these relation types
            exclude_relations: If set, exclude these relation types
            kinds: If set, only include these kinds (asserted, inferred, hypothesis)
            start_date: Earliest published date of source doc (ISO). None = no lower bound.
            end_date: Latest published date of source doc (ISO). None = no upper bound.

        Returns:
            List of relation dicts
        """
        # When date filtering, join against documents.published_at
        if start_date or end_date:
            clauses: list[str] = []
            params: list[Any] = []
            if start_date:
                clauses.append("d.published_at >= ?")
                params.append(start_date)
            if end_date:
                clauses.append("d.published_at <= ?")
                params.append(end_date)
            where = " AND " + " AND ".join(clauses)
            cursor = self.conn.execute(
                f"SELECT r.* FROM relations r JOIN documents d ON r.doc_id = d.doc_id WHERE 1=1{where}",
                params,
            )
        else:
            cursor = self.conn.execute("SELECT * FROM relations")

        relations = []
        for row in cursor.fetchall():
            rel = dict(row)
            if relation_filter and rel["rel"] not in relation_filter:
                continue
            if exclude_relations and rel["rel"] in exclude_relations:
                continue
            if kinds and rel["kind"] not in kinds:
                continue
            relations.append(rel)

        return relations

    def _get_evidence_for_relation(self, relation_id: int) -> list[dict[str, Any]]:
        """Get evidence records for a relation.

        Uses the document URL from the documents table rather than the
        evidence URL, which may have been corrupted by the LLM.
        """
        cursor = self.conn.execute(
            """SELECT e.*, COALESCE(d.url, e.url) AS url
               FROM evidence e
               LEFT JOIN documents d ON e.doc_id = d.doc_id
               WHERE e.relation_id = ?""",
            (relation_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def _build_edges_with_evidence(self, relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Build edges including evidence data."""
        edges = []
        for rel in relations:
            relation_id = rel.get("relation_id")
            evidence = self._get_evidence_for_relation(relation_id) if relation_id else []
            edges.append(build_edge(rel, evidence))
        return edges

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
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Export all entities and relations.

        Args:
            kinds: Optional filter for relation kinds
            start_date: Filter by published date >= (ISO). None = no lower bound.
            end_date: Filter by published date <= (ISO). None = no upper bound.

        Returns:
            Cytoscape elements dict
        """
        entities = self._get_entities(start_date=start_date, end_date=end_date)
        relations = self._get_relations(kinds=kinds, start_date=start_date, end_date=end_date)

        nodes = [build_node(e) for e in entities]
        edges = self._build_edges_with_evidence(relations)

        return {
            "elements": {
                "nodes": nodes,
                "edges": edges,
            }
        }

    def export_mentions(
        self,
        kinds: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Export mentions view (Document ↔ Entity).

        Includes document nodes and MENTIONS edges.

        Args:
            kinds: Optional filter for relation kinds
            start_date: Filter by published date >= (ISO). None = no lower bound.
            end_date: Filter by published date <= (ISO). None = no upper bound.

        Returns:
            Cytoscape elements dict
        """
        # Get MENTIONS relations
        relations = self._get_relations(
            relation_filter={"MENTIONS"},
            kinds=kinds,
            start_date=start_date,
            end_date=end_date,
        )

        # Get documents
        documents = self._get_documents(start_date=start_date, end_date=end_date)
        doc_nodes = [build_document_node(d) for d in documents]

        # Get referenced entities
        entities = self._get_entities(start_date=start_date, end_date=end_date)
        entity_nodes = [build_node(e) for e in entities]

        # Combine and filter to referenced nodes only
        all_nodes = doc_nodes + entity_nodes
        referenced_ids = self._get_referenced_entity_ids(relations)
        nodes = self._filter_nodes_by_ids(all_nodes, referenced_ids)

        # Include document nodes that have mentions
        for doc_node in doc_nodes:
            if doc_node["data"]["id"] in referenced_ids:
                if doc_node not in nodes:
                    nodes.append(doc_node)

        edges = self._build_edges_with_evidence(relations)

        return {
            "elements": {
                "nodes": nodes,
                "edges": edges,
            }
        }

    def export_claims(
        self,
        kinds: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Export claims view (semantic entity-to-entity relations).

        Excludes document relations like MENTIONS.

        Args:
            kinds: Optional filter for relation kinds
            start_date: Filter by published date >= (ISO). None = no lower bound.
            end_date: Filter by published date <= (ISO). None = no upper bound.

        Returns:
            Cytoscape elements dict
        """
        # Get semantic relations (exclude document relations)
        relations = self._get_relations(
            exclude_relations=DOCUMENT_RELATIONS,
            kinds=kinds,
            start_date=start_date,
            end_date=end_date,
        )

        # Get entities
        entities = self._get_entities(start_date=start_date, end_date=end_date)
        entity_nodes = [build_node(e) for e in entities]

        # Filter to only nodes referenced in relations
        referenced_ids = self._get_referenced_entity_ids(relations)
        nodes = self._filter_nodes_by_ids(entity_nodes, referenced_ids)

        edges = self._build_edges_with_evidence(relations)

        return {
            "elements": {
                "nodes": nodes,
                "edges": edges,
            }
        }

    def export_dependencies(
        self,
        kinds: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Export dependencies view (USES_*, DEPENDS_ON, REQUIRES, etc.).

        Args:
            kinds: Optional filter for relation kinds
            start_date: Filter by published date >= (ISO). None = no lower bound.
            end_date: Filter by published date <= (ISO). None = no upper bound.

        Returns:
            Cytoscape elements dict
        """
        # Get dependency relations only
        relations = self._get_relations(
            relation_filter=DEPENDENCY_RELATIONS,
            kinds=kinds,
            start_date=start_date,
            end_date=end_date,
        )

        # Get entities
        entities = self._get_entities(start_date=start_date, end_date=end_date)
        entity_nodes = [build_node(e) for e in entities]

        # Filter to only nodes referenced in relations
        referenced_ids = self._get_referenced_entity_ids(relations)
        nodes = self._filter_nodes_by_ids(entity_nodes, referenced_ids)

        edges = self._build_edges_with_evidence(relations)

        return {
            "elements": {
                "nodes": nodes,
                "edges": edges,
            }
        }

    def _build_meta(
        self,
        view: str,
        elements: dict[str, Any],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build the meta object for an export.

        Args:
            view: View name
            elements: The elements dict (nodes + edges)
            start_date: Date range start (ISO) or None
            end_date: Date range end (ISO) or None

        Returns:
            Meta dict per AGENTS.md spec
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "view": view,
            "nodeCount": len(elements.get("nodes", [])),
            "edgeCount": len(elements.get("edges", [])),
            "exportedAt": now,
            "dateRange": {
                "start": start_date,
                "end": end_date,
            },
        }

    def export_to_file(
        self,
        output_dir: Path,
        view: str,
        kinds: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Path:
        """Export a view to a JSON file with meta header.

        Args:
            output_dir: Directory to write to
            view: View name (mentions, claims, dependencies, all)
            kinds: Optional filter for relation kinds
            start_date: Filter by published date >= (ISO). None = no lower bound.
            end_date: Filter by published date <= (ISO). None = no upper bound.

        Returns:
            Path to created file
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        export_kwargs = dict(kinds=kinds, start_date=start_date, end_date=end_date)

        if view == "mentions":
            data = self.export_mentions(**export_kwargs)
        elif view == "claims":
            data = self.export_claims(**export_kwargs)
        elif view == "dependencies":
            data = self.export_dependencies(**export_kwargs)
        elif view == "all":
            data = self.export_all(**export_kwargs)
        else:
            raise ValueError(f"Unknown view: {view}")

        # Add meta block
        data["meta"] = self._build_meta(
            view, data["elements"], start_date=start_date, end_date=end_date,
        )

        output_path = output_dir / f"{view}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path

    def export_all_views(
        self,
        output_dir: Path,
        kinds: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[Path]:
        """Export all standard views to files.

        Args:
            output_dir: Directory to write to
            kinds: Optional filter for relation kinds
            start_date: Filter by published date >= (ISO). None = no lower bound.
            end_date: Filter by published date <= (ISO). None = no upper bound.

        Returns:
            List of created file paths
        """
        views = ["mentions", "claims", "dependencies"]
        paths = []

        for view in views:
            path = self.export_to_file(
                output_dir, view, kinds=kinds,
                start_date=start_date, end_date=end_date,
            )
            paths.append(path)

        return paths
