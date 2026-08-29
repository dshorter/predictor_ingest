"""Per-domain model selection and feature flags.

Both accessors exist so that a domain-specific requirement lands in that
domain's own config rather than in a sidecar env file keyed on a systemd
instance name. The isolation tests are the load-bearing ones: the predictor is
domain-agnostic, and naming a model for one domain must not move another.
"""

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain import (  # noqa: E402
    DEFAULT_MODEL,
    MODEL_STAGES,
    feature_enabled,
    model_from_profile,
)

REPO = Path(__file__).resolve().parents[1]
ACTIVE_DOMAINS = ("film", "semiconductors", "weapons_detection")


@pytest.fixture(autouse=True)
def _no_ambient_model(monkeypatch):
    """Every test states its own env; none inherits the developer's shell."""
    monkeypatch.delenv("PRIMARY_MODEL", raising=False)


class TestModelResolutionOrder:
    """profile -> PRIMARY_MODEL -> DEFAULT_MODEL, in that order."""

    def test_nothing_set_returns_framework_default(self):
        assert model_from_profile(None) == DEFAULT_MODEL
        assert model_from_profile({}) == DEFAULT_MODEL

    def test_env_used_when_profile_is_silent(self, monkeypatch):
        monkeypatch.setenv("PRIMARY_MODEL", "claude-sonnet-5")
        assert model_from_profile({"domain": {"slug": "ai"}}) == "claude-sonnet-5"

    def test_profile_beats_env(self, monkeypatch):
        monkeypatch.setenv("PRIMARY_MODEL", "claude-sonnet-5")
        profile = {"models": {"extraction": "claude-haiku-4-5-20251001"}}
        assert model_from_profile(profile) == "claude-haiku-4-5-20251001"

    def test_profile_used_with_no_env_at_all(self):
        profile = {"models": {"extraction": "claude-haiku-4-5-20251001"}}
        assert model_from_profile(profile) == "claude-haiku-4-5-20251001"


class TestModelNeverResolvesEmpty:
    """The drift these accessors replaced: five readers, three behaviours."""

    def test_whitespace_env_falls_through(self, monkeypatch):
        monkeypatch.setenv("PRIMARY_MODEL", "   ")
        assert model_from_profile(None) == DEFAULT_MODEL

    def test_empty_env_falls_through(self, monkeypatch):
        monkeypatch.setenv("PRIMARY_MODEL", "")
        assert model_from_profile(None) == DEFAULT_MODEL

    def test_padded_env_is_stripped(self, monkeypatch):
        monkeypatch.setenv("PRIMARY_MODEL", "  claude-sonnet-5  ")
        assert model_from_profile(None) == "claude-sonnet-5"

    def test_empty_profile_value_falls_through_to_env(self, monkeypatch):
        monkeypatch.setenv("PRIMARY_MODEL", "claude-sonnet-5")
        assert model_from_profile({"models": {"extraction": ""}}) == "claude-sonnet-5"

    def test_null_models_block_falls_through(self, monkeypatch):
        monkeypatch.setenv("PRIMARY_MODEL", "claude-sonnet-5")
        assert model_from_profile({"models": None}) == "claude-sonnet-5"

    @pytest.mark.parametrize("stage", MODEL_STAGES)
    def test_no_stage_ever_returns_empty(self, stage):
        assert model_from_profile(None, stage).strip()


class TestModelStages:
    def test_stages_resolve_independently(self, monkeypatch):
        monkeypatch.setenv("PRIMARY_MODEL", "claude-sonnet-5")
        profile = {"models": {"extraction": "claude-haiku-4-5-20251001"}}
        assert model_from_profile(profile, "extraction") == "claude-haiku-4-5-20251001"
        # synthesis said nothing, so it inherits rather than borrowing extraction's
        assert model_from_profile(profile, "synthesis") == "claude-sonnet-5"

    def test_unknown_stage_is_rejected(self):
        with pytest.raises(ValueError, match="unknown model stage"):
            model_from_profile({}, "embedding")


