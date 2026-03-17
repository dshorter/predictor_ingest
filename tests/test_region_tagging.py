"""Tests for Sprint 7B: export-time region tagging.

Validates 2-hop propagation from Location nodes using the domain
profile's regions config. See ADR-005 for design rationale.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from db import init_db, insert_entity, insert_relation


def _get_graph_module():
    """Lazy import of graph module."""
    import graph
    return graph


# --- Region config fixtures ---

SOUTHEAST_REGIONS = {
    "southeast": [
        "Atlanta",
        "Savannah",
        "New Orleans",
        "Wilmington",
        "Nashville",
    ],
}


def _setup_film_graph(conn):
    """Build a small film-domain graph with Location nodes.

    Graph structure:
        location:atlanta (Location "Atlanta")
            ← SHOOTS_IN ← prod:movie_a (Production)
                ← DIRECTS ← person:director_x (Person)
                ← STARS_IN ← person:actor_y (Person)
            ← SHOOTS_IN ← prod:movie_b (Production)
                ← PRODUCES ← studio:a24 (Studio)

        location:la (Location "Los Angeles") — NOT in southeast
            ← SHOOTS_IN ← prod:movie_c (Production)
                ← DIRECTS ← person:director_z (Person)

        person:agent (Person) — unconnected to any Location
    """
    # Entities
    insert_entity(conn, "location:atlanta", "Atlanta", "Location",
                  first_seen="2026-01-01")
    insert_entity(conn, "location:la", "Los Angeles", "Location",
                  first_seen="2026-01-01")
    insert_entity(conn, "prod:movie_a", "Movie A", "Production",
                  first_seen="2026-01-01")
    insert_entity(conn, "prod:movie_b", "Movie B", "Production",
                  first_seen="2026-01-01")
    insert_entity(conn, "prod:movie_c", "Movie C", "Production",
                  first_seen="2026-01-01")
    insert_entity(conn, "person:director_x", "Director X", "Person",
                  first_seen="2026-01-01")
    insert_entity(conn, "person:actor_y", "Actor Y", "Person",
                  first_seen="2026-01-01")
    insert_entity(conn, "person:director_z", "Director Z", "Person",
                  first_seen="2026-01-01")
    insert_entity(conn, "studio:a24", "A24", "Studio",
                  first_seen="2026-01-01")
    insert_entity(conn, "person:agent", "Agent Q", "Person",
                  first_seen="2026-01-01")

    # Document (needed for relations)
    conn.execute(
        "INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("doc_1", "https://example.com/1", "Test", "Doc 1",
         "2026-01-15", "2026-01-15T00:00:00Z", "extracted"),
    )
    conn.commit()

    # Relations — Atlanta subgraph (2-hop reachable)
    insert_relation(conn, "prod:movie_a", "SHOOTS_IN", "location:atlanta",
                    "asserted", 0.9, "doc_1", "1.0.0")
    insert_relation(conn, "person:director_x", "DIRECTS", "prod:movie_a",
                    "asserted", 0.95, "doc_1", "1.0.0")
    insert_relation(conn, "person:actor_y", "STARS_IN", "prod:movie_a",
                    "asserted", 0.9, "doc_1", "1.0.0")
    insert_relation(conn, "prod:movie_b", "SHOOTS_IN", "location:atlanta",
                    "asserted", 0.85, "doc_1", "1.0.0")
    insert_relation(conn, "studio:a24", "PRODUCES", "prod:movie_b",
                    "asserted", 0.9, "doc_1", "1.0.0")

    # Relations — LA subgraph (no southeast region)
    insert_relation(conn, "prod:movie_c", "SHOOTS_IN", "location:la",
                    "asserted", 0.9, "doc_1", "1.0.0")
    insert_relation(conn, "person:director_z", "DIRECTS", "prod:movie_c",
                    "asserted", 0.95, "doc_1", "1.0.0")


class TestRegionPropagation:
    """Test 2-hop region tagging from Location nodes."""

    def _export_with_regions(self, conn, regions_config):
        """Export using a mocked profile with the given regions config."""
        graph = _get_graph_module()
        exporter = graph.GraphExporter(conn)

        # Patch the module-level _profile to include regions
        original_profile = graph._profile
        patched_profile = dict(original_profile)
        patched_profile["regions"] = regions_config

        with patch.object(graph, "_profile", patched_profile):
            result = exporter.export_all()
            # Apply region tags (normally done in export_to_file)
            graph.GraphExporter._apply_region_tags(
                result["elements"]["nodes"],
                result["elements"]["edges"],
            )
        return result

    def test_location_node_gets_region(self, tmp_path: Path):
        """The Location node itself should get region tag."""
        conn = init_db(tmp_path / "test.db")
        _setup_film_graph(conn)

        result = self._export_with_regions(conn, SOUTHEAST_REGIONS)
        nodes_by_id = {n["data"]["id"]: n for n in result["elements"]["nodes"]}

        assert nodes_by_id["location:atlanta"]["data"]["region"] == ["southeast"]
        conn.close()

    def test_hop1_production_gets_region(self, tmp_path: Path):
        """Productions connected to a regional Location get tagged (hop 1)."""
        conn = init_db(tmp_path / "test.db")
        _setup_film_graph(conn)

        result = self._export_with_regions(conn, SOUTHEAST_REGIONS)
        nodes_by_id = {n["data"]["id"]: n for n in result["elements"]["nodes"]}

        # movie_a SHOOTS_IN Atlanta — 1 hop
        assert nodes_by_id["prod:movie_a"]["data"]["region"] == ["southeast"]
        # movie_b SHOOTS_IN Atlanta — 1 hop
        assert nodes_by_id["prod:movie_b"]["data"]["region"] == ["southeast"]
        conn.close()

    def test_hop2_people_get_region(self, tmp_path: Path):
        """People connected to regional Productions get tagged (hop 2)."""
        conn = init_db(tmp_path / "test.db")
        _setup_film_graph(conn)

        result = self._export_with_regions(conn, SOUTHEAST_REGIONS)
        nodes_by_id = {n["data"]["id"]: n for n in result["elements"]["nodes"]}

        # director_x DIRECTS movie_a (which SHOOTS_IN Atlanta) — 2 hops
        assert nodes_by_id["person:director_x"]["data"]["region"] == ["southeast"]
        # actor_y STARS_IN movie_a — 2 hops
        assert nodes_by_id["person:actor_y"]["data"]["region"] == ["southeast"]
        # a24 PRODUCES movie_b — 2 hops
        assert nodes_by_id["studio:a24"]["data"]["region"] == ["southeast"]
        conn.close()

    def test_non_regional_location_not_tagged(self, tmp_path: Path):
        """LA is not in the regions config so should not be tagged."""
        conn = init_db(tmp_path / "test.db")
        _setup_film_graph(conn)

        result = self._export_with_regions(conn, SOUTHEAST_REGIONS)
        nodes_by_id = {n["data"]["id"]: n for n in result["elements"]["nodes"]}

        assert "region" not in nodes_by_id["location:la"]["data"]
        conn.close()

    def test_unconnected_node_not_tagged(self, tmp_path: Path):
        """Nodes with no path to a regional Location should not be tagged."""
        conn = init_db(tmp_path / "test.db")
        _setup_film_graph(conn)

        result = self._export_with_regions(conn, SOUTHEAST_REGIONS)
        nodes_by_id = {n["data"]["id"]: n for n in result["elements"]["nodes"]}

        assert "region" not in nodes_by_id["person:agent"]["data"]
        conn.close()

    def test_la_subgraph_not_tagged(self, tmp_path: Path):
        """Nodes only connected to LA (not in southeast) should not be tagged."""
        conn = init_db(tmp_path / "test.db")
        _setup_film_graph(conn)

        result = self._export_with_regions(conn, SOUTHEAST_REGIONS)
        nodes_by_id = {n["data"]["id"]: n for n in result["elements"]["nodes"]}

        assert "region" not in nodes_by_id["prod:movie_c"]["data"]
        assert "region" not in nodes_by_id["person:director_z"]["data"]
        conn.close()

    def test_no_regions_config_is_noop(self, tmp_path: Path):
        """When domain profile has no regions, no nodes get tagged."""
        conn = init_db(tmp_path / "test.db")
        _setup_film_graph(conn)

        result = self._export_with_regions(conn, None)

        for node in result["elements"]["nodes"]:
            assert "region" not in node["data"]
        conn.close()

    def test_empty_regions_config_is_noop(self, tmp_path: Path):
        """Empty regions dict should not tag anything."""
        conn = init_db(tmp_path / "test.db")
        _setup_film_graph(conn)

        result = self._export_with_regions(conn, {})

        for node in result["elements"]["nodes"]:
            assert "region" not in node["data"]
        conn.close()

    def test_multiple_regions(self, tmp_path: Path):
        """A node reachable from locations in different regions gets both tags."""
        conn = init_db(tmp_path / "test.db")
        _setup_film_graph(conn)

        # Add a second region that includes LA
        multi_regions = {
            "southeast": ["Atlanta"],
            "west_coast": ["Los Angeles"],
        }

        # Connect movie_a to LA too (it already connects to Atlanta)
        insert_relation(conn, "prod:movie_a", "SHOOTS_IN", "location:la",
                        "asserted", 0.9, "doc_1", "1.0.0")

        result = self._export_with_regions(conn, multi_regions)
        nodes_by_id = {n["data"]["id"]: n for n in result["elements"]["nodes"]}

        # movie_a should have both regions
        regions = nodes_by_id["prod:movie_a"]["data"]["region"]
        assert "southeast" in regions
        assert "west_coast" in regions
        conn.close()

    def test_region_tags_sorted(self, tmp_path: Path):
        """Region arrays should be sorted for deterministic output."""
        conn = init_db(tmp_path / "test.db")
        _setup_film_graph(conn)

        multi_regions = {
            "southeast": ["Atlanta"],
            "west_coast": ["Los Angeles"],
        }
        insert_relation(conn, "prod:movie_a", "SHOOTS_IN", "location:la",
                        "asserted", 0.9, "doc_1", "1.0.0")

        result = self._export_with_regions(conn, multi_regions)
        nodes_by_id = {n["data"]["id"]: n for n in result["elements"]["nodes"]}

        regions = nodes_by_id["prod:movie_a"]["data"]["region"]
        assert regions == sorted(regions)
        conn.close()

    def test_case_insensitive_matching(self, tmp_path: Path):
        """Region lookup should be case-insensitive."""
        conn = init_db(tmp_path / "test.db")

        # Insert entity with different casing than config
        insert_entity(conn, "location:atl", "ATLANTA", "Location",
                      first_seen="2026-01-01")
        insert_entity(conn, "prod:test", "Test Movie", "Production",
                      first_seen="2026-01-01")

        conn.execute(
            "INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("doc_ci", "https://example.com/ci", "Test", "CI Doc",
             "2026-01-15", "2026-01-15T00:00:00Z", "extracted"),
        )
        conn.commit()

        insert_relation(conn, "prod:test", "SHOOTS_IN", "location:atl",
                        "asserted", 0.9, "doc_ci", "1.0.0")

        # Config uses "atlanta" (mixed case) but entity label is "ATLANTA"
        regions = {"southeast": ["atlanta"]}

        result = self._export_with_regions(conn, regions)
        nodes_by_id = {n["data"]["id"]: n for n in result["elements"]["nodes"]}

        assert nodes_by_id["location:atl"]["data"]["region"] == ["southeast"]
        assert nodes_by_id["prod:test"]["data"]["region"] == ["southeast"]
        conn.close()


class TestRegionInFileExport:
    """Test that export_to_file applies region tags."""

    def test_export_to_file_includes_regions(self, tmp_path: Path):
        """Region tags should appear in exported JSON files."""
        graph = _get_graph_module()
        conn = init_db(tmp_path / "test.db")
        _setup_film_graph(conn)

        original_profile = graph._profile
        patched_profile = dict(original_profile)
        patched_profile["regions"] = SOUTHEAST_REGIONS

        exporter = graph.GraphExporter(conn)
        output_dir = tmp_path / "graphs" / "test"

        with patch.object(graph, "_profile", patched_profile):
            exporter.export_to_file(output_dir, "all")

        with open(output_dir / "all.json") as f:
            data = json.load(f)

        nodes_by_id = {n["data"]["id"]: n for n in data["elements"]["nodes"]}
        assert nodes_by_id["location:atlanta"]["data"]["region"] == ["southeast"]
        assert nodes_by_id["prod:movie_a"]["data"]["region"] == ["southeast"]
        assert "region" not in nodes_by_id["person:agent"]["data"]

        conn.close()
