"""Tests for source_type column migration and ingest dispatcher."""

import sqlite3
import pytest
from pathlib import Path

from db import init_db
from ingest.dispatch import get_fetcher, is_supported, registered_types


class TestSourceTypeMigration:
    """Test that source_type column is added to documents table."""

    def test_new_db_has_source_type(self, tmp_path):
        """Fresh database should have source_type column."""
        conn = init_db(tmp_path / "fresh.sqlite")
        cols = {row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()}
        assert "source_type" in cols
        conn.close()

    def test_existing_db_gets_source_type(self, tmp_path):
        """Existing database without source_type should get it via migration."""
        db_path = tmp_path / "legacy.sqlite"
        # Create a pre-migration DB with all original columns but no source_type
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE documents (
                doc_id TEXT PRIMARY KEY,
                url TEXT,
                source TEXT,
                title TEXT,
                published_at TEXT,
                fetched_at TEXT,
                raw_path TEXT,
                text_path TEXT,
                content_hash TEXT,
                status TEXT,
                error TEXT,
                extracted_by TEXT,
                quality_score REAL,
                escalation_failed TEXT
            )
        """)
        conn.execute("""
            INSERT INTO documents (doc_id, url, source, title, status)
            VALUES ('doc1', 'http://example.com', 'Test', 'Title', 'cleaned')
        """)
        conn.commit()
        conn.close()

        # Re-open with init_db which should run migration
        conn = init_db(db_path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()}
        assert "source_type" in cols

        # Existing row should have default 'rss'
        row = conn.execute("SELECT source_type FROM documents WHERE doc_id='doc1'").fetchone()
        assert row[0] == "rss"
        conn.close()

    def test_source_type_default_is_rss(self, tmp_path):
        """Inserting without source_type should default to 'rss'."""
        conn = init_db(tmp_path / "default.sqlite")
        conn.execute("""
            INSERT INTO documents (doc_id, url, source, title, status)
            VALUES ('doc2', 'http://example.com/2', 'Feed', 'Title 2', 'cleaned')
        """)
        row = conn.execute("SELECT source_type FROM documents WHERE doc_id='doc2'").fetchone()
        assert row[0] == "rss"
        conn.close()

    def test_source_type_accepts_bluesky(self, tmp_path):
        """Should accept non-rss source types."""
        conn = init_db(tmp_path / "bluesky.sqlite")
        conn.execute("""
            INSERT INTO documents (doc_id, url, source, source_type, title, status)
            VALUES ('doc3', 'at://did:plc:abc/post/123', 'Bluesky', 'bluesky', 'Post', 'cleaned')
        """)
        row = conn.execute("SELECT source_type FROM documents WHERE doc_id='doc3'").fetchone()
        assert row[0] == "bluesky"
        conn.close()


class TestIngestDispatcher:
    """Test feed type routing."""

    def test_rss_type_supported(self):
        assert is_supported("rss")

    def test_atom_type_supported(self):
        assert is_supported("atom")

    def test_bluesky_type_supported(self):
        assert is_supported("bluesky")

    def test_reddit_type_supported(self):
        assert is_supported("reddit")

    def test_unknown_type_not_supported(self):
        assert not is_supported("twitter")

    def test_registered_types_sorted(self):
        types = registered_types()
        assert types == sorted(types)
        assert "rss" in types
        assert "bluesky" in types
        assert "reddit" in types

    def test_get_fetcher_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown feed type"):
            get_fetcher("twitter")

    def test_get_fetcher_bluesky_import_error(self):
        """Bluesky module doesn't exist yet — should raise ImportError."""
        with pytest.raises(ImportError):
            get_fetcher("bluesky")

    def test_get_fetcher_reddit_import_error(self):
        """Reddit module doesn't exist yet — should raise ImportError."""
        with pytest.raises(ImportError):
            get_fetcher("reddit")
