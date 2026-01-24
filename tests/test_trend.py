"""Tests for trend module - velocity, novelty, and bridge scoring.

Tests trend signal computation for entities per AGENTS.md specification.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from db import init_db, insert_entity, insert_relation


def _get_trend_module():
    """Lazy import of trend module."""
    import trend
    return trend


def _days_ago(n: int) -> str:
    """Return ISO date string for n days ago."""
    return (date.today() - timedelta(days=n)).isoformat()


class TestMentionCount:
    """Test mention counting functionality."""

    def test_count_mentions_7d(self, tmp_path: Path):
        """Test counting mentions in last 7 days."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Create entity
        insert_entity(conn, "org:openai", "OpenAI", "Org")

        # Create documents with mentions at various dates
        for i in range(10):
            doc_id = f"doc_{i}"
            days = i * 2  # 0, 2, 4, 6, 8, 10, 12, 14, 16, 18 days ago
            conn.execute(
                """
                INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, f"http://example.com/{i}", "Test", f"Doc {i}",
                 _days_ago(days), _days_ago(days), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:openai",
                          "asserted", 1.0, doc_id, "1.0.0")

        count = trend.count_mentions(conn, "org:openai", days=7)

        # Docs at 0, 2, 4, 6 days ago = 4 mentions
        assert count == 4

        conn.close()

    def test_count_mentions_30d(self, tmp_path: Path):
        """Test counting mentions in last 30 days."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")

        # Create 10 docs over various dates
        for i in range(10):
            doc_id = f"doc_{i}"
            days = i * 5  # 0, 5, 10, 15, 20, 25, 30, 35, 40, 45 days ago
            conn.execute(
                """
                INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, f"http://example.com/{i}", "Test", f"Doc {i}",
                 _days_ago(days), _days_ago(days), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:openai",
                          "asserted", 1.0, doc_id, "1.0.0")

        count = trend.count_mentions(conn, "org:openai", days=30)

        # Docs at 0, 5, 10, 15, 20, 25, 30 days ago = 7 mentions
        assert count == 7

        conn.close()

    def test_count_mentions_no_mentions(self, tmp_path: Path):
        """Test entity with no mentions."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")

        count = trend.count_mentions(conn, "org:openai", days=7)

        assert count == 0

        conn.close()


class TestVelocity:
    """Test velocity scoring."""

    def test_velocity_increasing(self, tmp_path: Path):
        """Test velocity for entity with increasing mentions."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")

        # 5 mentions in last 7 days
        for i in range(5):
            doc_id = f"recent_{i}"
            conn.execute(
                """
                INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, f"http://example.com/{i}", "Test", f"Doc {i}",
                 _days_ago(i), _days_ago(i), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:openai",
                          "asserted", 1.0, doc_id, "1.0.0")

        # 2 mentions in previous 7 days (8-14 days ago)
        for i in range(2):
            doc_id = f"old_{i}"
            conn.execute(
                """
                INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, f"http://example.com/old/{i}", "Test", f"Old Doc {i}",
                 _days_ago(10 + i), _days_ago(10 + i), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:openai",
                          "asserted", 1.0, doc_id, "1.0.0")

        velocity = trend.compute_velocity(conn, "org:openai")

        # 5/2 = 2.5x increase
        assert velocity > 1.0

        conn.close()

    def test_velocity_decreasing(self, tmp_path: Path):
        """Test velocity for entity with decreasing mentions."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")

        # 1 mention in last 7 days
        conn.execute(
            """
            INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("recent_1", "http://example.com/1", "Test", "Recent",
             _days_ago(1), _days_ago(1), "extracted")
        )
        insert_relation(conn, "doc:recent_1", "MENTIONS", "org:openai",
                      "asserted", 1.0, "recent_1", "1.0.0")

        # 5 mentions in previous week
        for i in range(5):
            doc_id = f"old_{i}"
            conn.execute(
                """
                INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, f"http://example.com/old/{i}", "Test", f"Old Doc {i}",
                 _days_ago(10 + i), _days_ago(10 + i), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:openai",
                          "asserted", 1.0, doc_id, "1.0.0")

        velocity = trend.compute_velocity(conn, "org:openai")

        # 1/5 = 0.2x (decreasing)
        assert velocity < 1.0

        conn.close()

    def test_velocity_zero_previous(self, tmp_path: Path):
        """Test velocity when no previous mentions (new entity)."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")

        # Only recent mentions
        for i in range(3):
            doc_id = f"recent_{i}"
            conn.execute(
                """
                INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, f"http://example.com/{i}", "Test", f"Doc {i}",
                 _days_ago(i), _days_ago(i), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:openai",
                          "asserted", 1.0, doc_id, "1.0.0")

        velocity = trend.compute_velocity(conn, "org:openai")

        # New entity with mentions should have high velocity
        assert velocity > 1.0

        conn.close()


