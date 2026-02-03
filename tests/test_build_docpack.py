"""Tests for docpack generator script.

Tests the build_docpack.py script which generates daily document bundles
for manual extraction via ChatGPT (Mode B).
"""

import json
import sqlite3
import pytest
from pathlib import Path
from datetime import date
import sys

# Add scripts directory to path to import build_docpack
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

import build_docpack


@pytest.fixture
def db_conn(tmp_path):
    """Create a temporary database with documents table."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))

    # Create documents table
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
            error TEXT
        )
    """)
    conn.commit()

    yield conn
    conn.close()


@pytest.fixture
def sample_docs(db_conn, tmp_path):
    """Insert sample documents into the database and create text files."""
    docs = [
        {
            'doc_id': '2026-02-03_example_001',
            'url': 'https://example.com/article1',
            'source': 'Example News',
            'title': 'AI Breakthrough Announced',
            'published_at': '2026-02-03',
            'fetched_at': '2026-02-03T10:00:00Z',
            'text_path': 'data/text/2026-02-03_example_001.txt',
            'status': 'cleaned'
        },
        {
            'doc_id': '2026-02-03_example_002',
            'url': 'https://example.com/article2',
            'source': 'Tech Blog',
            'title': 'New Model Released',
            'published_at': '2026-02-03',
            'fetched_at': '2026-02-03T11:00:00Z',
            'text_path': 'data/text/2026-02-03_example_002.txt',
            'status': 'fetched'
        },
        {
            'doc_id': '2026-02-02_example_003',
            'url': 'https://example.com/article3',
            'source': 'Research Papers',
            'title': 'Different Date Article',
            'published_at': '2026-02-02',
            'fetched_at': '2026-02-02T09:00:00Z',
            'text_path': 'data/text/2026-02-02_example_003.txt',
            'status': 'cleaned'
        },
        {
            'doc_id': '2026-02-03_example_004',
            'url': 'https://example.com/article4',
            'source': 'News Site',
            'title': 'Article Without Text File',
            'published_at': '2026-02-03',
            'fetched_at': '2026-02-03T12:00:00Z',
            'text_path': 'data/text/missing.txt',
            'status': 'cleaned'
        },
        {
            'doc_id': '2026-02-03_example_005',
            'url': 'https://example.com/article5',
            'source': 'Blog',
            'title': 'Extracted Status (Should Be Skipped)',
            'published_at': '2026-02-03',
            'fetched_at': '2026-02-03T13:00:00Z',
            'text_path': 'data/text/2026-02-03_example_005.txt',
            'status': 'extracted'  # Should be skipped - already extracted
        }
    ]

    for doc in docs:
        db_conn.execute(
            """INSERT INTO documents
               (doc_id, url, source, title, published_at, fetched_at, text_path, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (doc['doc_id'], doc['url'], doc['source'], doc['title'],
             doc['published_at'], doc['fetched_at'], doc['text_path'], doc['status'])
        )

    db_conn.commit()

    # Create text files for some documents
    text_dir = tmp_path / 'data' / 'text'
    text_dir.mkdir(parents=True, exist_ok=True)

    (text_dir / '2026-02-03_example_001.txt').write_text(
        'This is the cleaned text for article 1 about AI breakthroughs.'
    )
    (text_dir / '2026-02-03_example_002.txt').write_text(
        'This is the cleaned text for article 2 about new models.'
    )
    (text_dir / '2026-02-02_example_003.txt').write_text(
        'This is the cleaned text for article 3 from a different date.'
    )
    # Note: Not creating missing.txt to test missing file handling

    return docs


class TestGetDocuments:
    """Test document querying from database."""

    def test_filters_by_date(self, db_conn, sample_docs):
        """Should only return documents fetched on the specified date."""
        docs = build_docpack.get_documents(db_conn, '2026-02-03', 100)

        # Should get 4 docs (3 with status cleaned/fetched, 1 with extracted status excluded)
        # Actually, the query filters by status, so extracted is excluded
        assert len(docs) == 3

        # All should be from 2026-02-03
        for doc in docs:
            assert doc['fetched_at'].startswith('2026-02-03')

    def test_filters_by_status(self, db_conn, sample_docs):
        """Should only return documents with status 'cleaned' or 'fetched'."""
        docs = build_docpack.get_documents(db_conn, '2026-02-03', 100)

        # Should exclude the 'extracted' status document
        doc_ids = [d['doc_id'] for d in docs]
        assert '2026-02-03_example_005' not in doc_ids

        # Should include cleaned and fetched
        assert '2026-02-03_example_001' in doc_ids
        assert '2026-02-03_example_002' in doc_ids

    def test_respects_max_docs_limit(self, db_conn, sample_docs):
        """Should limit results to max_docs parameter."""
        docs = build_docpack.get_documents(db_conn, '2026-02-03', 1)

        assert len(docs) == 1

    def test_orders_by_fetched_at_desc(self, db_conn, sample_docs):
        """Should return documents in reverse chronological order."""
        docs = build_docpack.get_documents(db_conn, '2026-02-03', 100)

        # Should be ordered newest first
        # doc_004 was fetched at 12:00, doc_002 at 11:00, doc_001 at 10:00
        assert docs[0]['doc_id'] == '2026-02-03_example_004'
        assert docs[1]['doc_id'] == '2026-02-03_example_002'
        assert docs[2]['doc_id'] == '2026-02-03_example_001'

    def test_returns_empty_for_no_matches(self, db_conn, sample_docs):
        """Should return empty list when no documents match."""
        docs = build_docpack.get_documents(db_conn, '2026-01-01', 100)

        assert docs == []


class TestReadTextContent:
    """Test text file reading functionality."""

    def test_reads_existing_file(self, tmp_path):
        """Should read and return text content from existing file."""
        text_file = tmp_path / 'data' / 'text' / 'test.txt'
        text_file.parent.mkdir(parents=True, exist_ok=True)
        text_file.write_text('Sample text content')

        content = build_docpack.read_text_content('data/text/test.txt', tmp_path)

        assert content == 'Sample text content'

    def test_returns_none_for_missing_file(self, tmp_path):
        """Should return None when file doesn't exist."""
        content = build_docpack.read_text_content('data/text/missing.txt', tmp_path)

        assert content is None

    def test_returns_none_for_null_path(self, tmp_path):
        """Should return None when text_path is None."""
        content = build_docpack.read_text_content(None, tmp_path)

        assert content is None

    def test_handles_unicode_content(self, tmp_path):
        """Should correctly read files with unicode characters."""
        text_file = tmp_path / 'data' / 'text' / 'unicode.txt'
        text_file.parent.mkdir(parents=True, exist_ok=True)
        text_file.write_text('Unicode content: 日本語, emoji 🚀, special chars: é à ñ')

        content = build_docpack.read_text_content('data/text/unicode.txt', tmp_path)

        assert 'Unicode content: 日本語' in content
        assert '🚀' in content


class TestBuildJsonl:
    """Test JSONL format generation."""

    def test_creates_valid_jsonl_objects(self, tmp_path):
        """Should create valid JSONL objects with all required fields."""
        text_file = tmp_path / 'data' / 'text' / 'test.txt'
        text_file.parent.mkdir(parents=True, exist_ok=True)
        text_file.write_text('Article content here')

        docs = [{
            'doc_id': 'test_doc_001',
            'url': 'https://example.com',
            'source': 'Example',
            'title': 'Test Article',
            'published_at': '2026-02-03',
            'fetched_at': '2026-02-03T10:00:00Z',
            'text_path': 'data/text/test.txt'
        }]

        jsonl_data = build_docpack.build_jsonl(docs, tmp_path)

        assert len(jsonl_data) == 1
        obj = jsonl_data[0]

        assert obj['docId'] == 'test_doc_001'
        assert obj['url'] == 'https://example.com'
        assert obj['source'] == 'Example'
        assert obj['title'] == 'Test Article'
        assert obj['published'] == '2026-02-03'
        assert obj['fetched'] == '2026-02-03T10:00:00Z'
        assert obj['text'] == 'Article content here'

    def test_skips_documents_with_missing_text_files(self, tmp_path, capsys):
        """Should skip documents when text file is missing and log warning."""
        docs = [{
            'doc_id': 'missing_doc',
            'url': 'https://example.com',
            'source': 'Example',
            'title': 'Missing Text',
            'published_at': '2026-02-03',
            'fetched_at': '2026-02-03T10:00:00Z',
            'text_path': 'data/text/missing.txt'
        }]

        jsonl_data = build_docpack.build_jsonl(docs, tmp_path)

        assert len(jsonl_data) == 0

        # Should print warning
        captured = capsys.readouterr()
        assert 'WARNING' in captured.err
        assert 'missing_doc' in captured.err

    def test_handles_null_published_date(self, tmp_path):
        """Should handle documents with null published_at."""
        text_file = tmp_path / 'data' / 'text' / 'test.txt'
        text_file.parent.mkdir(parents=True, exist_ok=True)
        text_file.write_text('Article content')

        docs = [{
            'doc_id': 'test_doc',
            'url': 'https://example.com',
            'source': 'Example',
            'title': 'Test Article',
            'published_at': None,
            'fetched_at': '2026-02-03T10:00:00Z',
            'text_path': 'data/text/test.txt'
        }]

        jsonl_data = build_docpack.build_jsonl(docs, tmp_path)

        assert len(jsonl_data) == 1
        assert jsonl_data[0]['published'] == ''


class TestBuildMarkdown:
    """Test Markdown format generation."""

    def test_creates_markdown_with_header(self, tmp_path):
        """Should create markdown with proper header and instructions."""
        text_file = tmp_path / 'data' / 'text' / 'test.txt'
        text_file.parent.mkdir(parents=True, exist_ok=True)
        text_file.write_text('Article content')

        docs = [{
            'doc_id': 'test_doc',
            'url': 'https://example.com',
            'source': 'Example',
            'title': 'Test Article',
            'published_at': '2026-02-03',
            'fetched_at': '2026-02-03T10:00:00Z',
            'text_path': 'data/text/test.txt'
        }]

        markdown, count = build_docpack.build_markdown(docs, tmp_path, '2026-02-03')

        assert '# Daily Document Bundle — 2026-02-03' in markdown
        assert 'Extract entities, relations, and evidence' in markdown
        assert 'schemas/extraction.json' in markdown
        assert count == 1

    def test_formats_documents_correctly(self, tmp_path):
        """Should format each document with proper markdown structure."""
        text_file = tmp_path / 'data' / 'text' / 'test.txt'
        text_file.parent.mkdir(parents=True, exist_ok=True)
        text_file.write_text('Article content here')

        docs = [{
            'doc_id': 'test_doc_001',
            'url': 'https://example.com/article',
            'source': 'Example News',
            'title': 'Breakthrough in AI',
            'published_at': '2026-02-03',
            'fetched_at': '2026-02-03T10:00:00Z',
            'text_path': 'data/text/test.txt'
        }]

        markdown, count = build_docpack.build_markdown(docs, tmp_path, '2026-02-03')

        assert '## Document 1: Breakthrough in AI' in markdown
        assert '- **docId:** test_doc_001' in markdown
        assert '- **URL:** https://example.com/article' in markdown
        assert '- **Source:** Example News' in markdown
        assert '- **Published:** 2026-02-03' in markdown
        assert '### Text' in markdown
        assert 'Article content here' in markdown

    def test_numbers_documents_sequentially(self, tmp_path):
        """Should number documents sequentially starting from 1."""
        text_dir = tmp_path / 'data' / 'text'
        text_dir.mkdir(parents=True, exist_ok=True)

        (text_dir / 'doc1.txt').write_text('Content 1')
        (text_dir / 'doc2.txt').write_text('Content 2')

        docs = [
            {
                'doc_id': 'doc_001',
                'url': 'https://example.com/1',
                'source': 'Source',
                'title': 'Title 1',
                'published_at': '2026-02-03',
                'fetched_at': '2026-02-03T10:00:00Z',
                'text_path': 'data/text/doc1.txt'
            },
            {
                'doc_id': 'doc_002',
                'url': 'https://example.com/2',
                'source': 'Source',
                'title': 'Title 2',
                'published_at': '2026-02-03',
                'fetched_at': '2026-02-03T11:00:00Z',
                'text_path': 'data/text/doc2.txt'
            }
        ]

        markdown, count = build_docpack.build_markdown(docs, tmp_path, '2026-02-03')

        assert '## Document 1: Title 1' in markdown
        assert '## Document 2: Title 2' in markdown
        assert count == 2

    def test_skips_missing_files_and_adjusts_count(self, tmp_path, capsys):
        """Should skip documents with missing text files and return correct count."""
        text_file = tmp_path / 'data' / 'text' / 'exists.txt'
        text_file.parent.mkdir(parents=True, exist_ok=True)
        text_file.write_text('Existing content')

        docs = [
            {
                'doc_id': 'doc_exists',
                'url': 'https://example.com/1',
                'source': 'Source',
                'title': 'Exists',
                'published_at': '2026-02-03',
                'fetched_at': '2026-02-03T10:00:00Z',
                'text_path': 'data/text/exists.txt'
            },
            {
                'doc_id': 'doc_missing',
                'url': 'https://example.com/2',
                'source': 'Source',
                'title': 'Missing',
                'published_at': '2026-02-03',
                'fetched_at': '2026-02-03T11:00:00Z',
                'text_path': 'data/text/missing.txt'
            }
        ]

        markdown, count = build_docpack.build_markdown(docs, tmp_path, '2026-02-03')

        assert count == 1
        assert 'Exists' in markdown
        assert 'Missing' not in markdown


class TestIntegration:
    """Integration tests for the full script."""

    def test_components_work_together(self, db_conn, sample_docs, tmp_path):
        """Should successfully process documents through all components."""
        # Get documents from database
        docs = build_docpack.get_documents(db_conn, '2026-02-03', 100)
        assert len(docs) > 0

        # Build JSONL
        jsonl_data = build_docpack.build_jsonl(docs, tmp_path)
        assert len(jsonl_data) > 0
        assert all('docId' in obj for obj in jsonl_data)
        assert all('text' in obj for obj in jsonl_data)

        # Build Markdown
        markdown, count = build_docpack.build_markdown(docs, tmp_path, '2026-02-03')
        assert count > 0
        assert '# Daily Document Bundle' in markdown
        assert 'Extract entities, relations' in markdown

        # Verify consistency
        assert count == len(jsonl_data)  # Same number of valid documents
