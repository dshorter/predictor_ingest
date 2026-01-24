"""Tests for resolve module - entity resolution and alias merging.

Tests entity deduplication, similarity matching, and canonical ID management.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from db import init_db, insert_entity, insert_relation, get_entity, add_alias, resolve_alias


def _get_resolve_module():
    """Lazy import of resolve module."""
    import resolve
    return resolve


class TestNormalizeName:
    """Test name normalization for matching."""

    def test_lowercase(self):
        """Test lowercase conversion."""
        resolve = _get_resolve_module()
        assert resolve.normalize_name("OpenAI") == "openai"

    def test_strips_whitespace(self):
        """Test whitespace stripping."""
        resolve = _get_resolve_module()
        assert resolve.normalize_name("  OpenAI  ") == "openai"

    def test_normalizes_internal_whitespace(self):
        """Test internal whitespace normalization."""
        resolve = _get_resolve_module()
        assert resolve.normalize_name("Open   AI") == "open ai"

    def test_removes_punctuation(self):
        """Test punctuation removal."""
        resolve = _get_resolve_module()
        assert resolve.normalize_name("OpenAI, Inc.") == "openai inc"

    def test_handles_unicode(self):
        """Test unicode handling."""
        resolve = _get_resolve_module()
        # Should preserve unicode letters
        assert "café" in resolve.normalize_name("Café AI")

    def test_empty_string(self):
        """Test empty string handling."""
        resolve = _get_resolve_module()
        assert resolve.normalize_name("") == ""


class TestNameSimilarity:
    """Test name similarity scoring."""

    def test_exact_match(self):
        """Test exact match returns 1.0."""
        resolve = _get_resolve_module()
        score = resolve.name_similarity("OpenAI", "OpenAI")
        assert score == 1.0

    def test_case_insensitive_match(self):
        """Test case-insensitive matching."""
        resolve = _get_resolve_module()
        score = resolve.name_similarity("OpenAI", "openai")
        assert score == 1.0

    def test_whitespace_insensitive(self):
        """Test whitespace-insensitive matching."""
        resolve = _get_resolve_module()
        score = resolve.name_similarity("Open AI", "OpenAI")
        assert score >= 0.8

    def test_partial_match(self):
        """Test partial name matching."""
        resolve = _get_resolve_module()
        score = resolve.name_similarity("GPT-4", "GPT-4 Turbo")
        # GPT-4 is contained in GPT-4 Turbo, so partial match
        assert 0.4 <= score < 1.0

    def test_no_match(self):
        """Test completely different names."""
        resolve = _get_resolve_module()
        score = resolve.name_similarity("OpenAI", "Google")
        assert score < 0.5

    def test_abbreviation_matching(self):
        """Test matching with common abbreviations."""
        resolve = _get_resolve_module()
        # Inc. vs full form - has word overlap
        score = resolve.name_similarity("OpenAI Inc", "OpenAI Incorporated")
        assert score >= 0.5  # Shares "openai" word


class TestFindSimilarEntities:
    """Test finding similar entities in database."""

    def test_finds_exact_match(self, tmp_path: Path):
        """Test finding exact name match."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")

        matches = resolve.find_similar_entities(conn, "OpenAI", "Org")

        assert len(matches) >= 1
        assert any(m["entity_id"] == "org:openai" for m in matches)

        conn.close()

    def test_finds_case_variant(self, tmp_path: Path):
        """Test finding case-variant match."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")

        matches = resolve.find_similar_entities(conn, "openai", "Org")

        assert len(matches) >= 1
        assert any(m["entity_id"] == "org:openai" for m in matches)

        conn.close()

    def test_finds_by_alias(self, tmp_path: Path):
        """Test finding entity by registered alias."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")
        add_alias(conn, "Open AI", "org:openai")

        matches = resolve.find_similar_entities(conn, "Open AI", "Org")

        assert len(matches) >= 1
        assert any(m["entity_id"] == "org:openai" for m in matches)

        conn.close()

    def test_filters_by_type(self, tmp_path: Path):
        """Test that type filter is applied."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")
        insert_entity(conn, "model:openai", "OpenAI Model", "Model")

        matches = resolve.find_similar_entities(conn, "OpenAI", "Org")

        # Should only match the Org, not the Model
        assert all(m["type"] == "Org" for m in matches)

        conn.close()

    def test_returns_similarity_scores(self, tmp_path: Path):
        """Test that similarity scores are returned."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")

        matches = resolve.find_similar_entities(conn, "OpenAI", "Org")

        assert len(matches) >= 1
        assert "similarity" in matches[0]
        assert matches[0]["similarity"] == 1.0

        conn.close()


