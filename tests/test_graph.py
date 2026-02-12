"""Tests for graph export module.

Tests Cytoscape.js export functionality per AGENTS.md specification.
"""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

import pytest

from db import init_db, insert_entity, insert_relation, insert_evidence


# Import will be created
# from graph import (
#     export_mentions,
#     export_claims,
#     export_dependencies,
#     export_graph,
#     build_node,
#     build_edge,
#     GraphExporter,
# )


def _get_graph_module():
    """Lazy import of graph module."""
    import graph
    return graph


class TestBuildNode:
    """Test node building for Cytoscape format."""

    def test_minimal_node(self):
        """Test building a minimal node."""
        graph = _get_graph_module()
        entity = {
            "entity_id": "org:openai",
            "name": "OpenAI",
            "type": "Org",
        }
        node = graph.build_node(entity)

        assert node["data"]["id"] == "org:openai"
        assert node["data"]["label"] == "OpenAI"
        assert node["data"]["type"] == "Org"

    def test_node_with_aliases(self):
        """Test node with aliases."""
        graph = _get_graph_module()
        entity = {
            "entity_id": "org:openai",
            "name": "OpenAI",
            "type": "Org",
            "aliases": ["Open AI", "OpenAI Inc"],
        }
        node = graph.build_node(entity)

        assert node["data"]["aliases"] == ["Open AI", "OpenAI Inc"]

    def test_node_with_dates(self):
        """Test node with first/last seen dates."""
        graph = _get_graph_module()
        entity = {
            "entity_id": "model:gpt4",
            "name": "GPT-4",
            "type": "Model",
            "first_seen": "2023-03-14",
            "last_seen": "2026-01-20",
        }
        node = graph.build_node(entity)

        assert node["data"]["firstSeen"] == "2023-03-14"
        assert node["data"]["lastSeen"] == "2026-01-20"

    def test_document_node(self):
        """Test building a document node."""
        graph = _get_graph_module()
        doc = {
            "doc_id": "2026-01-15_arxiv_abc123",
            "title": "Transformer Improvements",
            "url": "https://arxiv.org/abs/2601.12345",
            "source": "arXiv CS.AI",
            "published_at": "2026-01-15",
        }
        node = graph.build_document_node(doc)

        assert node["data"]["id"] == "doc:2026-01-15_arxiv_abc123"
        assert node["data"]["label"] == "Transformer Improvements"
        assert node["data"]["type"] == "Document"
        assert node["data"]["url"] == "https://arxiv.org/abs/2601.12345"
        assert node["data"]["source"] == "arXiv CS.AI"


class TestBuildEdge:
    """Test edge building for Cytoscape format."""

    def test_minimal_edge(self):
        """Test building a minimal edge."""
        graph = _get_graph_module()
        relation = {
            "relation_id": 1,
            "source_id": "org:openai",
            "rel": "CREATED",
            "target_id": "model:gpt4",
            "kind": "asserted",
            "confidence": 0.95,
        }
        edge = graph.build_edge(relation)

        assert edge["data"]["source"] == "org:openai"
        assert edge["data"]["target"] == "model:gpt4"
        assert edge["data"]["rel"] == "CREATED"
        assert edge["data"]["kind"] == "asserted"
        assert edge["data"]["confidence"] == 0.95

    def test_edge_id_format(self):
        """Test edge ID follows expected format."""
        graph = _get_graph_module()
        relation = {
            "relation_id": 42,
            "source_id": "org:openai",
            "rel": "CREATED",
            "target_id": "model:gpt4",
            "kind": "asserted",
            "confidence": 0.9,
        }
        edge = graph.build_edge(relation)

        # Edge ID should be: e:{source}->{target} or include relation_id
        assert "id" in edge["data"]
        assert edge["data"]["id"].startswith("e:")

    def test_mentions_edge(self):
        """Test building a MENTIONS edge (doc → entity)."""
        graph = _get_graph_module()
        relation = {
            "relation_id": 1,
            "source_id": "doc:2026-01-15_arxiv_abc123",
            "rel": "MENTIONS",
            "target_id": "org:openai",
            "kind": "asserted",
            "confidence": 1.0,
        }
        edge = graph.build_edge(relation)

        assert edge["data"]["rel"] == "MENTIONS"
        assert edge["data"]["source"].startswith("doc:")


