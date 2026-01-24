"""Tests for JSON schema validation of extraction output.

Tests written BEFORE implementation (TDD).
Based on AGENTS.md extraction output specification.
"""

import pytest
from pathlib import Path

from schema import (
    validate_extraction,
    validate_entity,
    validate_relation,
    validate_evidence,
    ValidationError,
)


class TestValidateExtraction:
    """Test validation of complete extraction output."""

    def test_valid_minimal_extraction(self):
        """Should accept minimal valid extraction."""
        extraction = {
            "docId": "2025-12-01_arxiv_abc123",
            "extractorVersion": "1.0.0",
            "entities": [],
            "relations": [],
            "techTerms": [],
            "dates": [],
        }
        # Should not raise
        validate_extraction(extraction)

    def test_valid_full_extraction(self):
        """Should accept complete valid extraction."""
        extraction = {
            "docId": "2025-12-01_arxiv_abc123",
            "extractorVersion": "1.0.0",
            "entities": [
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-4", "type": "Model"},
            ],
            "relations": [
                {
                    "source": "OpenAI",
                    "rel": "CREATED",
                    "target": "GPT-4",
                    "kind": "asserted",
                    "confidence": 0.95,
                    "evidence": [
                        {
                            "docId": "2025-12-01_arxiv_abc123",
                            "url": "https://example.com",
                            "published": "2025-12-01",
                            "snippet": "OpenAI announced GPT-4...",
                        }
                    ],
                }
            ],
            "techTerms": ["transformer", "attention"],
            "dates": [
                {"text": "December 2025", "start": "2025-12-01", "end": "2025-12-31"}
            ],
            "notes": ["Some ambiguity in entity resolution"],
        }
        validate_extraction(extraction)

    def test_missing_required_field(self):
        """Should reject extraction missing required fields."""
        extraction = {
            "docId": "2025-12-01_arxiv_abc123",
            # missing extractorVersion
            "entities": [],
            "relations": [],
            "techTerms": [],
            "dates": [],
        }
        with pytest.raises(ValidationError, match="extractorVersion"):
            validate_extraction(extraction)

    def test_invalid_docid_type(self):
        """Should reject non-string docId."""
        extraction = {
            "docId": 12345,  # should be string
            "extractorVersion": "1.0.0",
            "entities": [],
            "relations": [],
            "techTerms": [],
            "dates": [],
        }
        with pytest.raises(ValidationError, match="docId"):
            validate_extraction(extraction)


class TestValidateEntity:
    """Test validation of entity objects."""

    def test_valid_minimal_entity(self):
        """Should accept entity with only required fields."""
        entity = {"name": "OpenAI", "type": "Org"}
        validate_entity(entity)

    def test_valid_full_entity(self):
        """Should accept entity with all fields."""
        entity = {
            "name": "OpenAI",
            "type": "Org",
            "aliases": ["Open AI", "OpenAI Inc"],
            "externalIds": {"wikidata": "Q123456"},
            "idHint": "org:openai",
        }
        validate_entity(entity)

    def test_missing_name(self):
        """Should reject entity without name."""
        entity = {"type": "Org"}
        with pytest.raises(ValidationError, match="name"):
            validate_entity(entity)

    def test_missing_type(self):
        """Should reject entity without type."""
        entity = {"name": "OpenAI"}
        with pytest.raises(ValidationError, match="type"):
            validate_entity(entity)

    def test_invalid_entity_type(self):
        """Should reject entity with invalid type enum."""
        entity = {"name": "OpenAI", "type": "InvalidType"}
        with pytest.raises(ValidationError, match="type"):
            validate_entity(entity)

    def test_valid_entity_types(self):
        """Should accept all valid entity types from AGENTS.md."""
        valid_types = [
            "Org", "Person", "Program", "Tool", "Model", "Dataset",
            "Benchmark", "Paper", "Repo", "Document", "Tech", "Topic",
            "Event", "Location", "Other",
        ]
        for entity_type in valid_types:
            entity = {"name": "Test", "type": entity_type}
            validate_entity(entity)  # Should not raise