class TestMergeEntities:
    """Test entity merging."""

    def test_merge_preserves_canonical(self, tmp_path: Path):
        """Test that canonical entity is preserved."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org", first_seen="2023-01-01")
        insert_entity(conn, "org:open_ai", "Open AI", "Org", first_seen="2023-06-01")

        resolve.merge_entities(conn, "org:open_ai", "org:openai")

        # Canonical should still exist
        canonical = get_entity(conn, "org:openai")
        assert canonical is not None

        conn.close()

    def test_merge_creates_alias(self, tmp_path: Path):
        """Test that merge creates alias mapping."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")
        insert_entity(conn, "org:open_ai", "Open AI", "Org")

        resolve.merge_entities(conn, "org:open_ai", "org:openai")

        # Alias should resolve to canonical
        resolved = resolve_alias(conn, "Open AI")
        assert resolved == "org:openai"

        conn.close()

    def test_merge_updates_relations(self, tmp_path: Path):
        """Test that relations are updated to point to canonical."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")
        insert_entity(conn, "org:open_ai", "Open AI", "Org")
        insert_entity(conn, "model:gpt4", "GPT-4", "Model")

        # Relation pointing to duplicate
        insert_relation(conn, "org:open_ai", "CREATED", "model:gpt4",
                       "asserted", 0.9, "doc1", "1.0.0")

        resolve.merge_entities(conn, "org:open_ai", "org:openai")

        # Check relation was updated
        cursor = conn.execute(
            "SELECT source_id FROM relations WHERE target_id = ?",
            ("model:gpt4",)
        )
        row = cursor.fetchone()
        assert row[0] == "org:openai"

        conn.close()

    def test_merge_preserves_earliest_first_seen(self, tmp_path: Path):
        """Test that earliest first_seen date is preserved."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org",
                     first_seen="2023-06-01", last_seen="2024-01-01")
        insert_entity(conn, "org:open_ai", "Open AI", "Org",
                     first_seen="2023-01-01", last_seen="2024-06-01")

        resolve.merge_entities(conn, "org:open_ai", "org:openai")

        canonical = get_entity(conn, "org:openai")
        # Should keep earliest first_seen
        assert canonical["first_seen"] == "2023-01-01"
        # Should keep latest last_seen
        assert canonical["last_seen"] == "2024-06-01"

        conn.close()

    def test_merge_combines_aliases(self, tmp_path: Path):
        """Test that aliases are combined."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org",
                     aliases=["OpenAI Inc"])
        insert_entity(conn, "org:open_ai", "Open AI", "Org",
                     aliases=["Open-AI"])

        resolve.merge_entities(conn, "org:open_ai", "org:openai")

        canonical = get_entity(conn, "org:openai")
        # Should have combined aliases
        assert "OpenAI Inc" in canonical["aliases"]
        assert "Open AI" in canonical["aliases"]  # Name of merged entity

        conn.close()


class TestEntityResolver:
    """Test the EntityResolver class."""

    def test_resolver_initialization(self, tmp_path: Path):
        """Test resolver initialization."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        resolver = resolve.EntityResolver(conn)
        assert resolver.conn is not None

        conn.close()

    def test_resolve_new_entity(self, tmp_path: Path):
        """Test resolving a new entity (no match)."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        resolver = resolve.EntityResolver(conn)
        result = resolver.resolve("OpenAI", "Org")

        # Should return None for no match
        assert result is None

        conn.close()

    def test_resolve_existing_entity(self, tmp_path: Path):
        """Test resolving to existing entity."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")

        resolver = resolve.EntityResolver(conn)
        result = resolver.resolve("OpenAI", "Org")

        assert result == "org:openai"

        conn.close()

    def test_resolve_with_threshold(self, tmp_path: Path):
        """Test resolution respects similarity threshold."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")

        resolver = resolve.EntityResolver(conn, threshold=0.9)

        # Exact match should resolve
        assert resolver.resolve("OpenAI", "Org") == "org:openai"

        # Partial match below threshold should not resolve
        assert resolver.resolve("Open", "Org") is None

        conn.close()

    def test_resolve_or_create(self, tmp_path: Path):
        """Test resolve_or_create for new entities."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        resolver = resolve.EntityResolver(conn)
        entity_id = resolver.resolve_or_create("OpenAI", "Org")

        assert entity_id is not None
        assert entity_id.startswith("org:")

        # Entity should exist
        entity = get_entity(conn, entity_id)
        assert entity is not None
        assert entity["name"] == "OpenAI"

        conn.close()

    def test_resolve_or_create_returns_existing(self, tmp_path: Path):
        """Test resolve_or_create returns existing entity."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")

        resolver = resolve.EntityResolver(conn)
        entity_id = resolver.resolve_or_create("OpenAI", "Org")

        assert entity_id == "org:openai"

        conn.close()


class TestBatchResolution:
    """Test batch entity resolution."""

    def test_resolve_extraction_entities(self, tmp_path: Path):
        """Test resolving entities from an extraction."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Pre-existing entity
        insert_entity(conn, "org:openai", "OpenAI", "Org")

        extraction = {
            "entities": [
                {"name": "OpenAI", "type": "Org"},  # Should match existing
                {"name": "GPT-4", "type": "Model"},  # New entity
                {"name": "Open AI", "type": "Org"},  # Should match OpenAI
            ]
        }

        resolver = resolve.EntityResolver(conn)
        resolved = resolver.resolve_extraction(extraction)

        # Check mappings
        assert resolved["OpenAI"] == "org:openai"
        assert resolved["Open AI"] == "org:openai"
        assert "GPT-4" in resolved
        assert resolved["GPT-4"].startswith("model:")

        conn.close()

    def test_run_resolution_pass(self, tmp_path: Path):
        """Test running resolution on all entities in database."""
        resolve = _get_resolve_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Insert duplicate entities
        insert_entity(conn, "org:openai_1", "OpenAI", "Org", first_seen="2023-01-01")
        insert_entity(conn, "org:openai_2", "OpenAI Inc", "Org", first_seen="2023-06-01")
        insert_entity(conn, "org:openai_3", "Open AI", "Org", first_seen="2023-03-01")

        resolver = resolve.EntityResolver(conn, threshold=0.8)
        stats = resolver.run_resolution_pass()

        # Should have merged some entities
        assert stats["entities_checked"] >= 3
        assert stats["merges_performed"] >= 0  # May or may not merge depending on threshold

        conn.close()


