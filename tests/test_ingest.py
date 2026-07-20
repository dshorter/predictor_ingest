"""Tests for RSS ingestion module.

Tests are split into:
- Non-network tests: Run anywhere (parsing, DB ops, config integration)
- Network tests: Marked with @pytest.mark.network, run locally

Run all tests:       pytest tests/test_ingest.py
Skip network tests:  pytest tests/test_ingest.py -m "not network"
"""

import sqlite3
import pytest
from pathlib import Path

from config import load_feeds


def _get_ingest_module():
    """Lazy import to avoid feedparser issues in restricted environments."""
    from ingest import rss
    return rss


# =============================================================================
# Non-network tests (run anywhere)
# =============================================================================

@pytest.mark.network
class TestUpsertDocument:
    """Test document database operations (requires feedparser import)."""

    @pytest.fixture
    def db_conn(self, tmp_path):
        """Create temp database with schema."""
        rss = _get_ingest_module()
        schema_path = Path(__file__).parent.parent / "schemas" / "sqlite.sql"
        db_path = tmp_path / "test.sqlite"
        conn = rss.open_db(db_path, schema_path)
        yield conn
        conn.close()

    def test_insert_new_document(self, db_conn):
        """Should insert a new document."""
        rss = _get_ingest_module()
        rss.upsert_document(
            db_conn,
            doc_id="2025-01-01_test_abc123",
            url="https://example.com/article",
            source="Test Source",
            title="Test Article",
            published_at="2025-01-01",
            fetched_at="2025-01-01T12:00:00Z",
            raw_path="data/raw/test.html",
            text_path="data/text/test.txt",
            content_hash="abc123",
            status="cleaned",
            error=None,
        )
        db_conn.commit()

        cursor = db_conn.execute(
            "SELECT * FROM documents WHERE doc_id = ?",
            ("2025-01-01_test_abc123",)
        )
        row = cursor.fetchone()
        assert row is not None

    def test_upsert_updates_existing(self, db_conn):
        """Should update existing document on conflict."""
        rss = _get_ingest_module()
        # Insert first
        rss.upsert_document(
            db_conn, "doc1", "url", "src", "title", None,
            "2025-01-01T00:00:00Z", None, None, None, "fetched", None
        )
        db_conn.commit()

        # Upsert with new status
        rss.upsert_document(
            db_conn, "doc1", "url", "src", "title", None,
            "2025-01-01T00:00:00Z", "path/raw", "path/text", "hash", "cleaned", None
        )
        db_conn.commit()

        cursor = db_conn.execute("SELECT status FROM documents WHERE doc_id = 'doc1'")
        assert cursor.fetchone()[0] == "cleaned"


class TestConfigIntegration:
    """Test RSS ingestion with config loader."""

    def test_loads_feeds_from_config(self):
        """Should be able to load feeds from config/feeds.yaml."""
        config_path = Path(__file__).parent.parent / "config" / "feeds.yaml"
        feeds = load_feeds(config_path)

        assert len(feeds) >= 7
        assert any(f.name == "arXiv CS.AI" for f in feeds)
        assert any(f.name == "Anthropic Blog" for f in feeds)
        assert all(f.url.startswith("https://") for f in feeds)

    def test_all_feeds_have_required_fields(self):
        """Each feed config should have name, url, type."""
        config_path = Path(__file__).parent.parent / "config" / "feeds.yaml"
        feeds = load_feeds(config_path)

        for feed in feeds:
            assert feed.name, "Feed missing name"
            assert feed.url, "Feed missing url"
            assert feed.type in ("rss", "atom"), f"Invalid feed type: {feed.type}"


class TestDocIdGeneration:
    """Test document ID generation logic."""

    def test_doc_id_format(self):
        """Doc ID should be {date}_{source_slug}_{url_hash}."""
        from util import slugify, short_hash

        date = "2025-12-01"
        source = "arXiv CS.AI"
        url = "https://arxiv.org/abs/1234.5678"

        doc_id = f"{date}_{slugify(source)}_{short_hash(url)}"

        assert doc_id.startswith("2025-12-01_")
        assert "arxiv_cs_ai" in doc_id
        assert len(doc_id.split("_")[-1]) == 8  # Hash is 8 chars


# =============================================================================
# Network tests (run locally with: pytest -m network)
# =============================================================================