class TestValidateRelation:
    """Test validation of relation objects."""

    def test_valid_minimal_relation(self):
        """Should accept relation with required fields."""
        relation = {
            "source": "OpenAI",
            "rel": "CREATED",
            "target": "GPT-4",
            "kind": "asserted",
            "confidence": 0.9,
            "evidence": [
                {
                    "docId": "doc123",
                    "url": "https://example.com",
                    "published": "2025-12-01",
                    "snippet": "Evidence text",
                }
            ],
        }
        validate_relation(relation)

    def test_valid_full_relation(self):
        """Should accept relation with all optional fields."""
        relation = {
            "source": "OpenAI",
            "rel": "CREATED",
            "target": "GPT-4",
            "kind": "asserted",
            "confidence": 0.9,
            "verbRaw": "created",
            "polarity": "pos",
            "modality": "observed",
            "time": {"text": "2023", "start": "2023-01-01", "end": "2023-12-31"},
            "evidence": [
                {
                    "docId": "doc123",
                    "url": "https://example.com",
                    "published": "2025-12-01",
                    "snippet": "Evidence text",
                }
            ],
        }
        validate_relation(relation)

    def test_missing_source(self):
        """Should reject relation without source."""
        relation = {
            "rel": "CREATED",
            "target": "GPT-4",
            "kind": "asserted",
            "confidence": 0.9,
            "evidence": [],
        }
        with pytest.raises(ValidationError, match="source"):
            validate_relation(relation)

    def test_invalid_kind(self):
        """Should reject relation with invalid kind."""
        relation = {
            "source": "OpenAI",
            "rel": "CREATED",
            "target": "GPT-4",
            "kind": "invalid_kind",
            "confidence": 0.9,
            "evidence": [],
        }
        with pytest.raises(ValidationError, match="kind"):
            validate_relation(relation)

    def test_valid_kinds(self):
        """Should accept all valid kind values."""
        for kind in ["asserted", "inferred", "hypothesis"]:
            relation = {
                "source": "A",
                "rel": "MENTIONS",
                "target": "B",
                "kind": kind,
                "confidence": 0.5,
                "evidence": [] if kind != "asserted" else [
                    {"docId": "d", "url": "u", "published": None, "snippet": "s"}
                ],
            }
            validate_relation(relation)

    def test_confidence_range(self):
        """Should reject confidence outside 0-1 range."""
        relation = {
            "source": "A",
            "rel": "MENTIONS",
            "target": "B",
            "kind": "inferred",
            "confidence": 1.5,  # Invalid: > 1
            "evidence": [],
        }
        with pytest.raises(ValidationError, match="confidence"):
            validate_relation(relation)

    def test_asserted_requires_evidence(self):
        """Asserted relations MUST have non-empty evidence."""
        relation = {
            "source": "OpenAI",
            "rel": "CREATED",
            "target": "GPT-4",
            "kind": "asserted",
            "confidence": 0.9,
            "evidence": [],  # Empty - should fail for asserted
        }
        with pytest.raises(ValidationError, match="evidence"):
            validate_relation(relation)

    def test_valid_relation_types(self):
        """Should accept valid relation types from AGENTS.md."""
        valid_rels = [
            "MENTIONS", "CITES", "ANNOUNCES", "REPORTED_BY",
            "LAUNCHED", "PUBLISHED", "UPDATED", "FUNDED", "PARTNERED_WITH",
            "ACQUIRED", "HIRED", "CREATED", "OPERATES", "GOVERNED_BY",
            "GOVERNS", "REGULATES", "COMPLIES_WITH",
            "USES_TECH", "USES_MODEL", "USES_DATASET", "TRAINED_ON",
            "EVALUATED_ON", "INTEGRATES_WITH", "DEPENDS_ON", "REQUIRES",
            "PRODUCES", "MEASURES", "AFFECTS",
            "PREDICTS", "DETECTS", "MONITORS",
        ]
        for rel in valid_rels:
            relation = {
                "source": "A",
                "rel": rel,
                "target": "B",
                "kind": "inferred",
                "confidence": 0.5,
                "evidence": [],
            }
            validate_relation(relation)


class TestValidateEvidence:
    """Test validation of evidence objects."""

    def test_valid_minimal_evidence(self):
        """Should accept evidence with required fields."""
        evidence = {
            "docId": "doc123",
            "url": "https://example.com/article",
            "published": "2025-12-01",
            "snippet": "The relevant quote from the document.",
        }
        validate_evidence(evidence)

    def test_valid_full_evidence(self):
        """Should accept evidence with optional charSpan."""
        evidence = {
            "docId": "doc123",
            "url": "https://example.com/article",
            "published": "2025-12-01",
            "snippet": "The relevant quote.",
            "charSpan": {"start": 100, "end": 150},
        }
        validate_evidence(evidence)

    def test_null_published_allowed(self):
        """Should accept null published date."""
        evidence = {
            "docId": "doc123",
            "url": "https://example.com/article",
            "published": None,
            "snippet": "Quote without known date.",
        }
        validate_evidence(evidence)

    def test_missing_snippet(self):
        """Should reject evidence without snippet."""
        evidence = {
            "docId": "doc123",
            "url": "https://example.com/article",
            "published": "2025-12-01",
        }
        with pytest.raises(ValidationError, match="snippet"):
            validate_evidence(evidence)


class TestSchemaFiles:
    """Test that schema files exist and are valid JSON Schema."""

    def test_extraction_schema_exists(self):
        """Schema file should exist at schemas/extraction.json."""
        schema_path = Path(__file__).parent.parent / "schemas" / "extraction.json"
        assert schema_path.exists(), f"Schema not found at {schema_path}"

    def test_extraction_schema_valid_json(self):
        """Schema should be valid JSON."""
        import json
        schema_path = Path(__file__).parent.parent / "schemas" / "extraction.json"
        with open(schema_path) as f:
            schema = json.load(f)
        assert "$schema" in schema
        assert "properties" in schema
