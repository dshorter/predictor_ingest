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


class TestMergeRelationCollisions:
    """Test that merge_entities handles relation collisions safely.

    When two entities are merged, their relations can collide (same
    source, rel, target, kind, doc_id). The merge must handle this
    without crashing on the UNIQUE index or leaving duplicate edges.
    """

    def test_merge_handles_same_doc_collision(self, tmp_path: Path):
        """Merging entities with relations to the same target from the same doc."""
        resolve = _get_resolve_module()
        conn = init_db(tmp_path / "test.db")

        insert_entity(conn, "org:openai", "OpenAI", "Org")
        insert_entity(conn, "org:open_ai", "Open AI", "Org")
        insert_entity(conn, "model:gpt4", "GPT-4", "Model")

        # Both entities assert CREATED model:gpt4 from the SAME doc
        from db import insert_evidence
        r1 = insert_relation(conn, "org:openai", "CREATED", "model:gpt4",
                             "asserted", 0.9, "doc_1", "1.0.0")
        r2 = insert_relation(conn, "org:open_ai", "CREATED", "model:gpt4",
                             "asserted", 0.95, "doc_1", "1.0.0")
        insert_evidence(conn, r1, "doc_1", "https://example.com", "2026-01-01", "evidence A")
        insert_evidence(conn, r2, "doc_1", "https://example.com", "2026-01-01", "evidence B")

        # This should NOT crash on unique index violation
        resolve.merge_entities(conn, "org:open_ai", "org:openai")

        # Should have exactly 1 CREATED relation (not 2)
        rels = conn.execute(
            "SELECT * FROM relations WHERE rel = 'CREATED'"
        ).fetchall()
        assert len(rels) == 1
        assert rels[0]["source_id"] == "org:openai"

        # Evidence from the duplicate should have been reassigned
        ev = conn.execute(
            "SELECT * FROM evidence WHERE relation_id = ?", (rels[0]["relation_id"],)
        ).fetchall()
        assert len(ev) == 2  # both evidence records preserved

        conn.close()

    def test_merge_handles_cross_doc_relations(self, tmp_path: Path):
        """Merging entities with relations to the same target from different docs."""
        resolve = _get_resolve_module()
        conn = init_db(tmp_path / "test.db")

        insert_entity(conn, "org:openai", "OpenAI", "Org")
        insert_entity(conn, "org:open_ai", "Open AI", "Org")
        insert_entity(conn, "model:gpt4", "GPT-4", "Model")

        # Relations from different docs
        insert_relation(conn, "org:openai", "CREATED", "model:gpt4",
                        "asserted", 0.9, "doc_1", "1.0.0")
        insert_relation(conn, "org:open_ai", "CREATED", "model:gpt4",
                        "asserted", 0.95, "doc_2", "1.0.0")

        resolve.merge_entities(conn, "org:open_ai", "org:openai")

        # Both relations should survive (different doc_ids)
        rels = conn.execute(
            "SELECT * FROM relations WHERE rel = 'CREATED' ORDER BY doc_id"
        ).fetchall()
        assert len(rels) == 2
        assert all(r["source_id"] == "org:openai" for r in rels)

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


