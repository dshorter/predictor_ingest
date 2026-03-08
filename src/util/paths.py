"""Domain-aware data path helpers.

All pipeline data directories are scoped by domain to prevent cross-domain
data collisions.  Layout:

    data/db/{domain}.db
    data/raw/{domain}/
    data/text/{domain}/
    data/docpacks/{domain}/
    data/extractions/{domain}/
    data/graphs/{domain}/
    data/logs/{domain}/
"""

from __future__ import annotations

import os
from pathlib import Path


def _resolve_domain(domain: str | None = None) -> str:
    """Return explicit domain or fall back to env / default."""
    if domain:
        return domain
    return os.environ.get("PREDICTOR_DOMAIN", "ai")


def get_db_path(domain: str | None = None) -> Path:
    d = _resolve_domain(domain)
    return Path("data") / "db" / f"{d}.db"


def get_raw_dir(domain: str | None = None) -> Path:
    return Path("data") / "raw" / _resolve_domain(domain)


def get_text_dir(domain: str | None = None) -> Path:
    return Path("data") / "text" / _resolve_domain(domain)


def get_docpacks_dir(domain: str | None = None) -> Path:
    return Path("data") / "docpacks" / _resolve_domain(domain)


def get_extractions_dir(domain: str | None = None) -> Path:
    return Path("data") / "extractions" / _resolve_domain(domain)


def get_graphs_dir(domain: str | None = None) -> Path:
    return Path("data") / "graphs" / _resolve_domain(domain)


def get_logs_dir(domain: str | None = None) -> Path:
    return Path("data") / "logs" / _resolve_domain(domain)