class TestGraphExporter:
    """Test the GraphExporter class."""

    def test_exporter_initialization(self, tmp_path: Path):
        """Test exporter initializes with database."""
        graph = _get_graph_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        exporter = graph.GraphExporter(conn)
        assert exporter.conn is not None

        conn.close()

    def test_export_empty_graph(self, tmp_path: Path):
        """Test exporting an empty graph."""
        graph = _get_graph_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        exporter = graph.GraphExporter(conn)
        result = exporter.export_all()

        assert "elements" in result
        assert "nodes" in result["elements"]
        assert "edges" in result["elements"]
        assert result["elements"]["nodes"] == []
        assert result["elements"]["edges"] == []

        conn.close()

    def test_export_with_entities(self, tmp_path: Path):
        """Test exporting entities as nodes."""
        graph = _get_graph_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Insert test entities
        insert_entity(conn, "org:openai", "OpenAI", "Org")
        insert_entity(conn, "model:gpt4", "GPT-4", "Model")

        exporter = graph.GraphExporter(conn)
        result = exporter.export_all()

        assert len(result["elements"]["nodes"]) == 2

        node_ids = {n["data"]["id"] for n in result["elements"]["nodes"]}
        assert "org:openai" in node_ids
        assert "model:gpt4" in node_ids

        conn.close()

    def test_export_with_relations(self, tmp_path: Path):
        """Test exporting relations as edges."""
        graph = _get_graph_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Insert entities and relation
        insert_entity(conn, "org:openai", "OpenAI", "Org")
        insert_entity(conn, "model:gpt4", "GPT-4", "Model")
        insert_relation(
            conn,
            source_id="org:openai",
            rel="CREATED",
            target_id="model:gpt4",
            kind="asserted",
            confidence=0.95,
            doc_id="test_doc",
            extractor_version="1.0.0",
        )

        exporter = graph.GraphExporter(conn)
        result = exporter.export_all()

        assert len(result["elements"]["edges"]) == 1
        edge = result["elements"]["edges"][0]
        assert edge["data"]["source"] == "org:openai"
        assert edge["data"]["target"] == "model:gpt4"
        assert edge["data"]["rel"] == "CREATED"

        conn.close()


