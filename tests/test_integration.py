"""End-to-end integration tests for the full pipeline.

Tests the complete flow: config → ingest → db → extract → schema validation.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from config import FeedConfig, load_feeds
from db import (
    init_db,
    insert_entity,
    insert_relation,
    insert_evidence,
    get_entity,
    get_relations_for_entity,
)
from extract import (
    build_extraction_prompt,
    parse_extraction_response,
    save_extraction,
    load_extraction,
    EXTRACTOR_VERSION,
)
from schema import validate_extraction
from util import slugify, short_hash, sha256_text, clean_html, utc_now_iso


# Sample document simulating an ingested RSS entry
SAMPLE_DOC = {
    "docId": "2026-01-15_arxiv_cs_ai_abc123",
    "url": "https://arxiv.org/abs/2601.12345",
    "source": "arXiv CS.AI",
    "title": "Transformer Architecture Improvements for Large Language Models",
    "published": "2026-01-15",
    "text": """
We present novel improvements to transformer architectures for training large language models.
Our research at OpenAI demonstrates that the GPT-5 model, trained on the RedPajama dataset,
achieves state-of-the-art performance on the MMLU benchmark.
The model uses 175 billion parameters and requires 1024 A100 GPUs for training.
Google DeepMind has published similar findings with their Gemini Ultra model.
The work builds upon previous research by Anthropic on constitutional AI.
""".strip(),
}

# Sample LLM extraction response
SAMPLE_EXTRACTION_RESPONSE = """
```json
{
  "docId": "2026-01-15_arxiv_cs_ai_abc123",
  "extractorVersion": "1.0.0",
  "entities": [
    {"name": "OpenAI", "type": "Org", "idHint": "org:openai"},
    {"name": "GPT-5", "type": "Model", "idHint": "model:gpt_5"},
    {"name": "RedPajama", "type": "Dataset", "idHint": "dataset:redpajama"},
    {"name": "MMLU", "type": "Benchmark", "idHint": "benchmark:mmlu"},
    {"name": "Google DeepMind", "type": "Org", "idHint": "org:google_deepmind"},
    {"name": "Gemini Ultra", "type": "Model", "idHint": "model:gemini_ultra"},
    {"name": "Anthropic", "type": "Org", "idHint": "org:anthropic"},
    {"name": "A100", "type": "Tech", "idHint": "tech:a100"}
  ],
  "relations": [
    {
      "source": "OpenAI",
      "rel": "CREATED",
      "target": "GPT-5",
      "kind": "asserted",
      "confidence": 0.95,
      "evidence": [{
        "docId": "2026-01-15_arxiv_cs_ai_abc123",
        "url": "https://arxiv.org/abs/2601.12345",
        "published": "2026-01-15",
        "snippet": "Our research at OpenAI demonstrates that the GPT-5 model"
      }]
    },
    {
      "source": "GPT-5",
      "rel": "TRAINED_ON",
      "target": "RedPajama",
      "kind": "asserted",
      "confidence": 0.9,
      "evidence": [{
        "docId": "2026-01-15_arxiv_cs_ai_abc123",
        "url": "https://arxiv.org/abs/2601.12345",
        "published": "2026-01-15",
        "snippet": "GPT-5 model, trained on the RedPajama dataset"
      }]
    },
    {
      "source": "GPT-5",
      "rel": "EVALUATED_ON",
      "target": "MMLU",
      "kind": "asserted",
      "confidence": 0.9,
      "evidence": [{
        "docId": "2026-01-15_arxiv_cs_ai_abc123",
        "url": "https://arxiv.org/abs/2601.12345",
        "published": "2026-01-15",
        "snippet": "achieves state-of-the-art performance on the MMLU benchmark"
      }]
    },
    {
      "source": "GPT-5",
      "rel": "REQUIRES",
      "target": "A100",
      "kind": "asserted",
      "confidence": 0.85,
      "evidence": [{
        "docId": "2026-01-15_arxiv_cs_ai_abc123",
        "url": "https://arxiv.org/abs/2601.12345",
        "published": "2026-01-15",
        "snippet": "requires 1024 A100 GPUs for training"
      }]
    },
    {
      "source": "Google DeepMind",
      "rel": "CREATED",
      "target": "Gemini Ultra",
      "kind": "inferred",
      "confidence": 0.8
    }
  ],
  "techTerms": ["transformer", "large language models", "constitutional AI"],
  "dates": [
    {"text": "2026-01-15", "start": "2026-01-15", "end": "2026-01-15"}
  ],
  "notes": ["Inferred Google DeepMind created Gemini Ultra based on context"]
}
```
"""


class TestEndToEndPipeline:
    """Test the complete pipeline from document to stored extraction."""

    def test_full_pipeline_with_mock_data(self, tmp_path: Path):
        """Test complete flow: doc → extract → validate → store."""
        # Step 1: Set up database
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Step 2: Simulate document ingestion (mock - no network)
        doc = SAMPLE_DOC.copy()
        doc_id = doc["docId"]

        # Store document record
        conn.execute(
            """
            INSERT INTO documents (doc_id, url, source, title, published_at,
                                   fetched_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                doc["url"],
                doc["source"],
                doc["title"],
                doc["published"],
                utc_now_iso(),
                "cleaned",
            ),
        )
        conn.commit()

        # Verify document stored
        cursor = conn.execute(
            "SELECT * FROM documents WHERE doc_id = ?", (doc_id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == doc_id

        # Step 3: Build extraction prompt
        prompt = build_extraction_prompt(doc)
        assert doc_id in prompt
        assert doc["title"] in prompt
        assert "OpenAI" in prompt  # From the text

        # Step 4: Parse LLM response (simulated)
        extraction = parse_extraction_response(
            SAMPLE_EXTRACTION_RESPONSE, doc_id
        )

        # Step 5: Validate extraction against schema
        validate_extraction(extraction)

        # Step 6: Save extraction to disk
        extractions_dir = tmp_path / "extractions"
        saved_path = save_extraction(extraction, extractions_dir)
        assert saved_path.exists()
        assert saved_path.name == f"{doc_id}.json"

        # Step 7: Load and verify extraction
        loaded = load_extraction(doc_id, extractions_dir)
        assert loaded is not None
        assert loaded["docId"] == doc_id
        assert len(loaded["entities"]) == 8
        assert len(loaded["relations"]) == 5

        # Step 8: Store entities in database
        today = utc_now_iso()[:10]
        for entity in extraction["entities"]:
            entity_id = entity.get("idHint") or f"entity:{slugify(entity['name'])}"
            insert_entity(
                conn,
                entity_id=entity_id,
                name=entity["name"],
                entity_type=entity["type"],
                aliases=entity.get("aliases"),
                first_seen=today,
                last_seen=today,
            )

        # Verify entities stored
        entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        assert entities == 8

        # Step 9: Store relations and evidence in database
        for rel_data in extraction["relations"]:
            source_entity = rel_data["source"]
            target_entity = rel_data["target"]

            # Find entity IDs (simplified - just use slugified names)
            source_id = f"entity:{slugify(source_entity)}"
            target_id = f"entity:{slugify(target_entity)}"

            relation_id = insert_relation(
                conn,
                source_id=source_id,
                rel=rel_data["rel"],
                target_id=target_id,
                kind=rel_data["kind"],
                confidence=rel_data["confidence"],
                doc_id=doc_id,
                extractor_version=EXTRACTOR_VERSION,
            )

            # Store evidence if present
            for evidence in rel_data.get("evidence", []):
                insert_evidence(
                    conn,
                    relation_id=relation_id,
                    doc_id=evidence["docId"],
                    url=evidence["url"],
                    published=evidence.get("published"),
                    snippet=evidence["snippet"],
                )

        # Verify relations stored
        relations_count = conn.execute(
            "SELECT COUNT(*) FROM relations"
        ).fetchone()[0]
        assert relations_count == 5

        # Verify evidence stored (only 4 relations have evidence)
        evidence_count = conn.execute(
            "SELECT COUNT(*) FROM evidence"
        ).fetchone()[0]
        assert evidence_count == 4

        # Step 10: Query back relations for an entity
        openai_rels = get_relations_for_entity(conn, "entity:openai")
        assert len(openai_rels) == 1
        assert openai_rels[0]["rel"] == "CREATED"
        assert openai_rels[0]["target_id"] == "entity:gpt_5"

        conn.close()

    def test_document_deduplication(self, tmp_path: Path):
        """Test that duplicate documents are handled correctly."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        doc_id = "2026-01-15_test_abc123"
        url = "https://example.com/article"

        # Insert first document
        conn.execute(
            """
            INSERT INTO documents (doc_id, url, source, title, fetched_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (doc_id, url, "Test", "First Title", utc_now_iso(), "fetched"),
        )
        conn.commit()

        # Try to insert duplicate with different title (should replace)
        conn.execute(
            """
            INSERT OR REPLACE INTO documents
            (doc_id, url, source, title, fetched_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (doc_id, url, "Test", "Updated Title", utc_now_iso(), "cleaned"),
        )
        conn.commit()

        # Verify only one document exists
        count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        assert count == 1

        # Verify title was updated
        row = conn.execute(
            "SELECT title FROM documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        assert row[0] == "Updated Title"

        conn.close()

    def test_entity_update_preserves_first_seen(self, tmp_path: Path):
        """Test that entity updates preserve first_seen date."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        entity_id = "org:test_org"

        # Insert entity with first_seen
        insert_entity(
            conn,
            entity_id=entity_id,
            name="Test Org",
            entity_type="Org",
            first_seen="2025-01-01",
            last_seen="2025-01-01",
        )

        # Update entity with new last_seen
        insert_entity(
            conn,
            entity_id=entity_id,
            name="Test Org",
            entity_type="Org",
            first_seen="2026-01-01",  # Should be ignored
            last_seen="2026-01-20",
        )

        # Verify first_seen preserved
        entity = get_entity(conn, entity_id)
        assert entity["first_seen"] == "2025-01-01"
        assert entity["last_seen"] == "2026-01-20"

        conn.close()


class TestUtilityFunctions:
    """Test utility functions used throughout the pipeline."""

    def test_doc_id_generation(self):
        """Test document ID generation components."""
        source = "arXiv CS.AI"
        url = "https://arxiv.org/abs/2601.12345"
        date = "2026-01-15"

        source_slug = slugify(source)
        url_hash = short_hash(url)

        doc_id = f"{date}_{source_slug}_{url_hash}"

        assert source_slug == "arxiv_cs_ai"
        assert len(url_hash) == 8
        assert doc_id.startswith("2026-01-15_arxiv_cs_ai_")

    def test_content_hash_consistency(self):
        """Test that content hashing is deterministic."""
        text = "This is sample article text."

        hash1 = sha256_text(text)
        hash2 = sha256_text(text)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex

    def test_html_cleaning(self):
        """Test HTML to text conversion."""
        html = """
        <html>
        <head><title>Test</title></head>
        <body>
        <p>First paragraph.</p>
        <p>Second paragraph.</p>
        <script>evil();</script>
        </body>
        </html>
        """

        text = clean_html(html)

        assert "First paragraph" in text
        assert "Second paragraph" in text
        assert "evil()" not in text
        assert "<p>" not in text


class TestConfigIntegration:
    """Test config loading integration."""

    def test_config_to_feed_list(self, tmp_path: Path):
        """Test loading feeds from YAML config."""
        config_path = tmp_path / "feeds.yaml"
        config_path.write_text(
            """
feeds:
  - name: "Test Feed 1"
    url: "https://example.com/feed1.xml"
    type: rss
    enabled: true
  - name: "Test Feed 2"
    url: "https://example.com/feed2.xml"
    type: rss
    enabled: true
  - name: "Disabled Feed"
    url: "https://example.com/disabled.xml"
    type: rss
    enabled: false
"""
        )

        feeds = load_feeds(config_path)

        assert len(feeds) == 2  # Only enabled feeds
        assert feeds[0].name == "Test Feed 1"
        assert feeds[1].name == "Test Feed 2"


class TestExtractionValidation:
    """Test extraction validation scenarios."""

    def test_valid_extraction_passes(self):
        """Test that a valid extraction passes validation."""
        extraction = {
            "docId": "test_doc_123",
            "extractorVersion": "1.0.0",
            "entities": [
                {"name": "OpenAI", "type": "Org"}
            ],
            "relations": [],
            "techTerms": ["AI"],
            "dates": [],
            "notes": [],
        }

        # Should not raise
        validate_extraction(extraction)

    def test_asserted_relation_requires_evidence(self):
        """Test that asserted relations require evidence."""
        extraction = {
            "docId": "test_doc_123",
            "extractorVersion": "1.0.0",
            "entities": [
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            "relations": [
                {
                    "source": "OpenAI",
                    "rel": "CREATED",
                    "target": "GPT-5",
                    "kind": "asserted",
                    "confidence": 0.9,
                    # Missing evidence!
                }
            ],
            "techTerms": [],
            "dates": [],
            "notes": [],
        }

        with pytest.raises(Exception) as exc_info:
            validate_extraction(extraction)

        assert "evidence" in str(exc_info.value).lower()

    def test_inferred_relation_without_evidence_ok(self):
        """Test that inferred relations don't require evidence."""
        extraction = {
            "docId": "test_doc_123",
            "extractorVersion": "1.0.0",
            "entities": [
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            "relations": [
                {
                    "source": "OpenAI",
                    "rel": "CREATED",
                    "target": "GPT-5",
                    "kind": "inferred",  # Inferred, so no evidence needed
                    "confidence": 0.7,
                }
            ],
            "techTerms": [],
            "dates": [],
            "notes": [],
        }

        # Should not raise
        validate_extraction(extraction)


@pytest.mark.network
class TestNetworkIntegration:
    """Integration tests that require network access.

    Run locally with: python scripts/run_network_tests.py
    """

    def test_real_feed_ingest_and_extract(self, tmp_path: Path):
        """Test ingesting a real feed and building extraction prompts."""
        import feedparser
        import requests

        # Fetch a real feed
        feed_url = "https://huggingface.co/blog/feed.xml"
        session = requests.Session()
        session.headers.update({"User-Agent": "predictor-ingest-test/0.1"})

        try:
            resp = session.get(feed_url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            pytest.skip(f"Network unavailable: {e}")

        feed = feedparser.parse(resp.text)

        if not feed.entries:
            pytest.skip("Feed has no entries")

        # Take first entry
        entry = feed.entries[0]
        title = entry.get("title", "Unknown")
        url = entry.get("link", "")
        summary = entry.get("summary", "")

        # Build a doc from the entry
        doc = {
            "docId": f"test_{short_hash(url)}",
            "url": url,
            "source": "Hugging Face Blog",
            "title": title,
            "published": utc_now_iso()[:10],
            "text": clean_html(summary) if summary else title,
        }

        # Build extraction prompt
        prompt = build_extraction_prompt(doc)

        assert doc["docId"] in prompt
        assert title in prompt
        assert len(prompt) > 100

        # Verify we can set up database
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Insert document
        conn.execute(
            """
            INSERT INTO documents (doc_id, url, source, title, fetched_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (doc["docId"], url, doc["source"], title, utc_now_iso(), "cleaned"),
        )
        conn.commit()

        # Verify stored
        count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        assert count == 1

        conn.close()


class TestFullPipeline:
    """Test the complete pipeline with all modules.

    Covers: ingest → clean → extract → resolve → graph → trend
    """

    # Sample raw HTML simulating fetched webpage
    SAMPLE_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Breakthrough - Tech News</title>
        <meta name="author" content="Jane Smith">
        <meta property="article:published_time" content="2026-01-20T10:00:00Z">
    </head>
    <body>
        <nav><a href="/">Home</a></nav>
        <article>
            <h1>OpenAI Releases GPT-5 with Major Improvements</h1>
            <p>OpenAI announced GPT-5, their latest language model built on
            transformer architecture. The model was trained on diverse datasets
            and evaluated on MMLU benchmark.</p>
            <p>Google DeepMind also released updates to their Gemini model,
            showing the competitive AI landscape.</p>
        </article>
        <footer>Copyright 2026</footer>
    </body>
    </html>
    """

    def test_complete_pipeline(self, tmp_path: Path):
        """Test the entire pipeline from raw HTML to trending export."""
        from clean import clean_document, extract_content
        from resolve import EntityResolver
        from graph import GraphExporter
        from trend import TrendScorer

        # === Step 1: Initialize database ===
        db_path = tmp_path / "pipeline.db"
        conn = init_db(db_path)

        # === Step 2: Clean HTML (simulating post-ingest) ===
        cleaned = clean_document(self.SAMPLE_HTML)

        assert cleaned["title"] == "OpenAI Releases GPT-5 with Major Improvements"
        assert cleaned["metadata"].get("author") == "Jane Smith"
        assert "OpenAI announced GPT-5" in cleaned["content"]
        assert "Copyright 2026" not in cleaned["content"]  # Boilerplate removed

        # === Step 3: Store document ===
        doc_id = "2026-01-20_technews_abc123"
        conn.execute(
            """
            INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (doc_id, "https://example.com/ai-news", "Tech News",
             cleaned["title"], "2026-01-20", utc_now_iso(), "cleaned"),
        )
        conn.commit()

        # === Step 4: Build extraction prompt ===
        doc = {
            "docId": doc_id,
            "url": "https://example.com/ai-news",
            "source": "Tech News",
            "title": cleaned["title"],
            "published": "2026-01-20",
            "text": cleaned["content"],
        }
        prompt = build_extraction_prompt(doc)
        assert "OpenAI" in prompt
        assert "GPT-5" in prompt

        # === Step 5: Simulate LLM extraction response ===
        extraction_json = """
        {
          "docId": "2026-01-20_technews_abc123",
          "extractorVersion": "1.0.0",
          "entities": [
            {"name": "OpenAI", "type": "Org"},
            {"name": "GPT-5", "type": "Model"},
            {"name": "Google DeepMind", "type": "Org"},
            {"name": "Gemini", "type": "Model"},
            {"name": "MMLU", "type": "Benchmark"},
            {"name": "Transformer", "type": "Tech"}
          ],
          "relations": [
            {"source": "OpenAI", "rel": "CREATED", "target": "GPT-5",
             "kind": "asserted", "confidence": 0.95,
             "evidence": [{"docId": "2026-01-20_technews_abc123",
                          "url": "https://example.com/ai-news",
                          "published": "2026-01-20",
                          "snippet": "OpenAI announced GPT-5"}]},
            {"source": "GPT-5", "rel": "USES_TECH", "target": "Transformer",
             "kind": "asserted", "confidence": 0.9,
             "evidence": [{"docId": "2026-01-20_technews_abc123",
                          "url": "https://example.com/ai-news",
                          "published": "2026-01-20",
                          "snippet": "built on transformer architecture"}]},
            {"source": "GPT-5", "rel": "EVALUATED_ON", "target": "MMLU",
             "kind": "asserted", "confidence": 0.85,
             "evidence": [{"docId": "2026-01-20_technews_abc123",
                          "url": "https://example.com/ai-news",
                          "published": "2026-01-20",
                          "snippet": "evaluated on MMLU benchmark"}]},
            {"source": "Google DeepMind", "rel": "CREATED", "target": "Gemini",
             "kind": "inferred", "confidence": 0.7}
          ],
          "techTerms": ["transformer", "language model"],
          "dates": [],
          "notes": []
        }
        """

        extraction = parse_extraction_response(extraction_json, doc_id)
        validate_extraction(extraction)

        # === Step 6: Resolve entities ===
        resolver = EntityResolver(conn, threshold=0.85)
        resolved_ids = resolver.resolve_extraction(extraction)

        assert len(resolved_ids) == 6
        assert resolved_ids["OpenAI"].startswith("org:")
        assert resolved_ids["GPT-5"].startswith("model:")

        # === Step 7: Store relations with resolved IDs ===
        for rel in extraction["relations"]:
            source_id = resolved_ids[rel["source"]]
            target_id = resolved_ids[rel["target"]]

            insert_relation(
                conn,
                source_id=source_id,
                rel=rel["rel"],
                target_id=target_id,
                kind=rel["kind"],
                confidence=rel["confidence"],
                doc_id=doc_id,
                extractor_version="1.0.0",
            )

            # Store evidence if present
            for ev in rel.get("evidence", []):
                # Get relation_id
                cursor = conn.execute(
                    "SELECT MAX(relation_id) FROM relations"
                )
                rel_id = cursor.fetchone()[0]
                insert_evidence(conn, rel_id, ev["docId"], ev["url"],
                              ev.get("published"), ev["snippet"])

        # Add MENTIONS edges (doc → entity)
        for name, entity_id in resolved_ids.items():
            insert_relation(
                conn,
                source_id=f"doc:{doc_id}",
                rel="MENTIONS",
                target_id=entity_id,
                kind="asserted",
                confidence=1.0,
                doc_id=doc_id,
                extractor_version="1.0.0",
            )

        # === Step 8: Export graph ===
        exporter = GraphExporter(conn)

        # Claims view
        claims = exporter.export_claims()
        assert len(claims["elements"]["nodes"]) >= 4
        assert len(claims["elements"]["edges"]) >= 3

        # Mentions view
        mentions = exporter.export_mentions()
        assert any(e["data"]["rel"] == "MENTIONS"
                  for e in mentions["elements"]["edges"])

        # Dependencies view
        deps = exporter.export_dependencies()
        dep_rels = {e["data"]["rel"] for e in deps["elements"]["edges"]}
        assert "USES_TECH" in dep_rels or "EVALUATED_ON" in dep_rels

        # Export to files
        output_dir = tmp_path / "graphs" / "2026-01-20"
        exporter.export_all_views(output_dir)
        assert (output_dir / "claims.json").exists()
        assert (output_dir / "mentions.json").exists()
        assert (output_dir / "dependencies.json").exists()

        # === Step 9: Compute trends ===
        scorer = TrendScorer(conn)

        # Score individual entity
        gpt5_id = resolved_ids["GPT-5"]
        scores = scorer.score_entity(gpt5_id)
        assert scores["mention_count_7d"] >= 0
        assert "velocity" in scores
        assert "novelty" in scores

        # Get trending
        trending = scorer.get_trending(limit=10)
        assert len(trending) >= 1

        # Export trending
        scorer.export_trending(output_dir, limit=10)
        assert (output_dir / "trending.json").exists()

        # === Step 10: Verify final state ===
        entity_count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        relation_count = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        evidence_count = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]

        assert entity_count == 6
        assert relation_count >= 10  # 4 semantic + 6 MENTIONS
        assert evidence_count >= 3

        conn.close()

        # === Verify output files ===
        with open(output_dir / "claims.json") as f:
            claims_data = json.load(f)
        assert "elements" in claims_data

        with open(output_dir / "trending.json") as f:
            trending_data = json.load(f)
        assert "entities" in trending_data

        print(f"\n✓ Full pipeline test passed!")
        print(f"  - Entities: {entity_count}")
        print(f"  - Relations: {relation_count}")
        print(f"  - Evidence: {evidence_count}")
        print(f"  - Graph files: claims.json, mentions.json, dependencies.json")
        print(f"  - Trending: {len(trending_data['entities'])} entities")