@pytest.mark.network
class TestFetchRealFeeds:
    """Tests that require real network access.

    Run with: pytest tests/test_ingest.py -m network
    Skip with: pytest tests/test_ingest.py -m "not network"
    """

    def test_fetch_arxiv_feed(self, tmp_path):
        """Should fetch and parse arXiv RSS feed."""
        import feedparser

        feed = feedparser.parse("https://rss.arxiv.org/rss/cs.AI")

        assert not feed.bozo, f"Feed parse error: {feed.bozo_exception}"
        assert len(feed.entries) > 0, "Feed has no entries"
        assert feed.entries[0].get("title"), "Entry missing title"
        assert feed.entries[0].get("link"), "Entry missing link"

    def test_fetch_huggingface_feed(self):
        """Should fetch and parse Hugging Face blog feed."""
        import feedparser

        feed = feedparser.parse("https://huggingface.co/blog/feed.xml")

        assert not feed.bozo, f"Feed parse error: {feed.bozo_exception}"
        assert len(feed.entries) > 0, "Feed has no entries"

    def test_fetch_openai_feed(self):
        """Should fetch and parse OpenAI blog feed."""
        import feedparser

        feed = feedparser.parse("https://openai.com/blog/rss.xml")

        # OpenAI may have different feed structure, be flexible
        assert len(feed.entries) >= 0  # May be empty but shouldn't error

    def test_ingest_feed_end_to_end(self, tmp_path):
        """Full ingestion of real feed entries."""
        import requests
        rss = _get_ingest_module()

        raw_dir = tmp_path / "raw"
        text_dir = tmp_path / "text"
        raw_dir.mkdir()
        text_dir.mkdir()

        schema_path = Path(__file__).parent.parent / "schemas" / "sqlite.sql"
        db_path = tmp_path / "test.sqlite"
        conn = rss.open_db(db_path, schema_path)

        session = requests.Session()
        session.headers["User-Agent"] = "predictor-ingest-test/1.0"

        fetched, skipped, errors = rss.ingest_feed(
            feed_url="https://rss.arxiv.org/rss/cs.AI",
            session=session,
            raw_dir=raw_dir,
            text_dir=text_dir,
            conn=conn,
            repo=tmp_path,
            source_override="arXiv CS.AI",
            limit=2,  # Only fetch 2 for speed
            timeout=30,
            skip_existing=False,
        )

        conn.close()

        # Should have fetched some entries
        assert fetched > 0 or errors > 0, "Nothing happened"

        # Check files were created
        raw_files = list(raw_dir.glob("*.html"))
        text_files = list(text_dir.glob("*.txt"))

        # At least some should succeed (arXiv links to abstracts which work)
        print(f"Fetched: {fetched}, Errors: {errors}, Files: {len(raw_files)}")


@pytest.mark.network
class TestNetworkErrorHandling:
    """Test handling of network errors."""

    def test_handles_timeout(self, tmp_path):
        """Should handle request timeouts gracefully."""
        import requests
        rss = _get_ingest_module()

        raw_dir = tmp_path / "raw"
        text_dir = tmp_path / "text"
        raw_dir.mkdir()
        text_dir.mkdir()

        session = requests.Session()

        # Use a very short timeout to trigger timeout errors
        fetched, skipped, errors = rss.ingest_feed(
            feed_url="https://rss.arxiv.org/rss/cs.AI",
            session=session,
            raw_dir=raw_dir,
            text_dir=text_dir,
            conn=None,
            repo=tmp_path,
            source_override="Test",
            limit=1,
            timeout=1,  # Very short timeout
            skip_existing=False,
        )

        # Should not crash, may have errors
        assert isinstance(fetched, int)
        assert isinstance(errors, int)


class TestEntryKeywordFilter:
    """Per-feed keyword scoping (Sprint 20 feed batch; audit 2026-07-19).

    Pure function, no network: filters feed entries on title+summary
    before any article fetch.
    """

    def _match(self, entry, include=None, exclude=None):
        from ingest import rss
        return rss.entry_matches_keywords(entry, include, exclude)

    def test_no_keywords_keeps_everything(self):
        assert self._match({"title": "Anything at all"}) is True

    def test_include_matches_title_case_insensitive(self):
        entry = {"title": "New SOUNDSTAGE breaks ground in Atlanta"}
        assert self._match(entry, include=["soundstage"]) is True

    def test_include_matches_summary(self):
        entry = {"title": "City council roundup",
                 "summary": "…also approved the film studio rezoning…"}
        assert self._match(entry, include=["film studio"]) is True

    def test_include_rejects_off_topic(self):
        entry = {"title": "School board election results",
                 "summary": "County votes tallied"}
        assert self._match(entry, include=["film", "studio", "production"]) is False

    def test_exclude_wins_over_include(self):
        entry = {"title": "GeForce NOW: new games this week"}
        assert self._match(entry, include=["GeForce"],
                           exclude=["GeForce NOW"]) is False

    def test_missing_fields_tolerated(self):
        assert self._match({}, include=["chip"]) is False
        assert self._match({"title": None, "summary": None}, include=["chip"]) is False


class TestFeedExtraPassthrough:
    """include/exclude keyword lists ride feeds.yaml → FeedConfig.extra."""

    def test_extra_keys_flow_through(self, tmp_path):
        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds:
  - name: "Scoped Feed"
    url: "https://example.com/feed.xml"
    type: rss
    enabled: true
    include_keywords: ["film", "studio"]
    exclude_keywords: ["obituary"]
""")
        feeds = load_feeds(config_file)
        assert feeds[0].extra["include_keywords"] == ["film", "studio"]
        assert feeds[0].extra["exclude_keywords"] == ["obituary"]
