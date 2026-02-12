"""Tests for database schema and operations for entities/relations.

Tests written BEFORE implementation (TDD).
Based on AGENTS.md specification.
"""

import sqlite3
import pytest
from pathlib import Path

from db import (
    init_db,
    insert_entity,
    insert_relation,
    insert_evidence,
    get_entity,
    get_entity_by_name,
    get_relations_for_entity,
    add_alias,
    resolve_alias,
    list_entities,
    list_entities_in_date_range,
    list_relations_in_date_range,
)


@pytest.fixture
def db_conn(tmp_path):
    """Create a temporary database with schema initialized."""
    db_path = tmp_path / "test.sqlite"
    conn = init_db(db_path)
    yield conn
    conn.close()


class TestInitDb:
    """Test database initialization."""

    def test_creates_database_file(self, tmp_path):
        """Should create database file at specified path."""
        db_path = tmp_path / "test.sqlite"
        conn = init_db(db_path)
        conn.close()
        assert db_path.exists()

    def test_creates_entities_table(self, db_conn):
        """Should create entities table with correct columns."""
        cursor = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entities'"
        )
        assert cursor.fetchone() is not None

    def test_creates_relations_table(self, db_conn):
        """Should create relations table with correct columns."""
        cursor = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='relations'"
        )
        assert cursor.fetchone() is not None

    def test_creates_evidence_table(self, db_conn):
        """Should create evidence table with correct columns."""
        cursor = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence'"
        )
        assert cursor.fetchone() is not None

    def test_creates_entity_aliases_table(self, db_conn):
        """Should create entity_aliases table for resolution."""
        cursor = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entity_aliases'"
        )
        assert cursor.fetchone() is not None

    def test_preserves_existing_documents_table(self, db_conn):
        """Should not drop existing documents table."""
        cursor = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"
        )
        assert cursor.fetchone() is not None


class TestInsertEntity:
    """Test entity insertion."""

    def test_insert_minimal_entity(self, db_conn):
        """Should insert entity with required fields."""
        entity_id = insert_entity(
            db_conn,
            entity_id="org:openai",
            name="OpenAI",
            entity_type="Org",
        )
        assert entity_id == "org:openai"

    def test_insert_full_entity(self, db_conn):
        """Should insert entity with all fields."""
        entity_id = insert_entity(
            db_conn,
            entity_id="model:gpt4",
            name="GPT-4",
            entity_type="Model",
            aliases=["GPT4", "gpt-4"],
            external_ids={"wikidata": "Q123"},
            first_seen="2025-12-01",
            last_seen="2025-12-15",
        )
        assert entity_id == "model:gpt4"

    def test_upsert_updates_last_seen(self, db_conn):
        """Should update last_seen on re-insert."""
        insert_entity(
            db_conn,
            entity_id="org:openai",
            name="OpenAI",
            entity_type="Org",
            first_seen="2025-01-01",
            last_seen="2025-01-01",
        )
        insert_entity(
            db_conn,
            entity_id="org:openai",
            name="OpenAI",
            entity_type="Org",
            last_seen="2025-12-01",
        )
        entity = get_entity(db_conn, "org:openai")
        assert entity["last_seen"] == "2025-12-01"
        # first_seen should not change
        assert entity["first_seen"] == "2025-01-01"


class TestGetEntity:
    """Test entity retrieval."""

    def test_get_existing_entity(self, db_conn):
        """Should return entity dict for existing entity."""
        insert_entity(
            db_conn,
            entity_id="org:openai",
            name="OpenAI",
            entity_type="Org",
        )
        entity = get_entity(db_conn, "org:openai")
        assert entity is not None
        assert entity["entity_id"] == "org:openai"
        assert entity["name"] == "OpenAI"
        assert entity["type"] == "Org"

    def test_get_nonexistent_entity(self, db_conn):
        """Should return None for nonexistent entity."""
        entity = get_entity(db_conn, "org:nonexistent")
        assert entity is None

    def test_get_entity_by_name(self, db_conn):
        """Should find entity by name."""
        insert_entity(
            db_conn,
            entity_id="org:openai",
            name="OpenAI",
            entity_type="Org",
        )
        entities = get_entity_by_name(db_conn, "OpenAI")
        assert len(entities) == 1
        assert entities[0]["entity_id"] == "org:openai"


class TestInsertRelation:
    """Test relation insertion."""

    def test_insert_relation(self, db_conn):
        """Should insert relation with required fields."""
        # First insert entities
        insert_entity(db_conn, "org:openai", "OpenAI", "Org")
        insert_entity(db_conn, "model:gpt4", "GPT-4", "Model")

        relation_id = insert_relation(
            db_conn,
            source_id="org:openai",
            rel="CREATED",
            target_id="model:gpt4",
            kind="asserted",
            confidence=0.95,
            doc_id="doc123",
            extractor_version="1.0.0",
        )
        assert relation_id is not None

    def test_insert_relation_with_optional_fields(self, db_conn):
        """Should insert relation with optional fields."""
        insert_entity(db_conn, "org:openai", "OpenAI", "Org")
        insert_entity(db_conn, "model:gpt4", "GPT-4", "Model")

        relation_id = insert_relation(
            db_conn,
            source_id="org:openai",
            rel="CREATED",
            target_id="model:gpt4",
            kind="asserted",
            confidence=0.95,
            doc_id="doc123",
            extractor_version="1.0.0",
            verb_raw="created",
            polarity="pos",
            modality="observed",
        )
        assert relation_id is not None


