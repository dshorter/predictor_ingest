"""Tests for retry logic in ingest and the repair_data script."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests


def _get_ingest_module():
    from ingest import rss
    return rss


class TestFetchWithRetry:
    """Test the fetch_with_retry function."""

    def test_success_no_retry(self):
        """Successful request should not retry."""
        rss = _get_ingest_module()
        session = MagicMock()
        resp = MagicMock()
        resp.ok = True
        resp.status_code = 200
        session.get.return_value = resp

        result = rss.fetch_with_retry(session, "https://example.com", timeout=10)
        assert result == resp
        assert session.get.call_count == 1

    def test_403_no_retry(self):
        """403 is not retryable — should fail immediately."""
        rss = _get_ingest_module()
        session = MagicMock()
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 403
        resp.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        session.get.return_value = resp

        with pytest.raises(requests.HTTPError):
            rss.fetch_with_retry(session, "https://example.com", timeout=10)
        # Should NOT retry on 403
        assert session.get.call_count == 1

    @patch("ingest.rss.time.sleep")
    def test_429_retries_then_succeeds(self, mock_sleep):
        """429 should retry with backoff, then succeed."""
        rss = _get_ingest_module()
        session = MagicMock()

        fail_resp = MagicMock()
        fail_resp.ok = False
        fail_resp.status_code = 429
        fail_resp.headers = {}
        fail_resp.raise_for_status.side_effect = requests.HTTPError("429 Too Many Requests")

        ok_resp = MagicMock()
        ok_resp.ok = True
        ok_resp.status_code = 200

        session.get.side_effect = [fail_resp, ok_resp]

        result = rss.fetch_with_retry(
            session, "https://example.com", timeout=10,
            max_retries=3, backoff_base=1,
        )
        assert result == ok_resp
        assert session.get.call_count == 2
        mock_sleep.assert_called_once()

    @patch("ingest.rss.time.sleep")
    def test_429_respects_retry_after(self, mock_sleep):
        """429 with Retry-After header should use that value."""
        rss = _get_ingest_module()
        session = MagicMock()

        fail_resp = MagicMock()
        fail_resp.ok = False
        fail_resp.status_code = 429
        fail_resp.headers = {"Retry-After": "30"}
        fail_resp.raise_for_status.side_effect = requests.HTTPError("429")

        ok_resp = MagicMock()
        ok_resp.ok = True
        ok_resp.status_code = 200

        session.get.side_effect = [fail_resp, ok_resp]

        rss.fetch_with_retry(
            session, "https://example.com", timeout=10,
            max_retries=3, backoff_base=2,
        )
        # Should have slept for 30s (from Retry-After), not 2s (from backoff)
        mock_sleep.assert_called_once_with(30.0)

    @patch("ingest.rss.time.sleep")
    def test_all_retries_exhausted(self, mock_sleep):
        """Should raise after all retries exhausted."""
        rss = _get_ingest_module()
        session = MagicMock()

        fail_resp = MagicMock()
        fail_resp.ok = False
        fail_resp.status_code = 429
        fail_resp.headers = {}
        fail_resp.raise_for_status.side_effect = requests.HTTPError("429")

        session.get.return_value = fail_resp

        with pytest.raises(requests.HTTPError):
            rss.fetch_with_retry(
                session, "https://example.com", timeout=10,
                max_retries=2, backoff_base=1,
            )
        # 1 initial + 2 retries = 3 total
        assert session.get.call_count == 3

    @patch("ingest.rss.time.sleep")
    def test_500_is_retryable(self, mock_sleep):
        """500 server error should be retried."""
        rss = _get_ingest_module()
        session = MagicMock()

        fail_resp = MagicMock()
        fail_resp.ok = False
        fail_resp.status_code = 500
        fail_resp.headers = {}
        fail_resp.raise_for_status.side_effect = requests.HTTPError("500")

        ok_resp = MagicMock()
        ok_resp.ok = True
        ok_resp.status_code = 200

        session.get.side_effect = [fail_resp, ok_resp]

        result = rss.fetch_with_retry(
            session, "https://example.com", timeout=10,
            max_retries=3, backoff_base=1,
        )
        assert result == ok_resp


class TestConsecutiveErrorBail:
    """Test that ingest bails early after too many consecutive errors."""

    @patch("ingest.rss.time.sleep")
    @patch("ingest.rss.feedparser")
    def test_bails_after_consecutive_errors(self, mock_feedparser, mock_sleep):
        """Should bail after 5 consecutive errors."""
        rss = _get_ingest_module()

        # Create mock feed with 10 entries
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.status = 200
        mock_feed.entries = [
            MagicMock(get=lambda key, _i=i: {
                "link": f"https://example.com/{_i}",
                "title": f"Article {_i}",
            }.get(key))
            for i in range(10)
        ]
        mock_feed.feed = MagicMock()
        mock_feed.feed.get = MagicMock(return_value="Test Feed")
        mock_feedparser.parse.return_value = mock_feed

        session = MagicMock()
        # All requests fail with 403
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 403
        resp.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        session.get.return_value = resp

        raw_dir = Path("/tmp/test_bail_raw")
        text_dir = Path("/tmp/test_bail_text")
        raw_dir.mkdir(parents=True, exist_ok=True)
        text_dir.mkdir(parents=True, exist_ok=True)

        fetched, skipped, errors, reachable = rss.ingest_feed(
            feed_url="https://example.com/feed",
            session=session,
            raw_dir=raw_dir,
            text_dir=text_dir,
            conn=None,
            repo=Path("/tmp"),
            source_override="Test",
            limit=10,
            timeout=10,
            skip_existing=False,
            delay=0,
        )

        # Should have bailed before trying all 10
        assert errors > 0
        # Total attempts should be less than 10 (bailed after 5 consecutive)
        assert session.get.call_count <= 6  # 5 fails + bail


class TestRepairData:
    """Test the repair_data script functions."""

    @pytest.fixture
    def setup_db(self, tmp_path):
        """Create a test database with sample data."""
        from db import init_db

        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Insert a cleaned doc with text file
        text_path = tmp_path / "text" / "good_doc.txt"
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text("Good article text\n")

        raw_path = tmp_path / "raw" / "good_doc.html"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text("<html><body>Good article text</body></html>")

        conn.execute(
            """INSERT INTO documents (doc_id, url, source, title, fetched_at,
               raw_path, text_path, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("good_doc", "https://example.com/good", "Test", "Good",
             "2026-02-17T00:00:00Z",
             str(raw_path), str(text_path), "cleaned"),
        )

        # Insert a cleaned doc with MISSING text file but raw exists
        raw_path2 = tmp_path / "raw" / "orphaned_doc.html"
        raw_path2.write_text("<html><body>Orphaned article text</body></html>")
        missing_text = tmp_path / "text" / "orphaned_doc.txt"

        conn.execute(
            """INSERT INTO documents (doc_id, url, source, title, fetched_at,
               raw_path, text_path, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("orphaned_doc", "https://example.com/orphan", "Test", "Orphan",
             "2026-02-17T00:00:00Z",
             str(raw_path2), str(missing_text), "cleaned"),
        )

        # Insert a doc with 429 error
        conn.execute(
            """INSERT INTO documents (doc_id, url, source, title, fetched_at,
               status, error)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("error_429_doc", "https://example.com/rate-limited", "Test", "Rate Limited",
             "2026-02-17T00:00:00Z", "error",
             "request_error: 429 Client Error: Too Many Requests"),
        )

        # Insert a doc with 403 error
        conn.execute(
            """INSERT INTO documents (doc_id, url, source, title, fetched_at,
               status, error)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("error_403_doc", "https://example.com/forbidden", "Test", "Forbidden",
             "2026-02-17T00:00:00Z", "error",
             "request_error: 403 Client Error: Forbidden"),
        )

        conn.commit()
        return conn, tmp_path

    def test_check_integrity(self, setup_db):
        """Should correctly identify data issues."""
        import importlib
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        # Import repair_data module
        spec = importlib.util.spec_from_file_location(
            "repair_data",
            Path(__file__).parent.parent / "scripts" / "repair_data.py",
        )
        repair = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(repair)

        conn, tmp_path = setup_db
        issues = repair.check_integrity(conn)

        assert issues["total_docs"] == 4
        assert issues["cleaned_docs"] == 2
        assert issues["error_docs"] == 2
        assert issues["missing_text_files"] == 1  # orphaned_doc
        assert issues["retryable_errors"] == 1     # 429 doc
        assert issues["permanent_errors"] == 1     # 403 doc

    def test_fix_missing_text(self, setup_db):
        """Should recover text files from raw HTML."""
        import importlib
        spec = importlib.util.spec_from_file_location(
            "repair_data",
            Path(__file__).parent.parent / "scripts" / "repair_data.py",
        )
        repair = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(repair)

        conn, tmp_path = setup_db
        recovered = repair.fix_missing_text(conn, dry_run=False)

        assert recovered == 1

        # The text file should now exist
        text_path = tmp_path / "text" / "orphaned_doc.txt"
        assert text_path.exists()
        content = text_path.read_text()
        assert "Orphaned article text" in content

    def test_reset_retryable_errors(self, setup_db):
        """Should reset 429 docs but not 403 docs."""
        import importlib
        spec = importlib.util.spec_from_file_location(
            "repair_data",
            Path(__file__).parent.parent / "scripts" / "repair_data.py",
        )
        repair = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(repair)

        conn, tmp_path = setup_db
        reset_count = repair.reset_retryable_errors(conn, dry_run=False)

        assert reset_count == 1

        # 429 doc should be gone
        row = conn.execute(
            "SELECT * FROM documents WHERE doc_id = 'error_429_doc'"
        ).fetchone()
        assert row is None

        # 403 doc should still be there
        row = conn.execute(
            "SELECT * FROM documents WHERE doc_id = 'error_403_doc'"
        ).fetchone()
        assert row is not None
