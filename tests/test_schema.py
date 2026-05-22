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

    def test_movers_schema_exists(self):
        """Schema file should exist at schemas/movers.json."""
        schema_path = Path(__file__).parent.parent / "schemas" / "movers.json"
        assert schema_path.exists(), f"Schema not found at {schema_path}"

    def test_movers_schema_valid_json(self):
        """Movers schema should be valid JSON with the expected structure."""
        import json
        schema_path = Path(__file__).parent.parent / "schemas" / "movers.json"
        with open(schema_path) as f:
            schema = json.load(f)
        assert schema.get("$schema", "").startswith("https://json-schema.org/")
        assert schema["title"] == "Movers Export"
        # Top-level requires meta + rows
        assert set(schema["required"]) == {"meta", "rows"}
        # row $def has the 15 fields from Appendix A
        row_required = set(schema["$defs"]["row"]["required"])
        expected_row_fields = {
            "entity_id", "label", "type",
            "current_rank", "rank_prior", "rank_delta", "is_new",
            "velocity_raw", "mention_count_7d", "mention_count_30d",
            "first_seen", "days_since_first_seen",
            "distinct_sources_7d", "in_trending_view", "trend_score",
        }
        assert row_required == expected_row_fields

    def test_movers_schema_validates_example(self):
        """A canonical Movers example should validate against the schema."""
        import json
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = Path(__file__).parent.parent / "schemas" / "movers.json"
        with open(schema_path) as f:
            schema = json.load(f)
        Draft202012Validator.check_schema(schema)

        example = {
            "meta": {
                "view": "movers",
                "domain": "ai",
                "rank_window_days": 7,
                "rowCount": 2,
                "exportedAt": "2026-05-10T20:30:00Z",
                "dateRange": {"start": "2026-03-15", "end": "2026-05-10"},
                "scoring": {
                    "novelty_decay_lambda": 0.05,
                    "min_mentions_for_velocity": 3,
                },
            },
            "rows": [
                {
                    "entity_id": "org:rivian",
                    "label": "Rivian",
                    "type": "Org",
                    "current_rank": 75,
                    "rank_prior": 140,
                    "rank_delta": 65,
                    "is_new": False,
                    "velocity_raw": 8.5,
                    "mention_count_7d": 17,
                    "mention_count_30d": 42,
                    "first_seen": "2026-03-15",
                    "days_since_first_seen": 56,
                    "distinct_sources_7d": 5,
                    "in_trending_view": False,
                    "trend_score": 0.412,
                },
                {
                    "entity_id": "tech:retentive_attention",
                    "label": "Retentive Attention",
                    "type": "Tech",
                    "current_rank": 88,
                    "rank_prior": None,
                    "rank_delta": None,
                    "is_new": True,
                    "velocity_raw": None,
                    "mention_count_7d": 4,
                    "mention_count_30d": 4,
                    "first_seen": "2026-05-06",
                    "days_since_first_seen": 4,
                    "distinct_sources_7d": 3,
                    "in_trending_view": False,
                    "trend_score": 0.218,
                },
            ],
        }
        v = Draft202012Validator(schema)
        errors = sorted(v.iter_errors(example), key=lambda e: e.path)
        assert not errors, "\n".join(e.message for e in errors)

    def test_movers_schema_rejects_missing_required(self):
        """Schema should reject a row missing a required field."""
        import json
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = Path(__file__).parent.parent / "schemas" / "movers.json"
        with open(schema_path) as f:
            schema = json.load(f)
        v = Draft202012Validator(schema)

        # Row missing is_new (a required field)
        bad = {
            "meta": {
                "view": "movers", "domain": "ai", "rank_window_days": 7,
                "rowCount": 1,
                "exportedAt": "2026-05-10T20:30:00Z",
                "dateRange": {"start": "2026-05-10", "end": "2026-05-10"},
                "scoring": {"novelty_decay_lambda": 0.05,
                            "min_mentions_for_velocity": 3},
            },
            "rows": [{
                "entity_id": "org:x", "label": "X", "type": "Org",
                "current_rank": 1, "rank_prior": None, "rank_delta": None,
                # is_new missing
                "velocity_raw": None,
                "mention_count_7d": 0, "mention_count_30d": 0,
                "first_seen": "2026-05-10", "days_since_first_seen": 0,
                "distinct_sources_7d": 0, "in_trending_view": False,
                "trend_score": 0.0,
            }],
        }
        errors = list(v.iter_errors(bad))
        assert errors, "Expected validation error for missing is_new"

    def test_movers_schema_accepts_domain_specific_entity_types(self):
        """entityType is an open string: domain-specific types like 'Company',
        'Chip', 'Fab', 'SelectAgent', 'Production' must pass validation. The
        framework V1 enum is a default; each domain extends it."""
        import json
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = Path(__file__).parent.parent / "schemas" / "movers.json"
        with open(schema_path) as f:
            schema = json.load(f)
        v = Draft202012Validator(schema)

        def _row(entity_type):
            return {
                "meta": {
                    "view": "movers", "domain": "semiconductors",
                    "rank_window_days": 7, "rowCount": 1,
                    "exportedAt": "2026-05-10T20:30:00Z",
                    "dateRange": {"start": "2026-05-10", "end": "2026-05-10"},
                    "scoring": {"novelty_decay_lambda": 0.05,
                                "min_mentions_for_velocity": 3},
                },
                "rows": [{
                    "entity_id": "z:x", "label": "X",
                    "type": entity_type,
                    "current_rank": 1, "rank_prior": None, "rank_delta": None,
                    "is_new": True, "velocity_raw": None,
                    "mention_count_7d": 0, "mention_count_30d": 0,
                    "first_seen": "2026-05-10", "days_since_first_seen": 0,
                    "distinct_sources_7d": 0, "in_trending_view": False,
                    "trend_score": 0.0,
                }],
            }

        for t in ("Company", "Chip", "Fab", "ProcessNode", "SelectAgent",
                  "Production", "Festival", "Org"):
            assert not list(v.iter_errors(_row(t))), (
                f"Expected {t!r} to validate as an entity type"
            )

    def test_movers_schema_rejects_structurally_invalid_entity_type(self):
        """entityType still rejects non-strings and empty strings."""
        import json
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = Path(__file__).parent.parent / "schemas" / "movers.json"
        with open(schema_path) as f:
            schema = json.load(f)
        v = Draft202012Validator(schema)

        def _row(entity_type):
            return {
                "meta": {
                    "view": "movers", "domain": "ai", "rank_window_days": 7,
                    "rowCount": 1,
                    "exportedAt": "2026-05-10T20:30:00Z",
                    "dateRange": {"start": "2026-05-10", "end": "2026-05-10"},
                    "scoring": {"novelty_decay_lambda": 0.05,
                                "min_mentions_for_velocity": 3},
                },
                "rows": [{
                    "entity_id": "z:x", "label": "X",
                    "type": entity_type,
                    "current_rank": 1, "rank_prior": None, "rank_delta": None,
                    "is_new": True, "velocity_raw": None,
                    "mention_count_7d": 0, "mention_count_30d": 0,
                    "first_seen": "2026-05-10", "days_since_first_seen": 0,
                    "distinct_sources_7d": 0, "in_trending_view": False,
                    "trend_score": 0.0,
                }],
            }

        for bad_value in ("", 42, None, ["Org"]):
            assert list(v.iter_errors(_row(bad_value))), (
                f"Expected validation error for entity type {bad_value!r}"
            )
