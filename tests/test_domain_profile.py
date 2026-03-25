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
    "gate_thresholds": {
        "evidence_fidelity_min": 0.70,
        "orphan_max": 0.0,
        "zero_value_min_entities": 1,
        "zero_value_min_doc_chars": 500,
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
        "base_relation", "gate_thresholds",
        "trend_weights", "suppressed_entities", "prompts",
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

    def test_missing_gate_threshold_field(self, validator, valid_profile):
        del valid_profile["gate_thresholds"]["evidence_fidelity_min"]
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

    def test_additional_properties_rejected_in_domain(self, validator, valid_profile):
        valid_profile["domain"]["unknown"] = "test"
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Unknown domain properties should be rejected"

    def test_normalization_target_must_be_uppercase(self, validator, valid_profile):
        valid_profile["relation_taxonomy"]["normalization"]["BUILT"] = "created"
        errors = list(validator.iter_errors(valid_profile))
        assert len(errors) > 0, "Normalization targets must be UPPER_SNAKE_CASE"


class TestAIDomainProfile:
    """Test the actual domains/ai/domain.yaml profile."""

    AI_PROFILE_PATH = Path(__file__).parent.parent / "domains" / "ai" / "domain.yaml"
    EXTRACTION_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "extraction.json"

    @pytest.fixture
    def ai_profile(self):
        import yaml
        with open(self.AI_PROFILE_PATH) as f:
            return yaml.safe_load(f)

    def test_ai_profile_exists(self):
        assert self.AI_PROFILE_PATH.exists()

    def test_ai_profile_validates_against_schema(self, validator, ai_profile):
        validator.validate(ai_profile)

    def test_entity_types_match_extraction_schema(self, ai_profile):
        with open(self.EXTRACTION_SCHEMA_PATH) as f:
            ext = json.load(f)
        schema_types = set(ext["$defs"]["entityType"]["enum"])
        profile_types = set(ai_profile["entity_types"])
        assert schema_types == profile_types, (
            f"Mismatch: schema-only={schema_types - profile_types}, "
            f"profile-only={profile_types - schema_types}"
        )

    def test_relation_types_match_extraction_schema(self, ai_profile):
        with open(self.EXTRACTION_SCHEMA_PATH) as f:
            ext = json.load(f)
        schema_rels = set(ext["$defs"]["relationType"]["enum"])
        profile_rels = set(ai_profile["relation_taxonomy"]["canonical"])
        assert schema_rels == profile_rels, (
            f"Mismatch: schema-only={schema_rels - profile_rels}, "
            f"profile-only={profile_rels - schema_rels}"
        )

    def test_normalization_targets_are_canonical(self, ai_profile):
        canonical = set(ai_profile["relation_taxonomy"]["canonical"])
        bad = {
            k: v for k, v in ai_profile["relation_taxonomy"]["normalization"].items()
            if v not in canonical
        }
        assert not bad, f"Normalization targets not in canonical: {bad}"

    def test_id_prefixes_cover_all_entity_types(self, ai_profile):
        entity_types = set(ai_profile["entity_types"])
        prefix_types = set(ai_profile["id_prefixes"].keys())
        assert entity_types == prefix_types, (
            f"Missing prefixes: {entity_types - prefix_types}, "
            f"Extra prefixes: {prefix_types - entity_types}"
        )

    def test_base_relation_is_canonical(self, ai_profile):
        canonical = set(ai_profile["relation_taxonomy"]["canonical"])
        assert ai_profile["base_relation"] in canonical

    def test_trend_weights_sum_to_one(self, ai_profile):
        tw = ai_profile["trend_weights"]
        total = tw["velocity"] + tw["novelty"] + tw["activity"]
        assert abs(total - 1.0) < 0.01, f"Trend weights sum to {total}, expected 1.0"

    def test_document_prefix_is_doc(self, ai_profile):
        """Document type has special 'doc' prefix, not 'document'."""
        assert ai_profile["id_prefixes"]["Document"] == "doc"

    def test_suppressed_entities_not_empty(self, ai_profile):
        assert len(ai_profile["suppressed_entities"]) > 0

    def test_prompt_files_exist(self, ai_profile):
        domain_dir = self.AI_PROFILE_PATH.parent
        prompts_dir = domain_dir / ai_profile["prompts"]["dir"]
        assert prompts_dir.is_dir(), f"Prompts dir not found: {prompts_dir}"

        system_file = prompts_dir / ai_profile["prompts"].get("system_prompt", "system.txt")
        user_file = prompts_dir / ai_profile["prompts"].get("user_prompt", "user.txt")
        single_file = prompts_dir / ai_profile["prompts"].get("single_message_prompt", "single_message.txt")

        assert system_file.exists(), f"System prompt not found: {system_file}"
        assert user_file.exists(), f"User prompt not found: {user_file}"
        assert single_file.exists(), f"Single message prompt not found: {single_file}"

    def test_system_prompt_has_placeholders(self, ai_profile):
        domain_dir = self.AI_PROFILE_PATH.parent
        prompts_dir = domain_dir / ai_profile["prompts"]["dir"]
        system_text = (prompts_dir / "system.txt").read_text()

        # Must have template placeholders for dynamic content
        assert "{extractor_version}" in system_text
        assert "{entity_types}" in system_text
        assert "{relation_types}" in system_text
        assert "{suppressed_entities_sample}" in system_text
        assert "{base_relation}" in system_text

    def test_user_prompt_has_placeholders(self, ai_profile):
        domain_dir = self.AI_PROFILE_PATH.parent
        prompts_dir = domain_dir / ai_profile["prompts"]["dir"]
        user_text = (prompts_dir / "user.txt").read_text()

        assert "{docId}" in user_text
        assert "{title}" in user_text
        assert "{text}" in user_text

    def test_single_message_prompt_has_placeholders(self, ai_profile):
        domain_dir = self.AI_PROFILE_PATH.parent
        prompts_dir = domain_dir / ai_profile["prompts"]["dir"]
        single_text = (prompts_dir / "single_message.txt").read_text()

        assert "{docId}" in single_text
        assert "{entity_types}" in single_text
        assert "{relation_types}" in single_text
        assert "{text}" in single_text

    def test_views_yaml_exists(self):
        views_path = self.AI_PROFILE_PATH.parent / "views.yaml"
        assert views_path.exists(), "domains/ai/views.yaml not found"

    def test_views_yaml_has_required_keys(self):
        import yaml
        views_path = self.AI_PROFILE_PATH.parent / "views.yaml"
        with open(views_path) as f:
            views = yaml.safe_load(f)
        assert "document_relations" in views, "Missing document_relations"
        assert "dependency_relations" in views, "Missing dependency_relations"
        assert len(views["document_relations"]) > 0
        assert len(views["dependency_relations"]) > 0

    def test_views_relations_are_canonical(self, ai_profile):
        import yaml
        views_path = self.AI_PROFILE_PATH.parent / "views.yaml"
        with open(views_path) as f:
            views = yaml.safe_load(f)
        canonical = set(ai_profile["relation_taxonomy"]["canonical"])
        for key in ["document_relations", "dependency_relations"]:
            for rel in views[key]:
                assert rel in canonical, f"'{rel}' in {key} is not a canonical relation"

    def test_feeds_yaml_exists(self):
        feeds_path = self.AI_PROFILE_PATH.parent / "feeds.yaml"
        assert feeds_path.exists(), "domains/ai/feeds.yaml not found"

    def test_feeds_yaml_has_feeds(self):
        import yaml
        feeds_path = self.AI_PROFILE_PATH.parent / "feeds.yaml"
        with open(feeds_path) as f:
            feeds = yaml.safe_load(f)
        assert "feeds" in feeds, "Missing 'feeds' key"
        assert len(feeds["feeds"]) > 0, "No feeds defined"

    def test_feeds_have_required_fields(self):
        import yaml
        feeds_path = self.AI_PROFILE_PATH.parent / "feeds.yaml"
        with open(feeds_path) as f:
            feeds = yaml.safe_load(f)
        for feed in feeds["feeds"]:
            assert "name" in feed, f"Feed missing 'name': {feed}"
            assert "url" in feed, f"Feed missing 'url': {feed.get('name', '?')}"
            assert "tier" in feed, f"Feed missing 'tier': {feed['name']}"


class TestBiosafetyDomainProfile:
    """Validate the biosafety domain profile end-to-end."""

    BIO_PROFILE_PATH = Path(__file__).parent.parent / "domains" / "biosafety" / "domain.yaml"

    @pytest.fixture
    def bio_profile(self):
        import yaml
        with open(self.BIO_PROFILE_PATH) as f:
            return yaml.safe_load(f)

    def test_biosafety_profile_exists(self):
        assert self.BIO_PROFILE_PATH.exists()

    def test_loads_via_domain_loader(self):
        from domain import load_domain_profile
        profile = load_domain_profile("biosafety")
        assert profile["base_relation"] == "MENTIONS"

    def test_validates_against_json_schema(self, bio_profile):
        import json
        from jsonschema import Draft202012Validator
        with open(Path(__file__).parent.parent / "schemas" / "domain-profile.json") as f:
            schema = json.load(f)
        validator = Draft202012Validator(schema)
        errors = list(validator.iter_errors(bio_profile))
        assert not errors, f"Schema errors: {[e.message for e in errors]}"

    def test_has_select_agent_entity_type(self, bio_profile):
        assert "SelectAgent" in bio_profile["entity_types"]

    def test_has_facility_entity_type(self, bio_profile):
        assert "Facility" in bio_profile["entity_types"]

    def test_has_regulation_entity_type(self, bio_profile):
        assert "Regulation" in bio_profile["entity_types"]

    def test_has_regulatory_relations(self, bio_profile):
        canonical = bio_profile["relation_taxonomy"]["canonical"]
        for rel in ["REGULATES", "INSPECTS", "COMPLIES_WITH", "AUTHORIZES"]:
            assert rel in canonical, f"Missing regulatory relation: {rel}"

    def test_has_containment_relations(self, bio_profile):
        canonical = bio_profile["relation_taxonomy"]["canonical"]
        for rel in ["STORES", "TRANSFERS", "CONTAINS"]:
            assert rel in canonical, f"Missing containment relation: {rel}"

    def test_has_incident_relations(self, bio_profile):
        canonical = bio_profile["relation_taxonomy"]["canonical"]
        for rel in ["CAUSED", "DETECTED_IN", "RESPONDS_TO"]:
            assert rel in canonical, f"Missing incident relation: {rel}"

    def test_id_prefix_for_select_agent(self, bio_profile):
        assert bio_profile["id_prefixes"]["SelectAgent"] == "agent"

    def test_id_prefix_for_facility(self, bio_profile):
        assert bio_profile["id_prefixes"]["Facility"] == "facility"

    def test_trend_weights_sum(self, bio_profile):
        tw = bio_profile["trend_weights"]
        total = tw["velocity"] + tw["novelty"] + tw["activity"]
        assert abs(total - 1.0) < 0.01

    def test_prompt_files_exist(self):
        prompts_dir = self.BIO_PROFILE_PATH.parent / "prompts"
        for name in ["system.txt", "user.txt", "single_message.txt"]:
            assert (prompts_dir / name).exists(), f"Missing prompt: {name}"

    def test_system_prompt_has_placeholders(self, bio_profile):
        prompts_dir = self.BIO_PROFILE_PATH.parent / bio_profile["prompts"]["dir"]
        text = (prompts_dir / "system.txt").read_text()
        for placeholder in ["{entity_types}", "{relation_types}", "{base_relation}"]:
            assert placeholder in text, f"Missing placeholder: {placeholder}"

    def test_feeds_file_exists(self):
        feeds_path = self.BIO_PROFILE_PATH.parent / "feeds.yaml"
        assert feeds_path.exists()

    def test_feeds_have_required_fields(self):
        import yaml
        feeds_path = self.BIO_PROFILE_PATH.parent / "feeds.yaml"
        with open(feeds_path) as f:
            feeds = yaml.safe_load(f)
        assert len(feeds["feeds"]) >= 5, "Need at least 5 feeds"
        for feed in feeds["feeds"]:
            assert "name" in feed, f"Feed missing 'name': {feed}"
            assert "url" in feed, f"Feed missing 'url': {feed.get('name', '?')}"
            assert "tier" in feed, f"Feed missing 'tier': {feed['name']}"

    def test_views_file_exists(self):
        views_path = self.BIO_PROFILE_PATH.parent / "views.yaml"
        assert views_path.exists()

    def test_normalization_targets_are_canonical(self, bio_profile):
        canonical = set(bio_profile["relation_taxonomy"]["canonical"])
        norm = bio_profile["relation_taxonomy"]["normalization"]
        for alias, target in norm.items():
            assert target in canonical, (
                f"Normalization '{alias}' → '{target}' but '{target}' not in canonical"
            )


class TestProfileValidationOnLoad:
    """Test that load_domain_profile validates structure and fails fast."""

    def test_load_ai_profile_succeeds(self):
        """The AI domain profile should load without errors."""
        from domain import load_domain_profile
        profile = load_domain_profile("ai")
        assert profile["base_relation"] == "MENTIONS"

    def test_missing_required_key_raises(self, tmp_path):
        """Missing a required key should raise ValueError."""
        import yaml
        from domain import load_domain_profile

        # Create a minimal but incomplete profile
        domain_dir = tmp_path / "domains" / "bad"
        domain_dir.mkdir(parents=True)
        profile = {"domain": "bad", "entity_types": ["Org"]}
        with open(domain_dir / "domain.yaml", "w") as f:
            yaml.dump(profile, f)

        # Monkey-patch _find_domains_dir to use tmp_path
        import domain as domain_mod
        orig = domain_mod._find_domains_dir
        domain_mod._find_domains_dir = lambda: tmp_path / "domains"
        try:
            with pytest.raises(ValueError, match="missing required keys"):
                load_domain_profile("bad")
        finally:
            domain_mod._find_domains_dir = orig

    def test_base_relation_not_in_canonical_raises(self, tmp_path):
        """base_relation must be in canonical relations."""
        import yaml
        from domain import load_domain_profile

        profile = _build_full_profile()
        profile["base_relation"] = "NONEXISTENT"

        domain_dir = tmp_path / "domains" / "bad3"
        domain_dir.mkdir(parents=True)
        with open(domain_dir / "domain.yaml", "w") as f:
            yaml.dump(profile, f)

        import domain as domain_mod
        orig = domain_mod._find_domains_dir
        domain_mod._find_domains_dir = lambda: tmp_path / "domains"
        try:
            with pytest.raises(ValueError, match="not in relation_taxonomy.canonical"):
                load_domain_profile("bad3")
        finally:
            domain_mod._find_domains_dir = orig


def _build_full_profile():
    """Build a minimal but structurally complete profile for testing."""
    return {
        "domain": "test",
        "entity_types": ["Org", "Person"],
        "relation_taxonomy": {
            "canonical": ["MENTIONS", "CREATED"],
            "normalization": {"BUILT": "CREATED"},
        },
        "id_prefixes": {"Org": "org"},
        "base_relation": "MENTIONS",
        "gate_thresholds": {"evidence_fidelity_min": 0.70, "orphan_max": 0.0,
                            "zero_value_min_entities": 1, "zero_value_min_doc_chars": 500},
        "trend_weights": {"velocity": 0.4, "novelty": 0.3, "activity": 0.3},
        "suppressed_entities": [],
        "prompts": {"dir": "prompts"},
    }