class TestDomainIsolation:
    """The property that makes this config rather than an exception."""

    def test_one_domain_naming_a_model_does_not_move_another(self, monkeypatch):
        monkeypatch.setenv("PRIMARY_MODEL", "claude-sonnet-5")
        movers_domain = {"models": {"extraction": "claude-haiku-4-5-20251001"}}
        landscape_domain = {"domain": {"slug": "semiconductors"}}

        assert model_from_profile(movers_domain) == "claude-haiku-4-5-20251001"
        assert model_from_profile(landscape_domain) == "claude-sonnet-5"

    @pytest.mark.parametrize("slug", ACTIVE_DOMAINS)
    def test_live_profiles_resolve_every_stage(self, slug, monkeypatch):
        monkeypatch.setenv("PRIMARY_MODEL", "claude-sonnet-5")
        profile = yaml.safe_load((REPO / "domains" / slug / "domain.yaml").read_text())
        for stage in MODEL_STAGES:
            assert model_from_profile(profile, stage).strip()

    def test_no_live_domain_pins_a_model_yet(self):
        """Baseline. Update deliberately when a domain takes an override."""
        pinned = {
            slug: yaml.safe_load(
                (REPO / "domains" / slug / "domain.yaml").read_text()
            ).get("models")
            for slug in ACTIVE_DOMAINS
        }
        assert {k: v for k, v in pinned.items() if v} == {}


class TestFeatureEnabled:
    def test_absent_features_block_uses_default(self):
        assert feature_enabled(None, "relation_extraction") is True
        assert feature_enabled({}, "relation_extraction") is True
        assert feature_enabled({}, "some_opt_in", default=False) is False

    def test_absent_feature_uses_default(self):
        profile = {"features": {"llm_disambiguation": {"enabled": True}}}
        assert feature_enabled(profile, "relation_extraction") is True

    def test_explicit_false_wins_over_default(self):
        profile = {"features": {"relation_extraction": {"enabled": False}}}
        assert feature_enabled(profile, "relation_extraction") is False

    def test_explicit_true(self):
        profile = {"features": {"relation_extraction": {"enabled": True}}}
        assert feature_enabled(profile, "relation_extraction") is True

    def test_bare_boolean_form_is_accepted(self):
        assert feature_enabled({"features": {"x": False}}, "x") is False
        assert feature_enabled({"features": {"x": True}}, "x") is True

    def test_null_features_block(self):
        assert feature_enabled({"features": None}, "relation_extraction") is True

    def test_block_without_enabled_key_uses_default(self):
        profile = {"features": {"relation_extraction": {"batch_size": 10}}}
        assert feature_enabled(profile, "relation_extraction") is True
        assert feature_enabled(profile, "relation_extraction", default=False) is False

    @pytest.mark.parametrize("slug", ACTIVE_DOMAINS)
    def test_relations_are_on_everywhere_today(self, slug):
        """Every live domain is Landscape-shaped for now; film flips later."""
        profile = yaml.safe_load((REPO / "domains" / slug / "domain.yaml").read_text())
        assert feature_enabled(profile, "relation_extraction") is True

    @pytest.mark.parametrize("slug", ACTIVE_DOMAINS)
    def test_existing_feature_reads_are_unchanged(self, slug):
        """The accessor must agree with the hand-rolled reads it centralises."""
        profile = yaml.safe_load((REPO / "domains" / slug / "domain.yaml").read_text())
        for name in ("llm_disambiguation", "relation_inference"):
            hand_rolled = (profile.get("features", {}).get(name) or {}).get(
                "enabled", True
            )
            assert feature_enabled(profile, name) is bool(hand_rolled)


class TestSchemaDeclaresModels:
    """doc_selection is schema-declared; models follows the same convention."""

    def test_models_is_declared(self):
        import json

        schema = json.loads((REPO / "schemas" / "domain-profile.json").read_text())
        models = schema["properties"]["models"]
        assert models["additionalProperties"] is False
        assert set(models["properties"]) == set(MODEL_STAGES)

    def test_schema_rejects_an_unknown_stage(self):
        import json

        import jsonschema

        schema = json.loads((REPO / "schemas" / "domain-profile.json").read_text())
        bad = {"models": {"embedding": "claude-haiku-4-5-20251001"}}
        errors = list(jsonschema.Draft7Validator(schema).iter_errors(bad))
        assert any("embedding" in e.message for e in errors)