class TestInsertEvidence:
    """Test evidence insertion."""

    def test_insert_evidence(self, db_conn):
        """Should insert evidence linked to relation."""
        insert_entity(db_conn, "org:openai", "OpenAI", "Org")
        insert_entity(db_conn, "model:gpt4", "GPT-4", "Model")
        relation_id = insert_relation(
            db_conn,
            source_id="org:openai",
            rel="CREATED",
            target_id="model:gpt4",
            kind="asserted",
            confidence=0.95,
            doc_id="doc123",
            extractor_version="1.0.0",
        )

        evidence_id = insert_evidence(
            db_conn,
            relation_id=relation_id,
            doc_id="doc123",
            url="https://example.com/article",
            published="2025-12-01",
            snippet="OpenAI announced GPT-4...",
        )
        assert evidence_id is not None

    def test_insert_evidence_with_char_span(self, db_conn):
        """Should insert evidence with character span."""
        insert_entity(db_conn, "org:openai", "OpenAI", "Org")
        insert_entity(db_conn, "model:gpt4", "GPT-4", "Model")
        relation_id = insert_relation(
            db_conn,
            source_id="org:openai",
            rel="CREATED",
            target_id="model:gpt4",
            kind="asserted",
            confidence=0.95,
            doc_id="doc123",
            extractor_version="1.0.0",
        )

        evidence_id = insert_evidence(
            db_conn,
            relation_id=relation_id,
            doc_id="doc123",
            url="https://example.com/article",
            published="2025-12-01",
            snippet="OpenAI announced GPT-4...",
            char_start=100,
            char_end=150,
        )
        assert evidence_id is not None


class TestGetRelations:
    """Test relation retrieval."""

    def test_get_relations_for_entity(self, db_conn):
        """Should get all relations involving an entity."""
        insert_entity(db_conn, "org:openai", "OpenAI", "Org")
        insert_entity(db_conn, "model:gpt4", "GPT-4", "Model")
        insert_entity(db_conn, "model:gpt3", "GPT-3", "Model")

        insert_relation(
            db_conn, "org:openai", "CREATED", "model:gpt4",
            "asserted", 0.95, "doc1", "1.0.0"
        )
        insert_relation(
            db_conn, "org:openai", "CREATED", "model:gpt3",
            "asserted", 0.95, "doc2", "1.0.0"
        )

        relations = get_relations_for_entity(db_conn, "org:openai")
        assert len(relations) == 2


class TestEntityAliases:
    """Test entity alias resolution."""

    def test_add_alias(self, db_conn):
        """Should add alias mapping."""
        insert_entity(db_conn, "org:openai", "OpenAI", "Org")
        add_alias(db_conn, "Open AI", "org:openai")
        add_alias(db_conn, "openai.com", "org:openai")

    def test_resolve_alias(self, db_conn):
        """Should resolve alias to canonical ID."""
        insert_entity(db_conn, "org:openai", "OpenAI", "Org")
        add_alias(db_conn, "Open AI", "org:openai")

        canonical = resolve_alias(db_conn, "Open AI")
        assert canonical == "org:openai"

    def test_resolve_unknown_alias(self, db_conn):
        """Should return None for unknown alias."""
        canonical = resolve_alias(db_conn, "Unknown Entity")
        assert canonical is None

    def test_resolve_canonical_id_directly(self, db_conn):
        """Should return canonical ID if passed directly."""
        insert_entity(db_conn, "org:openai", "OpenAI", "Org")
        # Even without alias, looking up the entity name should work
        add_alias(db_conn, "OpenAI", "org:openai")
        canonical = resolve_alias(db_conn, "OpenAI")
        assert canonical == "org:openai"


class TestListEntities:
    """Test entity listing."""

    def test_list_all_entities(self, db_conn):
        """Should list all entities."""
        insert_entity(db_conn, "org:openai", "OpenAI", "Org")
        insert_entity(db_conn, "org:anthropic", "Anthropic", "Org")
        insert_entity(db_conn, "model:gpt4", "GPT-4", "Model")

        entities = list_entities(db_conn)
        assert len(entities) == 3

    def test_list_entities_by_type(self, db_conn):
        """Should filter entities by type."""
        insert_entity(db_conn, "org:openai", "OpenAI", "Org")
        insert_entity(db_conn, "org:anthropic", "Anthropic", "Org")
        insert_entity(db_conn, "model:gpt4", "GPT-4", "Model")

        orgs = list_entities(db_conn, entity_type="Org")
        assert len(orgs) == 2

        models = list_entities(db_conn, entity_type="Model")
        assert len(models) == 1


