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


@dataclass
class FeedConfig:
    """Configuration for a single RSS/Atom feed.

    Attributes:
        name: Human-readable name for the feed
        url: URL of the RSS/Atom feed
        type: Feed type ('rss' or 'atom'), defaults to 'rss'
        enabled: Whether to include this feed in ingestion, defaults to True
        limit: Max items per ingestion run (0 = unlimited), defaults to 0
    """

    name: str
    url: str
    type: str = "rss"
    enabled: bool = True
    limit: int = 0


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

    feeds = []
    for feed_dict in feeds_data:
        feed = FeedConfig(
            name=feed_dict["name"],
            url=feed_dict["url"],
            type=feed_dict.get("type", "rss"),
            enabled=feed_dict.get("enabled", True),
            limit=feed_dict.get("limit", 0),
        )
        if include_disabled or feed.enabled:
            feeds.append(feed)

    return feeds
