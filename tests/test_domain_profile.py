"""Tests for domain profile JSON Schema validation.

Validates that schemas/domain-profile.json is correct and that
valid/invalid domain profiles are properly accepted/rejected.
"""

import json
import copy
import pytest
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "domain-profile.json"

# Minimal valid domain profile matching the schema
VALID_PROFILE = {
    "domain": {
        "name": "AI and Machine Learning",
        "slug": "ai",
        "description": "Artificial intelligence and machine learning trends",
    },
    "entity_types": [
        "Org", "Person", "Model", "Tool", "Dataset", "Tech", "Other",
    ],
    "relation_taxonomy": {
        "canonical": [
            "MENTIONS", "CREATED", "USES_TECH", "TRAINED_ON", "DEPENDS_ON",
        ],
        "normalization": {
            "ANNOUNCED": "MENTIONS",
            "BUILT": "CREATED",
            "USED": "USES_TECH",
        },
    },
    "id_prefixes": {
        "Org": "org",
        "Person": "person",
        "Model": "model",
        "Tool": "tool",
        "Dataset": "dataset",
        "Tech": "tech",
        "Other": "other",
    },
    "base_relation": "MENTIONS",
    "quality_thresholds": {
        "entity_density_target": 5.0,
        "evidence_coverage_min": 0.8,
        "avg_confidence_target": 0.85,
        "relation_entity_ratio_target": 0.5,
        "tech_terms_min": 2,
        "relation_type_diversity_target": 6,
    },
    "gate_thresholds": {
        "evidence_fidelity_min": 0.70,
        "orphan_max": 0.0,
        "zero_value_min_entities": 1,
        "zero_value_min_doc_chars": 500,
    },
    "scoring_weights": {
        "density": 0.15,
        "evidence": 0.15,
        "confidence": 0.10,
        "connectivity": 0.20,
        "diversity": 0.25,
        "tech_terms": 0.15,
    },
    "trend_weights": {
        "velocity": 0.4,
        "novelty": 0.3,
        "activity": 0.3,
    },
    "suppressed_entities": ["AI", "machine learning", "technology"],
    "prompts": {
        "dir": "prompts",
    },
}


@pytest.fixture
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


@pytest.fixture
def validator(schema):
    from jsonschema import Draft202012Validator
    return Draft202012Validator(schema)


@pytest.fixture
def valid_profile():
    return copy.deepcopy(VALID_PROFILE)


class TestDomainProfileSchemaFile:
    """Test that the schema file itself is valid."""

    def test_schema_file_exists(self):
        assert SCHEMA_PATH.exists(), f"Schema not found at {SCHEMA_PATH}"

    def test_schema_is_valid_json(self):
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        assert "$schema" in schema
        assert schema["type"] == "object"

    def test_schema_is_valid_json_schema(self):
        from jsonschema import Draft202012Validator
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        Draft202012Validator.check_schema(schema)


class TestValidProfile:
    """Test that valid profiles pass validation."""

    def test_minimal_valid_profile(self, validator, valid_profile):
        validator.validate(valid_profile)

    def test_profile_with_optional_fields(self, validator, valid_profile):
        valid_profile["escalation_threshold"] = 0.6
        valid_profile["relation_kinds"] = ["asserted", "inferred", "hypothesis"]
        valid_profile["polarity_values"] = ["pos", "neg", "unclear"]
        valid_profile["modality_values"] = ["observed", "planned", "speculative"]
        valid_profile["gate_thresholds"]["high_confidence_threshold"] = 0.8
        valid_profile["trend_weights"]["velocity_cap"] = 5.0
        valid_profile["trend_weights"]["activity_cap"] = 20
        valid_profile["trend_weights"]["max_age_days"] = 365
        valid_profile["trend_weights"]["novelty_age_weight"] = 0.6
        valid_profile["trend_weights"]["novelty_rarity_weight"] = 0.4
        valid_profile["prompts"]["system_prompt"] = "system.txt"
        valid_profile["prompts"]["user_prompt"] = "user.txt"
        validator.validate(valid_profile)

    def test_profile_with_relation_groups(self, validator, valid_profile):
        valid_profile["relation_taxonomy"]["groups"] = {
            "document": ["MENTIONS"],
            "creation": ["CREATED"],
            "technical": ["USES_TECH", "TRAINED_ON", "DEPENDS_ON"],
        }
        validator.validate(valid_profile)

    def test_profile_with_views(self, validator, valid_profile):
        valid_profile["views"] = {
            "mentions": {
                "description": "Document mentions",
                "relations": ["MENTIONS"],
            },
            "claims": {
                "description": "Semantic claims",
                "relations": [],
            },
        }
        validator.validate(valid_profile)