class TestDateRangeQueries:
    """Test date range filtering for entities and relations.

    All dates here are article publication dates, not fetch dates.
    """

    def _insert_dated_entities(self, db_conn):
        """Insert entities with various first_seen/last_seen dates."""
        insert_entity(db_conn, "org:old", "Old Org", "Org",
                      first_seen="2025-06-01", last_seen="2025-09-01")
        insert_entity(db_conn, "org:mid", "Mid Org", "Org",
                      first_seen="2025-10-01", last_seen="2026-01-15")
        insert_entity(db_conn, "org:new", "New Org", "Org",
                      first_seen="2026-01-20", last_seen="2026-02-10")
        insert_entity(db_conn, "org:nodates", "No Dates Org", "Org")

    def _insert_dated_relations(self, db_conn):
        """Insert documents and relations with different published_at dates."""
        self._insert_dated_entities(db_conn)

        # Documents with different publication dates
        for doc_id, pub_date in [
            ("doc_old", "2025-07-01"),
            ("doc_mid", "2025-12-01"),
            ("doc_new", "2026-02-01"),
        ]:
            db_conn.execute(
                "INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (doc_id, f"https://example.com/{doc_id}", "Test", f"Doc {doc_id}",
                 pub_date, "2026-02-12T00:00:00Z", "extracted"),
            )
        db_conn.commit()

        insert_relation(db_conn, "org:old", "CREATED", "org:mid",
                        "asserted", 0.9, "doc_old", "1.0.0")
        insert_relation(db_conn, "org:mid", "PARTNERED_WITH", "org:new",
                        "asserted", 0.8, "doc_mid", "1.0.0")
        insert_relation(db_conn, "org:new", "LAUNCHED", "org:mid",
                        "asserted", 0.95, "doc_new", "1.0.0")

    def test_entities_no_filter(self, db_conn):
        """No date filter returns all entities."""
        self._insert_dated_entities(db_conn)
        result = list_entities_in_date_range(db_conn)
        assert len(result) == 4

    def test_entities_start_date_only(self, db_conn):
        """Start date filters out entities whose last_seen is before it."""
        self._insert_dated_entities(db_conn)
        result = list_entities_in_date_range(db_conn, start_date="2026-01-01")
        ids = {e["entity_id"] for e in result}
        assert "org:old" not in ids  # last_seen 2025-09-01 < 2026-01-01
        assert "org:mid" in ids
        assert "org:new" in ids
        assert "org:nodates" in ids  # NULL last_seen is included

    def test_entities_end_date_only(self, db_conn):
        """End date filters out entities whose first_seen is after it."""
        self._insert_dated_entities(db_conn)
        result = list_entities_in_date_range(db_conn, end_date="2025-12-31")
        ids = {e["entity_id"] for e in result}
        assert "org:old" in ids
        assert "org:mid" in ids
        assert "org:new" not in ids  # first_seen 2026-01-20 > 2025-12-31
        assert "org:nodates" in ids  # NULL first_seen is included

    def test_entities_full_range(self, db_conn):
        """Both start and end date narrow to entities active in window."""
        self._insert_dated_entities(db_conn)
        result = list_entities_in_date_range(
            db_conn, start_date="2025-11-01", end_date="2026-01-31"
        )
        ids = {e["entity_id"] for e in result}
        assert "org:old" not in ids
        assert "org:mid" in ids
        assert "org:new" in ids
        assert "org:nodates" in ids

    def test_entities_with_type_filter(self, db_conn):
        """Date range + type filter combined."""
        self._insert_dated_entities(db_conn)
        insert_entity(db_conn, "model:recent", "Recent Model", "Model",
                      first_seen="2026-01-01", last_seen="2026-02-10")
        result = list_entities_in_date_range(
            db_conn, start_date="2026-01-01", entity_type="Org"
        )
        ids = {e["entity_id"] for e in result}
        assert "model:recent" not in ids
        assert "org:mid" in ids

    def test_relations_no_filter(self, db_conn):
        """No date filter returns all relations."""
        self._insert_dated_relations(db_conn)
        result = list_relations_in_date_range(db_conn)
        assert len(result) == 3

    def test_relations_start_date(self, db_conn):
        """Start date filters relations by document published_at."""
        self._insert_dated_relations(db_conn)
        result = list_relations_in_date_range(db_conn, start_date="2025-11-01")
        assert len(result) == 2  # doc_mid and doc_new

    def test_relations_end_date(self, db_conn):
        """End date filters relations by document published_at."""
        self._insert_dated_relations(db_conn)
        result = list_relations_in_date_range(db_conn, end_date="2025-12-31")
        assert len(result) == 2  # doc_old and doc_mid

    def test_relations_full_range(self, db_conn):
        """Full date range narrows to relations in window."""
        self._insert_dated_relations(db_conn)
        result = list_relations_in_date_range(
            db_conn, start_date="2025-11-01", end_date="2025-12-31"
        )
        assert len(result) == 1  # only doc_mid
