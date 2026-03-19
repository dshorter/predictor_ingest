"""Tests for config loading from feeds.yaml.

Tests written BEFORE implementation (TDD).
"""

import pytest
from pathlib import Path
import tempfile
import os

from config import load_feeds, FeedConfig


class TestLoadFeeds:
    """Test load_feeds() function."""

    def test_loads_feeds_from_yaml(self, tmp_path):
        """Should parse valid YAML and return list of FeedConfig."""
        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds:
  - name: "Test Feed"
    url: "https://example.com/feed.xml"
    type: rss
    enabled: true
""")
        feeds = load_feeds(config_file)
        assert len(feeds) == 1
        assert feeds[0].name == "Test Feed"
        assert feeds[0].url == "https://example.com/feed.xml"
        assert feeds[0].type == "rss"
        assert feeds[0].enabled is True
        assert feeds[0].limit == 0

    def test_loads_feed_with_limit(self, tmp_path):
        """Should parse per-feed limit from YAML."""
        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds:
  - name: "Limited Feed"
    url: "https://example.com/feed.xml"
    limit: 20
  - name: "Unlimited Feed"
    url: "https://example.com/other.xml"
""")
        feeds = load_feeds(config_file)
        assert len(feeds) == 2
        assert feeds[0].limit == 20
        assert feeds[1].limit == 0

    def test_filters_disabled_feeds_by_default(self, tmp_path):
        """Should only return enabled feeds by default."""
        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds:
  - name: "Enabled Feed"
    url: "https://example.com/enabled.xml"
    type: rss
    enabled: true
  - name: "Disabled Feed"
    url: "https://example.com/disabled.xml"
    type: rss
    enabled: false
""")
        feeds = load_feeds(config_file)
        assert len(feeds) == 1
        assert feeds[0].name == "Enabled Feed"

    def test_include_disabled_when_requested(self, tmp_path):
        """Should return all feeds when include_disabled=True."""
        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds:
  - name: "Enabled Feed"
    url: "https://example.com/enabled.xml"
    type: rss
    enabled: true
  - name: "Disabled Feed"
    url: "https://example.com/disabled.xml"
    type: rss
    enabled: false
""")
        feeds = load_feeds(config_file, include_disabled=True)
        assert len(feeds) == 2

    def test_returns_empty_list_for_missing_file(self, tmp_path):
        """Should return empty list if config file doesn't exist."""
        config_file = tmp_path / "nonexistent.yaml"
        feeds = load_feeds(config_file)
        assert feeds == []

    def test_returns_empty_list_for_empty_feeds(self, tmp_path):
        """Should return empty list if feeds key is empty."""
        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds: []
""")
        feeds = load_feeds(config_file)
        assert feeds == []

    def test_returns_empty_list_for_missing_feeds_key(self, tmp_path):
        """Should return empty list if feeds key is missing."""
        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
other_key: value
""")
        feeds = load_feeds(config_file)
        assert feeds == []

    def test_handles_invalid_yaml(self, tmp_path):
        """Should raise ValueError for invalid YAML."""
        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds:
  - name: "Bad YAML
    url: missing quote
""")
        with pytest.raises(ValueError, match="Invalid YAML"):
            load_feeds(config_file)

    def test_default_enabled_true(self, tmp_path):
        """Should default enabled to True if not specified."""
        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds:
  - name: "No enabled field"
    url: "https://example.com/feed.xml"
    type: rss
""")
        feeds = load_feeds(config_file)
        assert len(feeds) == 1
        assert feeds[0].enabled is True

    def test_default_type_rss(self, tmp_path):
        """Should default type to 'rss' if not specified."""
        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds:
  - name: "No type field"
    url: "https://example.com/feed.xml"
    enabled: true