class TestNovelty:
    """Test novelty scoring."""

    def test_novelty_new_entity(self, tmp_path: Path):
        """Test novelty for newly discovered entity."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Entity first seen today
        insert_entity(conn, "org:newco", "NewCo", "Org",
                     first_seen=_days_ago(0))

        novelty = trend.compute_novelty(conn, "org:newco")

        # Should be high novelty
        assert novelty >= 0.9

        conn.close()

    def test_novelty_old_entity(self, tmp_path: Path):
        """Test novelty for long-known entity."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Entity first seen 365 days ago
        insert_entity(conn, "org:oldco", "OldCo", "Org",
                     first_seen=_days_ago(365))

        novelty = trend.compute_novelty(conn, "org:oldco")

        # Should be lower novelty (age=0, but gets rarity boost)
        assert novelty < 0.5

        conn.close()

    def test_novelty_medium_age(self, tmp_path: Path):
        """Test novelty for moderately aged entity."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Entity first seen 30 days ago
        insert_entity(conn, "org:midco", "MidCo", "Org",
                     first_seen=_days_ago(30))

        novelty = trend.compute_novelty(conn, "org:midco")

        # Should be high-medium novelty (30 days is still fairly new)
        assert 0.5 <= novelty <= 1.0

        conn.close()

    def test_novelty_includes_rarity(self, tmp_path: Path):
        """Test that novelty considers mention rarity."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Two entities, same age
        insert_entity(conn, "org:rare", "RareCo", "Org",
                     first_seen=_days_ago(30))
        insert_entity(conn, "org:common", "CommonCo", "Org",
                     first_seen=_days_ago(30))

        # CommonCo has many mentions
        for i in range(20):
            doc_id = f"doc_{i}"
            conn.execute(
                """
                INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, f"http://example.com/{i}", "Test", f"Doc {i}",
                 _days_ago(i % 30), _days_ago(i % 30), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:common",
                          "asserted", 1.0, doc_id, "1.0.0")

        # RareCo has few mentions
        conn.execute(
            """
            INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("rare_doc", "http://example.com/rare", "Test", "Rare Doc",
             _days_ago(1), _days_ago(1), "extracted")
        )
        insert_relation(conn, "doc:rare_doc", "MENTIONS", "org:rare",
                      "asserted", 1.0, "rare_doc", "1.0.0")

        rare_novelty = trend.compute_novelty(conn, "org:rare")
        common_novelty = trend.compute_novelty(conn, "org:common")

        # Rare entity should have higher novelty (less well-known)
        assert rare_novelty >= common_novelty

        conn.close()


