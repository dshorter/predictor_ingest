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


class TestSourcePolicy:
    """Extraction policy by source_type — chatter sources are ingest-only."""

    def test_rss_extracts(self):
        from ingest.source_policy import should_extract
        assert should_extract("rss") is True

    def test_atom_extracts(self):
        from ingest.source_policy import should_extract
        assert should_extract("atom") is True

    def test_substack_extracts(self):
        from ingest.source_policy import should_extract
        assert should_extract("substack") is True

    def test_edgar_extracts(self):
        from ingest.source_policy import should_extract
        assert should_extract("edgar") is True

    def test_patents_extract(self):
        from ingest.source_policy import should_extract
        assert should_extract("patents") is True

    def test_bluesky_does_not_extract(self):
        """Bluesky posts are too short; ingest-only for velocity signal."""
        from ingest.source_policy import should_extract
        assert should_extract("bluesky") is False

    def test_reddit_does_not_extract(self):
        """Reddit comments are mostly short; ingest-only for velocity signal."""
        from ingest.source_policy import should_extract
        assert should_extract("reddit") is False

    def test_unknown_defaults_to_extract(self):
        """Unknown source_types default to extract=True (conservative)."""
        from ingest.source_policy import should_extract
        assert should_extract("twitter") is True

    def test_empty_or_none_defaults_to_extract(self):
        """Missing source_type defaults to extract=True."""
        from ingest.source_policy import should_extract
        assert should_extract("") is True
        assert should_extract(None) is True

    def test_case_insensitive(self):
        """source_type matching is case-insensitive."""
        from ingest.source_policy import should_extract
        assert should_extract("Bluesky") is False
        assert should_extract("REDDIT") is False
        assert should_extract("RSS") is True

    def test_extracting_types_excludes_chatter(self):
        from ingest.source_policy import extracting_source_types
        types = extracting_source_types()
        assert "rss" in types
        assert "atom" in types
        assert "bluesky" not in types
        assert "reddit" not in types

    def test_non_extracting_types_are_chatter(self):
        from ingest.source_policy import non_extracting_source_types
        types = non_extracting_source_types()
        assert types == ["bluesky", "reddit"]

    def test_extracting_types_sorted(self):
        from ingest.source_policy import extracting_source_types
        types = extracting_source_types()
        assert types == sorted(types)

    def test_registered_source_types_covers_all(self):
        from ingest.source_policy import (
            registered_source_types,
            extracting_source_types,
            non_extracting_source_types,
        )
        all_types = registered_source_types()
        assert set(all_types) == set(extracting_source_types() + non_extracting_source_types())


class TestDocSelectFiltersChatter:
    """Bench-load query and docpack candidate queries exclude chatter sources."""

    def _make_doc(self, conn, doc_id, source_type, status="cleaned"):
        """Helper to insert a minimal document row."""
        conn.execute(
            """INSERT INTO documents (doc_id, url, source, source_type,
                                      title, published_at, fetched_at,
                                      text_path, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (doc_id, f"http://x/{doc_id}", "test", source_type,
             "T", "2026-05-10", "2026-05-10T00:00:00Z",
             f"/tmp/{doc_id}.txt", status),
        )

    def test_load_bench_excludes_chatter(self, tmp_path):
        """Bench-resident bluesky/reddit docs are not returned for extraction."""
        from doc_select import load_bench

        conn = init_db(tmp_path / "bench.sqlite")
        # Two docs: one rss (extractable), one bluesky (chatter)
        self._make_doc(conn, "d1", "rss")
        self._make_doc(conn, "d2", "bluesky")
        # Both on the bench (expires_at is in the future so they remain unexpired)
        conn.execute(
            """INSERT INTO bench (doc_id, quality_score, scored_at, expires_at)
               VALUES (?, ?, ?, ?)""",
            ("d1", 0.8, "2026-05-10", "2026-12-31"),
        )
        conn.execute(
            """INSERT INTO bench (doc_id, quality_score, scored_at, expires_at)
               VALUES (?, ?, ?, ?)""",
            ("d2", 0.9, "2026-05-10", "2026-12-31"),
        )
        conn.commit()

        rows = load_bench(conn)
        ids = {r["doc_id"] for r in rows}
        assert "d1" in ids, "rss doc should be returned"
        assert "d2" not in ids, "bluesky doc should be filtered out"
        conn.close()
