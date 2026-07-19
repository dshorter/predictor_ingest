"""Configuration loading for predictor_ingest.

Loads feed configuration and export settings from YAML files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


# --------------------------------------------------------------------------- #
# Export / UI defaults
# --------------------------------------------------------------------------- #

# Default number of days shown when the UI first loads.
# Exposed as a config variable so it can be tuned as the dataset grows.
DEFAULT_DATE_WINDOW_DAYS: int = 30

# --------------------------------------------------------------------------- #
# Methodology version (Sprint 20 prep, 2026-07-19)
# --------------------------------------------------------------------------- #
# Stamped on every trend_history row and every export's meta block so
# scoring output is auditable back to the methodology that produced it.
# Distinct from the epoch column: epoch marks DATA-continuity boundaries
# (restarts), this marks SCORING-CODE boundaries — they can move
# independently.
#
# Bump rule: increment in the SAME commit as any scoring-affecting change
# (weights, formulas, filters, ranking). `git log -S METHODOLOGY_VERSION`
# is then the complete audit trail of what changed and when.
#
#   "1" — Sprint-13-era scoring (pre-2026-07-03-review methodology)
#   "2" — reserved: lands with Sprint 20.7-20.9 (CI-lower-bound velocity,
#         persistence-of-rise, bridge_delta)
METHODOLOGY_VERSION: str = "1"


@dataclass
class FeedConfig:
    """Configuration for a single feed (RSS/Atom/Bluesky/Reddit).

    Attributes:
        name: Human-readable name for the feed
        url: URL of the RSS/Atom feed (None for non-RSS types like Bluesky)
        type: Feed type ('rss', 'atom', 'bluesky', 'reddit')
        enabled: Whether to include this feed in ingestion, defaults to True
        limit: Max items per ingestion run (0 = unlimited), defaults to 0
        tier: Source tier (1=primary/original, 2=secondary/aggregator, 3=echo/mainstream)
        signal: Signal type hint (e.g. 'primary', 'echo', 'commentary', 'community')
        extra: Additional type-specific config (keywords, subreddit, listing, etc.)
    """

    name: str
    url: Optional[str] = None
    type: str = "rss"
    enabled: bool = True
    limit: int = 0
    tier: int = 1
    signal: str = "primary"
    extra: dict = field(default_factory=dict)


def load_feeds(
    config_path: Path,
    include_disabled: bool = False,
) -> list[FeedConfig]:
    """Load feed configurations from a YAML file.

    Args:
        config_path: Path to the feeds.yaml configuration file
        include_disabled: If True, include feeds with enabled=False

    Returns:
        List of FeedConfig objects for configured feeds

    Raises:
        ValueError: If the YAML file contains invalid syntax
    """
    if not config_path.exists():
        return []

    try:
        content = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {config_path}: {e}") from e

    if not data or "feeds" not in data:
        return []

    feeds_data = data["feeds"]
    if not feeds_data:
        return []

    # Keys consumed by FeedConfig directly; everything else goes into extra.
    _KNOWN_KEYS = {"name", "url", "type", "enabled", "limit", "tier", "signal"}

    feeds = []
    for feed_dict in feeds_data:
        extra = {k: v for k, v in feed_dict.items() if k not in _KNOWN_KEYS}
        feed = FeedConfig(
            name=feed_dict["name"],
            url=feed_dict.get("url"),
            type=feed_dict.get("type", "rss"),
            enabled=feed_dict.get("enabled", True),
            limit=feed_dict.get("limit", 0),
            tier=feed_dict.get("tier", 1),
            signal=feed_dict.get("signal", "primary"),
            extra=extra,
        )
        if include_disabled or feed.enabled:
            feeds.append(feed)

    return feeds
