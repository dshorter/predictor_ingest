"""Tests for extraction module.

Tests written BEFORE implementation (TDD).
Based on AGENTS.md extraction specification.
"""

import json
import pytest
from pathlib import Path

from extract import (
    build_extraction_prompt,
    parse_extraction_response,
    save_extraction,
    load_extraction,
    import_manual_extraction,
    ExtractionError,
)


class TestBuildExtractionPrompt:
    """Test prompt building for LLM extraction."""

    def test_builds_prompt_with_document(self):
        """Should build prompt containing document text."""
        doc = {
            "docId": "2025-12-01_arxiv_abc123",
            "title": "New AI Model Released",
            "text": "OpenAI announced GPT-5 today...",
            "url": "https://example.com/article",
            "published": "2025-12-01",
        }
        prompt = build_extraction_prompt(doc)

        assert "GPT-5" in prompt
        assert "OpenAI" in prompt
        assert "2025-12-01_arxiv_abc123" in prompt

    def test_prompt_includes_schema_instructions(self):
        """Should include extraction schema in prompt."""
        doc = {
            "docId": "doc1",
            "title": "Test",
            "text": "Some text",
            "url": "https://example.com",
            "published": "2025-01-01",
        }
        prompt = build_extraction_prompt(doc)

        # Should mention key schema elements
        assert "entities" in prompt.lower()
        assert "relations" in prompt.lower()
        assert "evidence" in prompt.lower()

    def test_prompt_includes_entity_types(self):
        """Should list valid entity types."""
        doc = {"docId": "d", "title": "t", "text": "x", "url": "u", "published": "p"}
        prompt = build_extraction_prompt(doc)

        assert "Org" in prompt
        assert "Person" in prompt
        assert "Model" in prompt

    def test_prompt_includes_relation_types(self):
        """Should list valid relation types."""
        doc = {"docId": "d", "title": "t", "text": "x", "url": "u", "published": "p"}
        prompt = build_extraction_prompt(doc)

        assert "CREATED" in prompt
        assert "MENTIONS" in prompt
        assert "USES_TECH" in prompt


class TestParseExtractionResponse:
    """Test parsing LLM responses."""

    def test_parses_valid_json(self):
        """Should parse valid JSON response."""
        response = json.dumps({
            "docId": "doc1",
            "extractorVersion": "1.0.0",
            "entities": [{"name": "OpenAI", "type": "Org"}],
            "relations": [],
            "techTerms": ["transformer"],
            "dates": [],
        })

        result = parse_extraction_response(response, doc_id="doc1")
        assert result["docId"] == "doc1"
        assert len(result["entities"]) == 1

    def test_extracts_json_from_markdown_code_block(self):
        """Should extract JSON from markdown code blocks."""
        response = """Here's the extraction:

```json
{
    "docId": "doc1",
    "extractorVersion": "1.0.0",
    "entities": [],
    "relations": [],
    "techTerms": [],
    "dates": []
}
```

I extracted the entities above."""

        result = parse_extraction_response(response, doc_id="doc1")
        assert result["docId"] == "doc1"

    def test_injects_doc_id_if_missing(self):
        """Should inject docId if not in response."""
        response = json.dumps({
            "extractorVersion": "1.0.0",
            "entities": [],
            "relations": [],
            "techTerms": [],
            "dates": [],
        })

        result = parse_extraction_response(response, doc_id="injected_doc_id")
        assert result["docId"] == "injected_doc_id"

    def test_raises_on_invalid_json(self):
        """Should raise ExtractionError for invalid JSON."""
        response = "This is not valid JSON at all"

        with pytest.raises(ExtractionError, match="Failed to parse"):
            parse_extraction_response(response, doc_id="doc1")

    def test_validates_against_schema(self):
        """Should validate parsed result against schema."""
        response = json.dumps({
            "docId": "doc1",
            "extractorVersion": "1.0.0",
            "entities": [{"name": "Test"}],  # Missing required 'type'
            "relations": [],
            "techTerms": [],
            "dates": [],
        })

        with pytest.raises(ExtractionError, match="type"):
            parse_extraction_response(response, doc_id="doc1")


class TestSaveAndLoadExtraction:
    """Test saving and loading extractions."""

    def test_save_extraction(self, tmp_path):
        """Should save extraction to JSON file."""
        extraction = {
            "docId": "2025-12-01_test_abc",
            "extractorVersion": "1.0.0",
            "entities": [{"name": "OpenAI", "type": "Org"}],
            "relations": [],
            "techTerms": [],
            "dates": [],
        }

        save_extraction(extraction, tmp_path)

        expected_path = tmp_path / "2025-12-01_test_abc.json"
        assert expected_path.exists()

    def test_load_extraction(self, tmp_path):
        """Should load extraction from JSON file."""
        extraction = {
            "docId": "doc123",
            "extractorVersion": "1.0.0",
            "entities": [],
            "relations": [],
            "techTerms": ["AI"],
            "dates": [],
        }

        # Save first
        save_extraction(extraction, tmp_path)

        # Load back
        loaded = load_extraction("doc123", tmp_path)
        assert loaded["docId"] == "doc123"
        assert loaded["techTerms"] == ["AI"]

    def test_load_nonexistent_extraction(self, tmp_path):
        """Should return None for nonexistent extraction."""
        loaded = load_extraction("nonexistent", tmp_path)
        assert loaded is None


class TestImportManualExtraction:
    """Test importing manual extractions (Mode B)."""

    def test_import_valid_extraction(self, tmp_path):
        """Should import and validate manual extraction."""
        extraction = {
            "docId": "manual_doc",
            "extractorVersion": "manual-1.0",
            "entities": [
                {"name": "Anthropic", "type": "Org"},
                {"name": "Claude", "type": "Model"},
            ],
            "relations": [
                {
                    "source": "Anthropic",
                    "rel": "CREATED",
                    "target": "Claude",
                    "kind": "asserted",
                    "confidence": 0.95,
                    "evidence": [{
                        "docId": "manual_doc",
                        "url": "https://anthropic.com",
                        "published": "2025-01-01",
                        "snippet": "Anthropic created Claude...",
                    }],
                }
            ],
            "techTerms": ["constitutional AI"],
            "dates": [],
        }

        # Write to file
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(extraction))

        # Import
        output_dir = tmp_path / "extractions"
        output_dir.mkdir()
        result = import_manual_extraction(input_file, output_dir)

        assert result["docId"] == "manual_doc"
        assert (output_dir / "manual_doc.json").exists()

    def test_import_rejects_invalid_extraction(self, tmp_path):
        """Should reject invalid extraction with clear error."""
        extraction = {
            "docId": "bad_doc",
            "extractorVersion": "1.0",
            "entities": [{"name": "Missing type field"}],  # Invalid
            "relations": [],
            "techTerms": [],
            "dates": [],
        }

        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(extraction))

        output_dir = tmp_path / "extractions"
        output_dir.mkdir()

        with pytest.raises(ExtractionError, match="type"):
            import_manual_extraction(input_file, output_dir)


class TestExtractionVersioning:
    """Test extractor versioning."""

    def test_default_extractor_version(self):
        """Build prompt should include extractor version."""
        doc = {"docId": "d", "title": "t", "text": "x", "url": "u", "published": "p"}
        prompt = build_extraction_prompt(doc, extractor_version="2.0.0")

        assert "2.0.0" in prompt