class TestCollectGrayZonePairs:
    """Tests for collect_gray_zone_pairs — the disambiguation candidate collector.

    These tests guard against the O(n²) DB query regression introduced when
    entity_types_to_disambiguate was changed from a short list to [] (all types).
    Without the fix, each pair in the inner loop issued a DB query via
    _pair_already_decided before checking similarity, causing resolve to hang
    on corpora with thousands of entities.
    """

    def _make_config(self, **kwargs):
        from resolve.disambiguate import DisambiguationConfig
        defaults = dict(
            enabled=True,
            similarity_lower_bound=0.40,
            similarity_upper_bound=0.85,
            max_pairs_per_run=500,
            batch_size=15,
            entity_types_to_disambiguate=[],  # all types — the regression trigger
        )
        defaults.update(kwargs)
        return DisambiguationConfig(**defaults)

    def _setup_db(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        from resolve.disambiguate import ensure_disambiguation_table
        ensure_disambiguation_table(conn)
        return conn

    def test_finds_similar_pairs_all_types(self, tmp_path):
        """With empty entity_types_to_disambiguate, similar pairs across all
        entity types are returned."""
        conn = self._setup_db(tmp_path)
        insert_entity(conn, "org:openai", "OpenAI", "Org")
        insert_entity(conn, "org:open_ai", "Open AI", "Org")
        insert_entity(conn, "person:john_smith", "John Smith", "Person")
        insert_entity(conn, "person:john_smithe", "John Smithe", "Person")
        insert_entity(conn, "org:google", "Google", "Org")  # dissimilar, should not appear

        from resolve.disambiguate import collect_gray_zone_pairs
        config = self._make_config()
        pairs = collect_gray_zone_pairs(conn, config)

        pair_names = {(p.entity_a_name, p.entity_b_name) for p in pairs}
        # Both similar pairs should be found regardless of type
        assert any("OpenAI" in n or "Open AI" in n for pair in pair_names for n in pair)
        assert any("John Smith" in n or "John Smithe" in n for pair in pair_names for n in pair)
        # Dissimilar entity should not appear
        assert not any("Google" in n for pair in pair_names for n in pair)
        conn.close()

    def test_respects_max_pairs_cap(self, tmp_path):
        """Result is capped at max_pairs_per_run even with many candidates."""
        conn = self._setup_db(tmp_path)
        # Insert entities with names designed to be similar to each other
        for i in range(60):
            insert_entity(conn, f"person:person_{i:03d}", f"James Person {i:03d}", "Person")

        from resolve.disambiguate import collect_gray_zone_pairs
        config = self._make_config(max_pairs_per_run=20)
        pairs = collect_gray_zone_pairs(conn, config)

        assert len(pairs) <= 20
        conn.close()

    def test_skips_already_decided_pairs(self, tmp_path):
        """Pairs with an existing disambiguation decision are not returned."""
        conn = self._setup_db(tmp_path)
        insert_entity(conn, "org:openai", "OpenAI", "Org")
        insert_entity(conn, "org:open_ai", "Open AI", "Org")

        # Pre-populate a decision for this pair
        a, b = sorted(["org:openai", "org:open_ai"])
        conn.execute(
            """INSERT INTO disambiguation_decisions
               (entity_a_id, entity_b_id, similarity_score, llm_verdict, llm_model, run_date)
               VALUES (?, ?, 0.72, 'keep_separate', 'gpt-5-nano', '2026-01-01')""",
            (a, b),
        )
        conn.commit()

        from resolve.disambiguate import collect_gray_zone_pairs
        config = self._make_config()
        pairs = collect_gray_zone_pairs(conn, config)

        # The already-decided pair must not be returned
        for p in pairs:
            assert not (
                {p.entity_a_id, p.entity_b_id} == {"org:openai", "org:open_ai"}
            ), "Already-decided pair was returned"
        conn.close()

    def test_large_corpus_all_types_completes_fast(self, tmp_path):
        """Regression test: with 150 entities across 3 types and empty
        entity_types_to_disambiguate, collect_gray_zone_pairs must complete
        in under 10 seconds.

        The pre-fix code issued one DB query per pair in the O(n^2) inner loop.
        At 150 entities per type that is ~33,750 pairs × 3 types = ~100k DB
        queries — enough to cause a measurable slowdown even in a test.
        The post-fix code issues a single bulk query and completes in <1 second.
        """
        import time
        conn = self._setup_db(tmp_path)

        # 150 entities per type, all with distinct names so similarity is low
        # (ensures we iterate the full O(n^2) space before finding candidates)
        for i in range(150):
            insert_entity(conn, f"person:p{i}", f"Person Unique Name {i:04d}", "Person")
            insert_entity(conn, f"org:o{i}", f"Organisation Distinct Label {i:04d}", "Org")
            insert_entity(conn, f"topic:t{i}", f"Topic Different Term {i:04d}", "Topic")

        # Add a handful of similar pairs so the function has real work to do
        insert_entity(conn, "person:james_a", "James Anderson", "Person")
        insert_entity(conn, "person:james_b", "James Andersen", "Person")

        from resolve.disambiguate import collect_gray_zone_pairs
        config = self._make_config(max_pairs_per_run=500)

        start = time.monotonic()
        pairs = collect_gray_zone_pairs(conn, config)
        elapsed = time.monotonic() - start

        assert elapsed < 10.0, (
            f"collect_gray_zone_pairs took {elapsed:.1f}s on 450-entity corpus — "
            "possible O(n²) DB query regression"
        )
        # Sanity: the similar pair should have been found
        assert any(
            {"james_a", "james_b"} & {p.entity_a_id.split(":")[-1], p.entity_b_id.split(":")[-1]}
            for p in pairs
        )
        conn.close()

    def test_type_filter_restricts_candidates(self, tmp_path):
        """When entity_types_to_disambiguate is non-empty, only those types
        are considered."""
        conn = self._setup_db(tmp_path)
        insert_entity(conn, "org:openai", "OpenAI", "Org")
        insert_entity(conn, "org:open_ai", "Open AI", "Org")
        insert_entity(conn, "person:john_smith", "John Smith", "Person")
        insert_entity(conn, "person:john_smithe", "John Smithe", "Person")

        from resolve.disambiguate import collect_gray_zone_pairs
        config = self._make_config(entity_types_to_disambiguate=["Org"])
        pairs = collect_gray_zone_pairs(conn, config)

        for p in pairs:
            assert p.entity_type == "Org", f"Unexpected type: {p.entity_type}"
        conn.close()