class TestBridgeScore:
    """Test bridge/connector scoring."""

    def test_bridge_score_connector(self, tmp_path: Path):
        """Test bridge score for entity connecting clusters."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Create entities
        insert_entity(conn, "tech:transformer", "Transformer", "Tech")
        insert_entity(conn, "model:gpt4", "GPT-4", "Model")
        insert_entity(conn, "model:gemini", "Gemini", "Model")
        insert_entity(conn, "org:openai", "OpenAI", "Org")
        insert_entity(conn, "org:google", "Google", "Org")

        # Transformer connects two model ecosystems
        insert_relation(conn, "model:gpt4", "USES_TECH", "tech:transformer",
                       "asserted", 1.0, "doc1", "1.0.0")
        insert_relation(conn, "model:gemini", "USES_TECH", "tech:transformer",
                       "asserted", 1.0, "doc2", "1.0.0")
        insert_relation(conn, "org:openai", "CREATED", "model:gpt4",
                       "asserted", 1.0, "doc1", "1.0.0")
        insert_relation(conn, "org:google", "CREATED", "model:gemini",
                       "asserted", 1.0, "doc2", "1.0.0")

        bridge = trend.compute_bridge_score(conn, "tech:transformer")

        # Transformer connects multiple entities
        assert bridge > 0

        conn.close()

    def test_bridge_score_isolated(self, tmp_path: Path):
        """Test bridge score for isolated entity."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:isolated", "Isolated", "Org")

        bridge = trend.compute_bridge_score(conn, "org:isolated")

        # No connections = no bridge value
        assert bridge == 0

        conn.close()


class TestTrendScorer:
    """Test the TrendScorer class."""

    def test_scorer_initialization(self, tmp_path: Path):
        """Test scorer initialization."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        scorer = trend.TrendScorer(conn)
        assert scorer.conn is not None

        conn.close()

    def test_score_entity(self, tmp_path: Path):
        """Test scoring a single entity."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org",
                     first_seen=_days_ago(30))

        # Add some mentions
        for i in range(3):
            doc_id = f"doc_{i}"
            conn.execute(
                """
                INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, f"http://example.com/{i}", "Test", f"Doc {i}",
                 _days_ago(i), _days_ago(i), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:openai",
                          "asserted", 1.0, doc_id, "1.0.0")

        scorer = trend.TrendScorer(conn)
        scores = scorer.score_entity("org:openai")

        assert "mention_count_7d" in scores
        assert "mention_count_30d" in scores
        assert "velocity" in scores
        assert "novelty" in scores
        assert "bridge_score" in scores

        assert scores["mention_count_7d"] == 3

        conn.close()

    def test_score_all_entities(self, tmp_path: Path):
        """Test scoring all entities."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org")
        insert_entity(conn, "model:gpt4", "GPT-4", "Model")

        scorer = trend.TrendScorer(conn)
        all_scores = scorer.score_all()

        assert len(all_scores) == 2
        assert "org:openai" in all_scores
        assert "model:gpt4" in all_scores

        conn.close()

    def test_get_trending(self, tmp_path: Path):
        """Test getting top trending entities."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Create entities with different activity levels
        insert_entity(conn, "org:hot", "HotCo", "Org", first_seen=_days_ago(7))
        insert_entity(conn, "org:cold", "ColdCo", "Org", first_seen=_days_ago(365))

        # Hot entity has recent mentions
        for i in range(5):
            doc_id = f"hot_{i}"
            conn.execute(
                """
                INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, f"http://example.com/{i}", "Test", f"Doc {i}",
                 _days_ago(i), _days_ago(i), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:hot",
                          "asserted", 1.0, doc_id, "1.0.0")

        scorer = trend.TrendScorer(conn)
        trending = scorer.get_trending(limit=5)

        # Hot entity should rank higher
        assert len(trending) >= 1
        assert trending[0]["entity_id"] == "org:hot"

        conn.close()


class TestTrendExport:
    """Test exporting trending data."""

    def test_export_trending_json(self, tmp_path: Path):
        """Test exporting trending entities to JSON."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:openai", "OpenAI", "Org", first_seen=_days_ago(7))

        # Add mentions
        for i in range(3):
            doc_id = f"doc_{i}"
            conn.execute(
                """
                INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, f"http://example.com/{i}", "Test", f"Doc {i}",
                 _days_ago(i), _days_ago(i), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:openai",
                          "asserted", 1.0, doc_id, "1.0.0")

        scorer = trend.TrendScorer(conn)
        output_dir = tmp_path / "graphs" / "2026-01-24"

        scorer.export_trending(output_dir, limit=10)

        output_path = output_dir / "trending.json"
        assert output_path.exists()

        import json
        with open(output_path) as f:
            data = json.load(f)

        assert "entities" in data
        assert len(data["entities"]) >= 1
        assert data["entities"][0]["entity_id"] == "org:openai"

        conn.close()