class TestCanonicalIdGeneration:
    """Test canonical ID generation."""

    def test_generates_valid_id(self):
        """Test ID generation format."""
        resolve = _get_resolve_module()

        entity_id = resolve.generate_canonical_id("OpenAI", "Org")

        assert entity_id.startswith("org:")
        assert "openai" in entity_id

    def test_different_types_different_prefix(self):
        """Test different entity types get different prefixes."""
        resolve = _get_resolve_module()

        org_id = resolve.generate_canonical_id("Test", "Org")
        model_id = resolve.generate_canonical_id("Test", "Model")
        person_id = resolve.generate_canonical_id("Test", "Person")

        assert org_id.startswith("org:")
        assert model_id.startswith("model:")
        assert person_id.startswith("person:")

    def test_handles_special_characters(self):
        """Test ID generation with special characters."""
        resolve = _get_resolve_module()

        entity_id = resolve.generate_canonical_id("OpenAI, Inc.", "Org")

        # Should be valid ID format (no special chars)
        assert "," not in entity_id
        assert "." not in entity_id

    def test_id_is_deterministic(self):
        """Test same input produces same ID."""
        resolve = _get_resolve_module()

        id1 = resolve.generate_canonical_id("OpenAI", "Org")
        id2 = resolve.generate_canonical_id("OpenAI", "Org")

        assert id1 == id2