""")
        feeds = load_feeds(config_file)
        assert len(feeds) == 1
        assert feeds[0].type == "rss"


class TestFeedConfig:
    """Test FeedConfig dataclass."""

    def test_required_fields(self):
        """Should require only name; url defaults to None."""
        feed = FeedConfig(name="Test", url="https://example.com/feed.xml")
        assert feed.name == "Test"
        assert feed.url == "https://example.com/feed.xml"

    def test_default_values(self):
        """Should have sensible defaults for optional fields."""
        feed = FeedConfig(name="Test", url="https://example.com/feed.xml")
        assert feed.type == "rss"
        assert feed.enabled is True
        assert feed.limit == 0

    def test_custom_values(self):
        """Should accept custom values for all fields."""
        feed = FeedConfig(
            name="Custom",
            url="https://example.com/atom.xml",
            type="atom",
            enabled=False,
            limit=25,
        )
        assert feed.type == "atom"
        assert feed.enabled is False
        assert feed.limit == 25

    def test_bluesky_feed_no_url(self):
        """Bluesky feeds have no url — should construct without error."""
        feed = FeedConfig(
            name="Bluesky SE Film",
            type="bluesky",
            limit=25,
            extra={"keywords": ["indie film Georgia", "Atlanta film"]},
        )
        assert feed.url is None
        assert feed.extra["keywords"] == ["indie film Georgia", "Atlanta film"]

    def test_reddit_feed_no_url(self):
        """Reddit feeds have no url — should construct without error."""
        feed = FeedConfig(
            name="Reddit r/Filmmakers",
            type="reddit",
            limit=25,
            extra={"subreddit": "Filmmakers", "listing": "new"},
        )
        assert feed.url is None
        assert feed.extra["subreddit"] == "Filmmakers"
        assert feed.extra["listing"] == "new"


class TestLoadFeedsNonRss:
    """Tests for loading non-RSS feed types (bluesky, reddit)."""

    def test_loads_bluesky_feed(self, tmp_path):
        """Should parse a bluesky feed entry without url."""
        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds:
  - name: "Bluesky SE Film"
    type: bluesky
    enabled: true
    limit: 25
    keywords:
      - "indie film Georgia"
      - "Atlanta film production"
""")
        feeds = load_feeds(config_file)
        assert len(feeds) == 1
        assert feeds[0].name == "Bluesky SE Film"
        assert feeds[0].type == "bluesky"
        assert feeds[0].url is None
        assert feeds[0].extra["keywords"] == ["indie film Georgia", "Atlanta film production"]

    def test_loads_reddit_feed(self, tmp_path):
        """Should parse a reddit feed entry without url."""
        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds:
  - name: "Reddit r/Filmmakers"
    type: reddit
    enabled: true
    subreddit: "Filmmakers"
    listing: new
    limit: 25
""")
        feeds = load_feeds(config_file)
        assert len(feeds) == 1
        assert feeds[0].type == "reddit"
        assert feeds[0].url is None
        assert feeds[0].extra["subreddit"] == "Filmmakers"
        assert feeds[0].extra["listing"] == "new"

    def test_mixed_feed_types_load_without_error(self, tmp_path):
        """A config with rss, bluesky, and reddit feeds should all load cleanly."""
        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds:
  - name: "RSS Feed"
    url: "https://example.com/feed.xml"
    type: rss
    enabled: true
  - name: "Bluesky"
    type: bluesky
    enabled: true
    keywords: ["test keyword"]
  - name: "Reddit"
    type: reddit
    enabled: true
    subreddit: "indiefilm"
""")
        feeds = load_feeds(config_file)
        assert len(feeds) == 3
        types = {f.type for f in feeds}
        assert types == {"rss", "bluesky", "reddit"}


class TestLoadFeedsIntegration:
    """Integration test with actual config file."""

    def test_loads_real_config(self):
        """Should load the actual config/feeds.yaml file."""
        config_path = Path(__file__).parent.parent / "config" / "feeds.yaml"
        if config_path.exists():
            feeds = load_feeds(config_path)
            # Should have at least the 7 feeds we defined
            assert len(feeds) >= 7
            # Check known feeds
            names = [f.name for f in feeds]
            assert "arXiv CS.AI" in names
            assert "Anthropic Blog" in names
            # arXiv should have a per-feed limit
            arxiv = next(f for f in feeds if f.name == "arXiv CS.AI")
            assert arxiv.limit == 20
