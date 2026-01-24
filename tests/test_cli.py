"""Tests for RSS CLI with config loader integration.

Tests the --config flag that loads feeds from feeds.yaml.

Note: These tests require feedparser to be installed, so they're marked
as network tests (run locally with full dependencies).
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock


@pytest.mark.network
class TestCliConfigIntegration:
    """Test CLI config flag integration."""

    def test_parse_config_flag(self):
        """Should accept --config flag."""
        from ingest.rss import build_arg_parser

        parser = build_arg_parser()
        args = parser.parse_args(["--config", "config/feeds.yaml"])

        assert args.config == "config/feeds.yaml"

    def test_config_and_feed_mutually_optional(self):
        """Should allow --config without --feed."""
        from ingest.rss import build_arg_parser

        parser = build_arg_parser()

        # --config alone should work
        args = parser.parse_args(["--config", "config/feeds.yaml"])
        assert args.config == "config/feeds.yaml"
        assert args.feed is None

    def test_feed_without_config(self):
        """Should allow --feed without --config."""
        from ingest.rss import build_arg_parser

        parser = build_arg_parser()
        args = parser.parse_args(["--feed", "https://example.com/feed.xml"])

        assert args.feed == ["https://example.com/feed.xml"]
        assert args.config is None

    def test_config_and_feed_together(self):
        """Should allow both --config and --feed (feed adds to config)."""
        from ingest.rss import build_arg_parser

        parser = build_arg_parser()
        args = parser.parse_args([
            "--config", "config/feeds.yaml",
            "--feed", "https://extra.com/feed.xml",
        ])

        assert args.config == "config/feeds.yaml"
        assert args.feed == ["https://extra.com/feed.xml"]

    def test_requires_config_or_feed(self):
        """Should require at least --config or --feed."""
        from ingest.rss import build_arg_parser, validate_args

        parser = build_arg_parser()
        args = parser.parse_args([])  # No --config or --feed

        with pytest.raises(SystemExit):
            validate_args(args)


@pytest.mark.network
class TestGetFeedsFromArgs:
    """Test feed URL collection from args."""

    def test_feeds_from_config_only(self, tmp_path):
        """Should load feeds from config file."""
        from ingest.rss import get_feeds_from_args

        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds:
  - name: "Test Feed 1"
    url: "https://example.com/feed1.xml"
    type: rss
    enabled: true
  - name: "Test Feed 2"
    url: "https://example.com/feed2.xml"
    type: rss
    enabled: true
""")

        args = MagicMock()
        args.config = str(config_file)
        args.feed = None

        feeds = get_feeds_from_args(args)

        assert len(feeds) == 2
        assert feeds[0] == ("https://example.com/feed1.xml", "Test Feed 1")
        assert feeds[1] == ("https://example.com/feed2.xml", "Test Feed 2")

    def test_feeds_from_feed_flag_only(self):
        """Should use --feed URLs directly."""
        from ingest.rss import get_feeds_from_args

        args = MagicMock()
        args.config = None
        args.feed = ["https://example.com/feed.xml"]

        feeds = get_feeds_from_args(args)

        assert len(feeds) == 1
        assert feeds[0] == ("https://example.com/feed.xml", None)

    def test_feeds_combined(self, tmp_path):
        """Should combine config feeds with --feed URLs."""
        from ingest.rss import get_feeds_from_args

        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds:
  - name: "Config Feed"
    url: "https://config.com/feed.xml"
    type: rss
    enabled: true
""")

        args = MagicMock()
        args.config = str(config_file)
        args.feed = ["https://extra.com/feed.xml"]

        feeds = get_feeds_from_args(args)

        assert len(feeds) == 2
        # Config feeds first, then CLI feeds
        assert feeds[0] == ("https://config.com/feed.xml", "Config Feed")
        assert feeds[1] == ("https://extra.com/feed.xml", None)

    def test_disabled_feeds_excluded(self, tmp_path):
        """Should exclude disabled feeds from config."""
        from ingest.rss import get_feeds_from_args

        config_file = tmp_path / "feeds.yaml"
        config_file.write_text("""
feeds:
  - name: "Enabled"
    url: "https://enabled.com/feed.xml"
    type: rss
    enabled: true
  - name: "Disabled"
    url: "https://disabled.com/feed.xml"
    type: rss
    enabled: false
""")

        args = MagicMock()
        args.config = str(config_file)
        args.feed = None

        feeds = get_feeds_from_args(args)

        assert len(feeds) == 1
        assert feeds[0][0] == "https://enabled.com/feed.xml"


@pytest.mark.network
class TestDefaultConfigPath:
    """Test default config path behavior."""

    def test_default_config_path(self):
        """--config without value should use default path."""
        from ingest.rss import get_default_config_path

        default_path = get_default_config_path()
        assert default_path.name == "feeds.yaml"
        assert "config" in str(default_path)