class TestRequiredFields:
    """Test that missing required fields are rejected."""

    REQUIRED_TOP_LEVEL = [
        "domain", "entity_types", "relation_taxonomy", "id_prefixes",
        "base_relation", "quality_thresholds", "gate_thresholds",
        "scoring_weights", "trend_weights", "suppressed_entities", "prompts",
    ]

    @pytest.mark.parametrize("field", REQUIRED_TOP_LEVEL)
    def test_missing_top_level_field(self, validator, valid_profile, field):
        del valid_profile[field]
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, f"Should reject profile missing '{field}'"

    def test_missing_domain_name(self, validator, valid_profile):
        del valid_profile["domain"]["name"]
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0

    def test_missing_domain_slug(self, validator, valid_profile):
        del valid_profile["domain"]["slug"]
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0

    def test_missing_quality_threshold_field(self, validator, valid_profile):
        del valid_profile["quality_thresholds"]["entity_density_target"]
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0

    def test_missing_gate_threshold_field(self, validator, valid_profile):
        del valid_profile["gate_thresholds"]["evidence_fidelity_min"]
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0

    def test_missing_scoring_weight_field(self, validator, valid_profile):
        del valid_profile["scoring_weights"]["density"]
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0

    def test_missing_trend_weight_field(self, validator, valid_profile):
        del valid_profile["trend_weights"]["velocity"]
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0

    def test_missing_prompts_dir(self, validator, valid_profile):
        del valid_profile["prompts"]["dir"]
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0


class TestInvalidValues:
    """Test that invalid values are rejected."""

    def test_invalid_domain_slug_uppercase(self, validator, valid_profile):
        valid_profile["domain"]["slug"] = "AI"
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Slug must be lowercase"

    def test_invalid_domain_slug_spaces(self, validator, valid_profile):
        valid_profile["domain"]["slug"] = "a i"
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Slug must not contain spaces"

    def test_invalid_entity_type_lowercase(self, validator, valid_profile):
        valid_profile["entity_types"] = ["org"]
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Entity types must be PascalCase"

    def test_entity_types_must_be_unique(self, validator, valid_profile):
        valid_profile["entity_types"] = ["Org", "Org", "Model"]
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Entity types must be unique"

    def test_entity_types_cannot_be_empty(self, validator, valid_profile):
        valid_profile["entity_types"] = []
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Must have at least one entity type"

    def test_invalid_canonical_relation_lowercase(self, validator, valid_profile):
        valid_profile["relation_taxonomy"]["canonical"] = ["mentions"]
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Canonical relations must be UPPER_SNAKE_CASE"

    def test_invalid_base_relation_lowercase(self, validator, valid_profile):
        valid_profile["base_relation"] = "mentions"
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Base relation must be UPPER_SNAKE_CASE"

    def test_invalid_id_prefix_uppercase(self, validator, valid_profile):
        valid_profile["id_prefixes"]["Org"] = "ORG"
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "ID prefixes must be lowercase"

    def test_evidence_fidelity_out_of_range(self, validator, valid_profile):
        valid_profile["gate_thresholds"]["evidence_fidelity_min"] = 1.5
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Evidence fidelity must be <= 1.0"

    def test_scoring_weight_negative(self, validator, valid_profile):
        valid_profile["scoring_weights"]["density"] = -0.1
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Scoring weights must be >= 0"

    def test_escalation_threshold_out_of_range(self, validator, valid_profile):
        valid_profile["escalation_threshold"] = 2.0
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Escalation threshold must be <= 1.0"

    def test_additional_properties_rejected_at_top_level(self, validator, valid_profile):
        valid_profile["unknown_field"] = "test"
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Unknown top-level properties should be rejected"

    def test_additional_properties_rejected_in_domain(self, validator, valid_profile):
        valid_profile["domain"]["unknown"] = "test"
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Unknown domain properties should be rejected"

    def test_normalization_target_must_be_uppercase(self, validator, valid_profile):
        valid_profile["relation_taxonomy"]["normalization"]["BUILT"] = "created"
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Normalization targets must be UPPER_SNAKE_CASE"