class TestViewExports:
    """Test different graph views."""

    def _setup_test_data(self, conn):
        """Set up test data for view tests."""
        # Entities
        insert_entity(conn, "org:openai", "OpenAI", "Org", first_seen="2026-01-01")
        insert_entity(conn, "model:gpt4", "GPT-4", "Model", first_seen="2026-01-01")
        insert_entity(conn, "dataset:redpajama", "RedPajama", "Dataset", first_seen="2026-01-01")
        insert_entity(conn, "tech:transformer", "Transformer", "Tech", first_seen="2026-01-01")

        # Document record
        conn.execute(
            """
            INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("doc_123", "https://example.com", "Test", "Test Doc", "2026-01-15", "2026-01-15T10:00:00Z", "extracted"),
        )
        conn.commit()

        # MENTIONS relations (doc → entity)
        insert_relation(conn, "doc:doc_123", "MENTIONS", "org:openai", "asserted", 1.0, "doc_123", "1.0.0")
        insert_relation(conn, "doc:doc_123", "MENTIONS", "model:gpt4", "asserted", 1.0, "doc_123", "1.0.0")

        # Semantic relations (entity → entity)
        insert_relation(conn, "org:openai", "CREATED", "model:gpt4", "asserted", 0.95, "doc_123", "1.0.0")
        insert_relation(conn, "model:gpt4", "TRAINED_ON", "dataset:redpajama", "asserted", 0.9, "doc_123", "1.0.0")
        insert_relation(conn, "model:gpt4", "USES_TECH", "tech:transformer", "inferred", 0.8, "doc_123", "1.0.0")

    def test_mentions_view(self, tmp_path: Path):
        """Test mentions view (doc ↔ entity)."""
        graph = _get_graph_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        self._setup_test_data(conn)

        exporter = graph.GraphExporter(conn)
        result = exporter.export_mentions()

        # Should include document nodes and entity nodes
        node_types = {n["data"]["type"] for n in result["elements"]["nodes"]}
        assert "Document" in node_types

        # Should only include MENTIONS edges
        edge_rels = {e["data"]["rel"] for e in result["elements"]["edges"]}
        assert edge_rels == {"MENTIONS"}

        conn.close()

    def test_claims_view(self, tmp_path: Path):
        """Test claims view (semantic entity-to-entity)."""
        graph = _get_graph_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        self._setup_test_data(conn)

        exporter = graph.GraphExporter(conn)
        result = exporter.export_claims()

        # Should NOT include MENTIONS edges
        edge_rels = {e["data"]["rel"] for e in result["elements"]["edges"]}
        assert "MENTIONS" not in edge_rels

        # Should include semantic relations
        assert "CREATED" in edge_rels
        assert "TRAINED_ON" in edge_rels

        conn.close()

    def test_dependencies_view(self, tmp_path: Path):
        """Test dependencies view (USES_*, DEPENDS_ON, REQUIRES, etc.)."""
        graph = _get_graph_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        self._setup_test_data(conn)

        exporter = graph.GraphExporter(conn)
        result = exporter.export_dependencies()

        # Should only include dependency relations
        edge_rels = {e["data"]["rel"] for e in result["elements"]["edges"]}

        # TRAINED_ON and USES_TECH are dependencies
        assert "TRAINED_ON" in edge_rels or "USES_TECH" in edge_rels

        # CREATED is not a dependency
        assert "CREATED" not in edge_rels
        assert "MENTIONS" not in edge_rels

        conn.close()

    def test_filter_by_kind(self, tmp_path: Path):
        """Test filtering edges by kind."""
        graph = _get_graph_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        self._setup_test_data(conn)

        exporter = graph.GraphExporter(conn)

        # Only asserted
        result = exporter.export_claims(kinds=["asserted"])
        edge_kinds = {e["data"]["kind"] for e in result["elements"]["edges"]}
        assert edge_kinds == {"asserted"}

        # Only inferred
        result = exporter.export_claims(kinds=["inferred"])
        edge_kinds = {e["data"]["kind"] for e in result["elements"]["edges"]}
        assert "inferred" in edge_kinds
        assert "asserted" not in edge_kinds

        conn.close()


class TestFileExport:
    """Test file export functionality."""

    def test_export_to_file(self, tmp_path: Path):
        """Test exporting graph to JSON file."""
        graph = _get_graph_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:test", "Test Org", "Org")

        exporter = graph.GraphExporter(conn)
        output_dir = tmp_path / "graphs" / "2026-01-24"

        # Use "all" view which includes all entities regardless of relations
        exporter.export_to_file(output_dir, "all")

        output_path = output_dir / "all.json"
        assert output_path.exists()

        with open(output_path) as f:
            data = json.load(f)

        assert "elements" in data
        assert len(data["elements"]["nodes"]) == 1

        conn.close()

    def test_export_all_views(self, tmp_path: Path):
        """Test exporting all standard views."""
        graph = _get_graph_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:test", "Test Org", "Org")

        exporter = graph.GraphExporter(conn)
        output_dir = tmp_path / "graphs" / "2026-01-24"

        exporter.export_all_views(output_dir)

        # All standard views should exist
        assert (output_dir / "mentions.json").exists()
        assert (output_dir / "claims.json").exists()
        assert (output_dir / "dependencies.json").exists()

        conn.close()

    def test_export_creates_directories(self, tmp_path: Path):
        """Test that export creates output directories."""
        graph = _get_graph_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        exporter = graph.GraphExporter(conn)
        output_dir = tmp_path / "deep" / "nested" / "path"

        exporter.export_to_file(output_dir, "claims")

        assert output_dir.exists()
        assert (output_dir / "claims.json").is_file()

        conn.close()


class TestCytoscapeFormat:
    """Test Cytoscape.js format compliance."""

    def test_valid_cytoscape_structure(self, tmp_path: Path):
        """Test output matches Cytoscape.js expected structure."""
        graph = _get_graph_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org",
                      aliases=["Open AI"], first_seen="2026-01-01", last_seen="2026-01-20")
        insert_entity(conn, "model:gpt4", "GPT-4", "Model")
        insert_relation(conn, "org:openai", "CREATED", "model:gpt4",
                        "asserted", 0.95, "doc_123", "1.0.0")

        exporter = graph.GraphExporter(conn)
        result = exporter.export_all()

        # Top-level structure
        assert "elements" in result
        assert "nodes" in result["elements"]
        assert "edges" in result["elements"]

        # Node structure
        node = next(n for n in result["elements"]["nodes"]
                    if n["data"]["id"] == "org:openai")
        assert "data" in node
        assert "id" in node["data"]
        assert "label" in node["data"]
        assert "type" in node["data"]

        # Edge structure
        edge = result["elements"]["edges"][0]
        assert "data" in edge
        assert "id" in edge["data"]
        assert "source" in edge["data"]
        assert "target" in edge["data"]

        conn.close()

    def test_json_serializable(self, tmp_path: Path):
        """Test that output is JSON serializable."""
        graph = _get_graph_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:test", "Test", "Org")

        exporter = graph.GraphExporter(conn)
        result = exporter.export_all()

        # Should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

        # Round-trip
        parsed = json.loads(json_str)
        assert parsed == result

        conn.close()


class TestDateFiltering:
    """Test date-range filtering in graph exports.

    All dates are article publication dates, not fetch dates.
    """

    def _setup_dated_data(self, conn):
        """Insert entities and relations spanning different date ranges."""
        # Entities with different date windows
        insert_entity(conn, "org:old", "Old Org", "Org",
                      first_seen="2025-06-01", last_seen="2025-09-01")
        insert_entity(conn, "org:recent", "Recent Org", "Org",
                      first_seen="2026-01-01", last_seen="2026-02-10")
        insert_entity(conn, "model:new", "New Model", "Model",
                      first_seen="2026-01-20", last_seen="2026-02-10")

        # Documents with different published_at dates
        for doc_id, pub_date in [
            ("doc_old", "2025-07-01"),
            ("doc_recent", "2026-01-15"),
            ("doc_new", "2026-02-01"),
        ]:
            conn.execute(
                "INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (doc_id, f"https://example.com/{doc_id}", "Test", f"Doc {doc_id}",
                 pub_date, "2026-02-12T00:00:00Z", "extracted"),
            )
        conn.commit()

        # Relations tied to different documents
        insert_relation(conn, "org:old", "CREATED", "org:recent",
                        "asserted", 0.9, "doc_old", "1.0.0")
        insert_relation(conn, "org:recent", "CREATED", "model:new",
                        "asserted", 0.95, "doc_recent", "1.0.0")
        insert_relation(conn, "model:new", "USES_TECH", "org:recent",
                        "inferred", 0.7, "doc_new", "1.0.0")

    def test_export_all_no_date_filter(self, tmp_path: Path):
        """Without date filter, all entities are included."""
        graph = _get_graph_module()
        conn = init_db(tmp_path / "test.db")
        self._setup_dated_data(conn)

        exporter = graph.GraphExporter(conn)
        result = exporter.export_all()
        assert len(result["elements"]["nodes"]) == 3
        conn.close()

    def test_export_all_with_start_date(self, tmp_path: Path):
        """Start date excludes old entities."""
        graph = _get_graph_module()
        conn = init_db(tmp_path / "test.db")
        self._setup_dated_data(conn)

        exporter = graph.GraphExporter(conn)
        result = exporter.export_all(start_date="2026-01-01")

        node_ids = {n["data"]["id"] for n in result["elements"]["nodes"]}
        assert "org:old" not in node_ids  # last_seen 2025-09-01 < 2026-01-01
        assert "org:recent" in node_ids
        assert "model:new" in node_ids
        conn.close()

    def test_export_claims_with_date_range(self, tmp_path: Path):
        """Date range filters relations by document published_at."""
        graph = _get_graph_module()
        conn = init_db(tmp_path / "test.db")
        self._setup_dated_data(conn)

        exporter = graph.GraphExporter(conn)
        result = exporter.export_claims(
            start_date="2026-01-01", end_date="2026-01-31"
        )

        # Only doc_recent (2026-01-15) is in range
        edge_count = len(result["elements"]["edges"])
        assert edge_count == 1
        assert result["elements"]["edges"][0]["data"]["rel"] == "CREATED"
        conn.close()

    def test_export_to_file_includes_meta(self, tmp_path: Path):
        """export_to_file should include meta with dateRange."""
        graph = _get_graph_module()
        conn = init_db(tmp_path / "test.db")
        insert_entity(conn, "org:test", "Test", "Org",
                      first_seen="2026-01-01", last_seen="2026-02-01")

        exporter = graph.GraphExporter(conn)
        output_dir = tmp_path / "graphs" / "2026-02-12"
        path = exporter.export_to_file(
            output_dir, "claims",
            start_date="2026-01-01", end_date="2026-02-12",
        )

        with open(path) as f:
            data = json.load(f)

        assert "meta" in data
        assert data["meta"]["view"] == "claims"
        assert data["meta"]["dateRange"]["start"] == "2026-01-01"
        assert data["meta"]["dateRange"]["end"] == "2026-02-12"
        assert "exportedAt" in data["meta"]
        assert "nodeCount" in data["meta"]
        assert "edgeCount" in data["meta"]
        conn.close()

    def test_export_all_views_with_date_range(self, tmp_path: Path):
        """export_all_views passes date range to each view."""
        graph = _get_graph_module()
        conn = init_db(tmp_path / "test.db")
        self._setup_dated_data(conn)

        exporter = graph.GraphExporter(conn)
        output_dir = tmp_path / "graphs" / "2026-02-12"
        paths = exporter.export_all_views(
            output_dir,
            start_date="2026-01-01", end_date="2026-02-12",
        )

        # All views should have meta with dateRange
        for path in paths:
            with open(path) as f:
                data = json.load(f)
            assert data["meta"]["dateRange"]["start"] == "2026-01-01"
            assert data["meta"]["dateRange"]["end"] == "2026-02-12"
        conn.close()
