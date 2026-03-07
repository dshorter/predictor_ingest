"""Domain profile loader.

Loads domain-specific configuration from domains/<slug>/domain.yaml.
The profile provides entity types, relation taxonomy, thresholds,
scoring weights, and prompt paths — everything that varies by domain.

Usage:
    from domain import load_domain_profile, get_active_profile

    # Load explicitly
    profile = load_domain_profile("ai")

    # Get the currently active profile (default: "ai")
    profile = get_active_profile()

    # Access values
    profile["entity_types"]         # ["Org", "Person", ...]
    profile["base_relation"]        # "MENTIONS"
    profile["quality_thresholds"]   # {entity_density_target: 5.0, ...}
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml

# Environment variable for domain override (used by subprocess pipelines)
_ENV_DOMAIN = "PREDICTOR_DOMAIN"


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


def load_domain_profile(domain: str = "ai") -> dict[str, Any]:
    """Load a domain profile from domains/<domain>/domain.yaml.

    Args:
        domain: Domain slug (e.g., "ai", "cyber"). Defaults to "ai".

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

    # Attach the resolved domain directory path for prompt/config loading
    profile["_domain_dir"] = domain_dir
    profile["_domain_slug"] = domain

    return profile


def get_domain_dir(domain: str = "ai") -> Path:
    """Get the filesystem path to a domain's directory.

    Args:
        domain: Domain slug.

    Returns:
        Path to domains/<domain>/
    """
    domains_dir = _find_domains_dir()
    return domains_dir / domain


def set_active_domain(domain: str = "ai") -> dict[str, Any]:
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
    return os.environ.get(_ENV_DOMAIN, "ai")


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
