"""Ingest dispatcher — routes feeds to the appropriate fetcher by type.

The pipeline calls this module to process all feeds in a domain's feeds.yaml.
Each feed has a `type` field that determines which fetcher handles it:
  - rss/atom  → src/ingest/rss.py (existing)
  - bluesky   → src/ingest/bluesky.py
  - reddit    → src/ingest/reddit.py
  - edgar     → src/ingest/edgar.py (SEC EDGAR filings)
  - patents   → src/ingest/patents.py (USPTO PatentsView)

Substack feeds use type=rss since they serve standard RSS.
"""

from __future__ import annotations

import importlib
from typing import Any


# Registry of feed types → fetcher module paths.
# Each module must expose: ingest_feed(feed_config, **kwargs) -> dict
_FETCHER_REGISTRY: dict[str, str] = {
    "rss": "ingest.rss",
    "atom": "ingest.rss",       # atom feeds use the same feedparser-based fetcher
    "bluesky": "ingest.bluesky",
    "reddit": "ingest.reddit",
    "edgar": "ingest.edgar",    # SEC EDGAR company filings
    "patents": "ingest.patents",  # USPTO PatentsView patent search
}


def get_fetcher(feed_type: str) -> Any:
    """Import and return the fetcher module for the given feed type.

    Args:
        feed_type: The 'type' field from feeds.yaml (e.g., 'rss', 'bluesky')

    Returns:
        The fetcher module (must have an ingest_feed function)

    Raises:
        ValueError: If the feed type is not registered
        ImportError: If the fetcher module is not yet implemented
    """
    feed_type = feed_type.lower()
    if feed_type not in _FETCHER_REGISTRY:
        raise ValueError(
            f"Unknown feed type '{feed_type}'. "
            f"Registered types: {sorted(_FETCHER_REGISTRY.keys())}"
        )
    module_path = _FETCHER_REGISTRY[feed_type]
    return importlib.import_module(module_path)


def is_supported(feed_type: str) -> bool:
    """Check if a feed type has a registered fetcher."""
    return feed_type.lower() in _FETCHER_REGISTRY


def registered_types() -> list[str]:
    """Return sorted list of registered feed types."""
    return sorted(_FETCHER_REGISTRY.keys())
