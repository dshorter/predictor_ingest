"""Domain profile loader.

Loads domain-specific configuration from domains/<slug>/domain.yaml.
The profile provides entity types, relation taxonomy, thresholds,
and prompt paths — everything that varies by domain.

Usage:
    from domain import load_domain_profile, get_active_profile

    # Load explicitly
    profile = load_domain_profile("film")

    # Get the currently active profile (default: "film")
    profile = get_active_profile()

    # Access values
    profile["entity_types"]         # ["Org", "Person", ...]
    profile["base_relation"]        # "MENTIONS"
    profile["gate_thresholds"]      # {evidence_fidelity_min: 0.70, ...}

    # Per-domain calibration accessors
    model_from_profile(profile, "extraction")     # domain.yaml -> env -> default
    feature_enabled(profile, "relation_extraction")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml

# Environment variable for domain override (used by subprocess pipelines)
_ENV_DOMAIN = "PREDICTOR_DOMAIN"

# Pipeline-wide model default, used when neither the domain profile nor the
# environment names one. Kept here rather than duplicated at each call site:
# before this existed the five readers of PRIMARY_MODEL had drifted into three
# behaviours, one of which could resolve to the empty string.
DEFAULT_MODEL = "claude-sonnet-5"
_ENV_MODEL = "PRIMARY_MODEL"

# Stages that may carry a per-domain model override.
MODEL_STAGES = ("extraction", "synthesis", "narratives")


# Root of the repository (two levels up from src/domain/)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DOMAINS_DIR = _REPO_ROOT / "domains"

# Module-level active profile — set on first access or explicitly via set_active_domain()
_active_profile: Optional[dict[str, Any]] = None
_active_domain: Optional[str] = None


def _find_domains_dir() -> Path:
    """Locate the domains/ directory."""
    if _DOMAINS_DIR.is_dir():
        return _DOMAINS_DIR
    # Fallback: check relative to cwd
    cwd_domains = Path.cwd() / "domains"
    if cwd_domains.is_dir():
        return cwd_domains
    raise FileNotFoundError(
        f"Cannot find domains/ directory. Checked: {_DOMAINS_DIR}, {cwd_domains}"
    )


def load_domain_profile(domain: str = "film") -> dict[str, Any]:
    """Load a domain profile from domains/<domain>/domain.yaml.

    Args:
        domain: Domain slug (e.g., "film", "ai", "biosafety"). Defaults to "film".

    Returns:
        Parsed domain profile dict.

    Raises:
        FileNotFoundError: If domain directory or domain.yaml not found.
        ValueError: If domain.yaml is invalid YAML.
    """
    domains_dir = _find_domains_dir()
    domain_dir = domains_dir / domain
    profile_path = domain_dir / "domain.yaml"

    if not profile_path.exists():
        raise FileNotFoundError(
            f"Domain profile not found: {profile_path}\n"
            f"Available domains: {[d.name for d in domains_dir.iterdir() if d.is_dir() and not d.name.startswith('_')]}"
        )

    with open(profile_path, "r", encoding="utf-8") as f:
        profile = yaml.safe_load(f)

    if not isinstance(profile, dict):
        raise ValueError(f"Invalid domain profile at {profile_path}: expected dict, got {type(profile)}")

    # Validate required fields with clear error messages
    _validate_profile(profile, profile_path)

    # Attach the resolved domain directory path for prompt/config loading
    profile["_domain_dir"] = domain_dir
    profile["_domain_slug"] = domain

    return profile


def _validate_profile(profile: dict[str, Any], path: Path) -> None:
    """Validate domain profile structure. Fail fast with clear errors."""
    required_keys = {
        "domain": (str, dict),
        "entity_types": (list,),
        "relation_taxonomy": (dict,),
        "id_prefixes": (dict,),
        "base_relation": (str,),
        "gate_thresholds": (dict,),
        "trend_weights": (dict,),
        "suppressed_entities": (list,),
        "prompts": (dict,),
    }

    missing = [k for k in required_keys if k not in profile]
    if missing:
        raise ValueError(
            f"Domain profile {path} missing required keys: {missing}"
        )

    for key, expected_types in required_keys.items():
        val = profile[key]
        if not isinstance(val, expected_types):
            type_names = "/".join(t.__name__ for t in expected_types)
            raise ValueError(
                f"Domain profile {path}: '{key}' must be {type_names}, "
                f"got {type(val).__name__}"
            )

    # Validate relation_taxonomy has required sub-keys
    rt = profile["relation_taxonomy"]
    for sub in ("canonical", "normalization"):
        if sub not in rt:
            raise ValueError(
                f"Domain profile {path}: relation_taxonomy missing '{sub}'"
            )

    # Validate base_relation is in canonical relations
    canonical = rt["canonical"]
    if profile["base_relation"] not in canonical:
        raise ValueError(
            f"Domain profile {path}: base_relation '{profile['base_relation']}' "
            f"not in relation_taxonomy.canonical"
        )

    # Validate trend_weights core weights sum to ~1.0
    tw = profile["trend_weights"]
    core_trend = sum(tw.get(k, 0) for k in ("velocity", "novelty", "activity"))
    if abs(core_trend - 1.0) > 0.01:
        raise ValueError(
            f"Domain profile {path}: trend_weights (velocity+novelty+activity) "
            f"sum to {core_trend:.3f}, expected ~1.0"
        )


def get_domain_dir(domain: str = "film") -> Path:
    """Get the filesystem path to a domain's directory.

    Args:
        domain: Domain slug.

    Returns:
        Path to domains/<domain>/
    """
    domains_dir = _find_domains_dir()
    return domains_dir / domain


def set_active_domain(domain: str = "film") -> dict[str, Any]:
    """Set the active domain profile (module-level singleton).

    Called once at startup (e.g., from CLI argument parsing).
    Subsequent calls to get_active_profile() return this profile.

    Args:
        domain: Domain slug.

    Returns:
        The loaded profile.
    """
    global _active_profile, _active_domain
    _active_profile = load_domain_profile(domain)
    _active_domain = domain
    return _active_profile


def _default_domain() -> str:
    """Return the default domain slug from env or fallback to 'ai'."""
    return os.environ.get(_ENV_DOMAIN, "film")


def get_active_profile() -> dict[str, Any]:
    """Get the active domain profile.

    On first access, loads the domain specified by PREDICTOR_DOMAIN
    environment variable, falling back to "ai".

    Returns:
        The active domain profile dict.
    """
    global _active_profile
    if _active_profile is None:
        set_active_domain(_default_domain())
    return _active_profile


def get_active_domain() -> str:
    """Get the slug of the currently active domain.

    Returns:
        Domain slug string (e.g., "ai").
    """
    global _active_domain
    if _active_domain is None:
        get_active_profile()  # triggers default load
    return _active_domain


def model_from_profile(
    profile: dict[str, Any] | None,
    stage: str = "extraction",
) -> str:
    """Resolve the model for one pipeline stage.

    Per-domain models live in domain.yaml under `models`, the same shape
    doc_selection uses for per-domain budgets (ADR-010 D3 / Sprint 20.5).
    Resolution order:

        1. profile["models"][stage]  — this domain asked for a specific model
        2. PRIMARY_MODEL env var     — the pipeline-wide default
        3. DEFAULT_MODEL             — framework floor

    A domain that omits the block inherits the pipeline default, so naming a
    model for one domain cannot move any other domain. That property is the
    point: the predictor is domain-agnostic, and a per-domain model belongs in
    the domain's own config rather than in a sidecar env file keyed on a
    systemd instance name, which would be an exception hidden outside the
    config system entirely.

    Why a domain would differ: the model requirement follows the domain's
    lens, not the pipeline's convenience. Film runs the Movers lens, which is
    built from base-relation mentions rather than relation quality, so it does
    not need the tier a Landscape domain does.

    Args:
        profile: A loaded domain profile, or None to fall through to env.
        stage:   One of MODEL_STAGES.

    Returns:
        A model id. Never empty — an empty or whitespace-only env var falls
        through to DEFAULT_MODEL rather than propagating "" to an API call.
    """
    if stage not in MODEL_STAGES:
        raise ValueError(
            f"unknown model stage {stage!r} — known: {', '.join(MODEL_STAGES)}"
        )

    section = (profile or {}).get("models") or {}
    configured = str(section.get(stage, "") or "").strip()
    if configured:
        return configured

    return os.environ.get(_ENV_MODEL, "").strip() or DEFAULT_MODEL


def model_for_stage(stage: str = "extraction") -> str:
    """model_from_profile against the active domain profile.

    The drop-in for call sites that previously read PRIMARY_MODEL directly.
    """
    return model_from_profile(get_active_profile(), stage)


def feature_enabled(
    profile: dict[str, Any] | None,
    feature: str,
    default: bool = True,
) -> bool:
    """Whether a per-domain feature is switched on.

    Centralises the `profile.get("features", {})` read that llm_disambiguation
    and relation_inference already do by hand in five modules, so every
    consumer agrees on what an absent block means: absent → `default`.

    `default=True` suits capability flags a domain switches OFF as the
    exception (relation_extraction); pass default=False for a capability a
    domain must opt IN to.
    """
    features = (profile or {}).get("features") or {}
    block = features.get(feature)
    if block is None:
        return default
    if isinstance(block, bool):
        return block
    return bool(block.get("enabled", default))
