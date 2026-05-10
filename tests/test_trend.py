"""Tests for trend module - velocity, novelty, and bridge scoring.

Tests trend signal computation for entities per AGENTS.md specification.
"""

from __future__ import annotations

import math
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


class TestTrendDomainProfile:
    """Test that trend module loads configuration from the domain profile."""

    def test_base_relation_loaded(self):
        """Trend module should load base_relation from domain profile."""
        trend = _get_trend_module()
        from domain import get_active_profile
        profile = get_active_profile()
        assert trend._BASE_RELATION == profile["base_relation"]

    def test_trend_weights_loaded(self):
        """Trend module should load trend_weights from domain profile."""
        trend = _get_trend_module()
        from domain import get_active_profile
        profile = get_active_profile()
        assert trend._TREND_WEIGHTS["velocity"] == profile["trend_weights"]["velocity"]
        assert trend._TREND_WEIGHTS["novelty"] == profile["trend_weights"]["novelty"]
        assert trend._TREND_WEIGHTS["activity"] == profile["trend_weights"]["activity"]

    def test_velocity_cap_from_profile(self):
        """Velocity cap should match domain profile."""
        trend = _get_trend_module()
        assert trend._TREND_WEIGHTS["velocity_cap"] == 5.0

    def test_novelty_weights_from_profile(self):
        """Novelty age/rarity weights should match domain profile."""
        trend = _get_trend_module()
        assert trend._TREND_WEIGHTS["novelty_age_weight"] == 0.6
        assert trend._TREND_WEIGHTS["novelty_rarity_weight"] == 0.4


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

        # 3 mentions in last 7 days (meets min-mention gate threshold)
        for i in range(3):
            doc_id = f"recent_{i}"
            conn.execute(
                """
                INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, f"http://example.com/{i}", "Test", f"Recent {i}",
                 _days_ago(i), _days_ago(i), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:openai",
                          "asserted", 1.0, doc_id, "1.0.0")

        # 10 mentions in previous week
        for i in range(10):
            doc_id = f"old_{i}"
            conn.execute(
                """
                INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, f"http://example.com/old/{i}", "Test", f"Old Doc {i}",
                 _days_ago(8 + i), _days_ago(8 + i), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:openai",
                          "asserted", 1.0, doc_id, "1.0.0")

        velocity = trend.compute_velocity(conn, "org:openai")

        # 3/10 = 0.3x (decreasing)
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

        # New entity with mentions should have high velocity, capped at 5.0
        assert velocity > 1.0
        assert velocity <= 5.0

        conn.close()

    def test_velocity_zero_previous_capped(self, tmp_path: Path):
        """Test that velocity is capped at 5.0 for brand-new entities."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:viral", "ViralCo", "Org")

        # 20 recent mentions, no previous — would have been 21.0 uncapped
        for i in range(20):
            doc_id = f"recent_{i}"
            conn.execute(
                """
                INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, f"http://example.com/{i}", "Test", f"Doc {i}",
                 _days_ago(i % 7), _days_ago(i % 7), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:viral",
                          "asserted", 1.0, doc_id, "1.0.0")

        velocity = trend.compute_velocity(conn, "org:viral")

        assert velocity == 5.0  # capped

        conn.close()

    def test_velocity_both_zero(self, tmp_path: Path):
        """Test velocity is 0.0 when no mentions in either window."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "org:ghost", "GhostCo", "Org")

        velocity = trend.compute_velocity(conn, "org:ghost")

        assert velocity == 0.0

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

        # Should be moderate novelty — between brand-new (1.0) and very old (<0.3)
        # Exact value depends on domain's decay_lambda: film (0.07) → ~0.47, AI (0.05) → ~0.53
        assert 0.3 <= novelty <= 0.8

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


class TestTrendingBridgeEntities:
    """Test bridge entity logic in the trending view export.

    When entity suppression removes generic hub nodes, specific trending
    entities can become isolated (degree 0). Bridge entities are non-trending
    entities that reconnect isolated trending nodes to the rest of the graph.
    """

    def _run_export(self, db_path, output_dir, top_n=50):
        """Helper to import and run export_trending."""
        import importlib
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        # Direct import of the function avoids running main()
        from run_trending import export_trending
        return export_trending(db_path, output_dir, top_n)

    def _setup_connected_graph(self, conn):
        """Create a graph where all trending entities are interconnected."""
        insert_entity(conn, "org:openai", "OpenAI", "Org", first_seen=_days_ago(7))
        insert_entity(conn, "model:gpt4", "GPT-4", "Model", first_seen=_days_ago(5))
        insert_entity(conn, "org:anthropic", "Anthropic", "Org", first_seen=_days_ago(7))

        # Add mentions so all are trending
        for eid in ["org:openai", "model:gpt4", "org:anthropic"]:
            for i in range(3):
                doc_id = f"doc_{eid}_{i}"
                conn.execute(
                    """INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (doc_id, f"http://example.com/{doc_id}", "Test", f"Doc {doc_id}",
                     _days_ago(i), _days_ago(i), "extracted")
                )
                insert_relation(conn, f"doc:{doc_id}", "MENTIONS", eid,
                              "asserted", 1.0, doc_id, "1.0.0")

        # Semantic relation connecting openai to gpt4
        insert_relation(conn, "org:openai", "CREATED", "model:gpt4",
                       "asserted", 0.9, "doc_org:openai_0", "1.0.0")

    def test_no_bridges_needed_when_all_connected(self, tmp_path: Path):
        """When all trending entities are already connected, no bridges added."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        self._setup_connected_graph(conn)

        # Add relation between openai and anthropic so all are connected
        insert_relation(conn, "org:openai", "PARTNERED_WITH", "org:anthropic",
                       "asserted", 0.8, "doc_org:openai_0", "1.0.0")
        conn.close()

        output_dir = tmp_path / "graphs"
        self._run_export(db_path, output_dir, top_n=50)

        import json
        with open(output_dir / "trending.json") as f:
            data = json.load(f)

        # No bridge nodes should be present
        bridge_nodes = [n for n in data["elements"]["nodes"] if n["data"].get("bridge")]
        assert len(bridge_nodes) == 0

    def test_bridge_reconnects_isolated_trending(self, tmp_path: Path):
        """A non-trending entity that connects two isolated trending entities
        should be included as a bridge node."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Two trending entities with no direct relation to each other
        insert_entity(conn, "model:gpt4", "GPT-4", "Model", first_seen=_days_ago(5))
        insert_entity(conn, "model:claude", "Claude", "Model", first_seen=_days_ago(5))

        # A non-trending bridge entity (e.g., a tech concept)
        insert_entity(conn, "tech:transformer", "Transformer", "Tech",
                     first_seen=_days_ago(100))

        # Both models are trending (have recent mentions)
        for eid in ["model:gpt4", "model:claude"]:
            for i in range(3):
                doc_id = f"doc_{eid}_{i}"
                conn.execute(
                    """INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (doc_id, f"http://example.com/{doc_id}", "Test", f"Doc {doc_id}",
                     _days_ago(i), _days_ago(i), "extracted")
                )
                insert_relation(conn, f"doc:{doc_id}", "MENTIONS", eid,
                              "asserted", 1.0, doc_id, "1.0.0")

        # Both models connect to the bridge entity (transformer)
        insert_relation(conn, "model:gpt4", "USES_TECH", "tech:transformer",
                       "asserted", 0.9, "doc_model:gpt4_0", "1.0.0")
        insert_relation(conn, "model:claude", "USES_TECH", "tech:transformer",
                       "asserted", 0.9, "doc_model:claude_0", "1.0.0")
        conn.close()

        output_dir = tmp_path / "graphs"
        # top_n=2: only the two models qualify as trending; transformer
        # must be pulled in as a bridge entity to reconnect them.
        self._run_export(db_path, output_dir, top_n=2)

        import json
        with open(output_dir / "trending.json") as f:
            data = json.load(f)

        node_ids = {n["data"]["id"] for n in data["elements"]["nodes"]}
        bridge_nodes = [n for n in data["elements"]["nodes"] if n["data"].get("bridge")]

        # Bridge entity should be included
        assert "tech:transformer" in node_ids
        assert len(bridge_nodes) == 1
        assert bridge_nodes[0]["data"]["id"] == "tech:transformer"

        # Both trending entities should be connected via the bridge
        edge_pairs = {(e["data"]["source"], e["data"]["target"]) for e in data["elements"]["edges"]}
        assert ("model:gpt4", "tech:transformer") in edge_pairs
        assert ("model:claude", "tech:transformer") in edge_pairs

    def test_bridge_not_added_for_single_connection(self, tmp_path: Path):
        """A non-trending entity connecting to only ONE trending entity
        should NOT be included (it doesn't bridge anything)."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "model:gpt4", "GPT-4", "Model", first_seen=_days_ago(5))
        insert_entity(conn, "model:claude", "Claude", "Model", first_seen=_days_ago(5))
        insert_entity(conn, "tech:rlhf", "RLHF", "Tech", first_seen=_days_ago(100))

        # Both trending
        for eid in ["model:gpt4", "model:claude"]:
            for i in range(3):
                doc_id = f"doc_{eid}_{i}"
                conn.execute(
                    """INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (doc_id, f"http://example.com/{doc_id}", "Test", f"Doc {doc_id}",
                     _days_ago(i), _days_ago(i), "extracted")
                )
                insert_relation(conn, f"doc:{doc_id}", "MENTIONS", eid,
                              "asserted", 1.0, doc_id, "1.0.0")

        # RLHF only connects to gpt4, not claude — not a useful bridge
        insert_relation(conn, "model:gpt4", "USES_TECH", "tech:rlhf",
                       "asserted", 0.9, "doc_model:gpt4_0", "1.0.0")
        conn.close()

        output_dir = tmp_path / "graphs"
        # top_n=2: only the two models qualify as trending
        self._run_export(db_path, output_dir, top_n=2)

        import json
        with open(output_dir / "trending.json") as f:
            data = json.load(f)

        node_ids = {n["data"]["id"] for n in data["elements"]["nodes"]}
        # RLHF should NOT be included as a bridge (only touches one trending entity)
        assert "tech:rlhf" not in node_ids

    def test_bridge_data_has_zero_velocity(self, tmp_path: Path):
        """Bridge entities should have velocity=0 and bridge=True marker."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        insert_entity(conn, "model:gpt4", "GPT-4", "Model", first_seen=_days_ago(5))
        insert_entity(conn, "model:claude", "Claude", "Model", first_seen=_days_ago(5))
        insert_entity(conn, "tech:transformer", "Transformer", "Tech",
                     first_seen=_days_ago(100))

        for eid in ["model:gpt4", "model:claude"]:
            for i in range(3):
                doc_id = f"doc_{eid}_{i}"
                conn.execute(
                    """INSERT INTO documents (doc_id, url, source, title, published_at, fetched_at, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (doc_id, f"http://example.com/{doc_id}", "Test", f"Doc {doc_id}",
                     _days_ago(i), _days_ago(i), "extracted")
                )
                insert_relation(conn, f"doc:{doc_id}", "MENTIONS", eid,
                              "asserted", 1.0, doc_id, "1.0.0")

        insert_relation(conn, "model:gpt4", "USES_TECH", "tech:transformer",
                       "asserted", 0.9, "doc_model:gpt4_0", "1.0.0")
        insert_relation(conn, "model:claude", "USES_TECH", "tech:transformer",
                       "asserted", 0.9, "doc_model:claude_0", "1.0.0")
        conn.close()

        output_dir = tmp_path / "graphs"
        # top_n=2: only the two models qualify as trending
        self._run_export(db_path, output_dir, top_n=2)

        import json
        with open(output_dir / "trending.json") as f:
            data = json.load(f)

        bridge_node = next(
            n for n in data["elements"]["nodes"] if n["data"]["id"] == "tech:transformer"
        )
        assert bridge_node["data"]["bridge"] is True
        assert bridge_node["data"]["velocity"] == 0
        assert bridge_node["data"]["trend_score"] == 0


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


# ── Sprint 13 formula tests ──────────────────────────────────────────────


class TestExponentialNoveltyDecay:
    """Tests for 13.6: exponential novelty decay replacing linear decay."""

    def _make_entity_at_age(self, tmp_path, age_days):
        """Create a DB with one entity first_seen `age_days` ago, no mentions."""
        trend = _get_trend_module()
        db_path = tmp_path / f"test_{age_days}.db"
        conn = init_db(db_path)
        insert_entity(conn, "org:test", "Test", "Org",
                      first_seen=_days_ago(age_days))
        return trend, conn

    def test_decay_at_zero_days(self, tmp_path):
        """Age=0: novelty age component should be 1.0 (exp(0) = 1)."""
        trend, conn = self._make_entity_at_age(tmp_path, 0)
        # Override lambda to test with known value
        old_lambda = trend._TREND_WEIGHTS.get("novelty_decay_lambda")
        trend._TREND_WEIGHTS["novelty_decay_lambda"] = 0.05
        try:
            novelty = trend.compute_novelty(conn, "org:test")
            # age_novelty = exp(0) = 1.0, rarity = 1.0 (no mentions, 1 entity)
            assert novelty >= 0.95
        finally:
            if old_lambda is not None:
                trend._TREND_WEIGHTS["novelty_decay_lambda"] = old_lambda
            else:
                trend._TREND_WEIGHTS.pop("novelty_decay_lambda", None)
            conn.close()

    @pytest.mark.parametrize("lambda_val,age,expected_approx", [
        (0.05, 0,   1.0),
        (0.05, 7,   math.exp(-0.05 * 7)),    # ~0.705
        (0.05, 14,  math.exp(-0.05 * 14)),   # ~0.497 (half-life)
        (0.05, 30,  math.exp(-0.05 * 30)),   # ~0.223
        (0.05, 90,  math.exp(-0.05 * 90)),   # ~0.011
        (0.05, 365, math.exp(-0.05 * 365)),  # ~0.000
        (0.02, 14,  math.exp(-0.02 * 14)),   # ~0.756 (slower decay)
        (0.02, 90,  math.exp(-0.02 * 90)),   # ~0.165
        (0.10, 14,  math.exp(-0.10 * 14)),   # ~0.247 (faster decay)
        (0.10, 90,  math.exp(-0.10 * 90)),   # ~0.000
    ])
    def test_decay_curve(self, tmp_path, lambda_val, age, expected_approx):
        """Verify decay values at key ages for multiple λ values."""
        trend, conn = self._make_entity_at_age(tmp_path, age)
        trend._TREND_WEIGHTS["novelty_decay_lambda"] = lambda_val
        try:
            novelty = trend.compute_novelty(conn, "org:test")
            # Age weight = 0.6, rarity weight = 0.4, rarity=1.0 (single entity, 0 mentions)
            age_w = trend._TREND_WEIGHTS.get("novelty_age_weight", 0.6)
            rarity_w = trend._TREND_WEIGHTS.get("novelty_rarity_weight", 0.4)
            expected = age_w * expected_approx + rarity_w * 1.0
            assert abs(novelty - expected) < 0.01, (
                f"λ={lambda_val}, age={age}: expected ~{expected:.3f}, got {novelty:.3f}"
            )
        finally:
            trend._TREND_WEIGHTS.pop("novelty_decay_lambda", None)
            conn.close()

    def test_lambda_zero_no_decay(self, tmp_path):
        """λ=0 means novelty never decays with age."""
        trend, conn = self._make_entity_at_age(tmp_path, 365)
        trend._TREND_WEIGHTS["novelty_decay_lambda"] = 0.0
        try:
            novelty = trend.compute_novelty(conn, "org:test")
            # exp(0) = 1.0 regardless of age
            age_w = trend._TREND_WEIGHTS.get("novelty_age_weight", 0.6)
            rarity_w = trend._TREND_WEIGHTS.get("novelty_rarity_weight", 0.4)
            expected = age_w * 1.0 + rarity_w * 1.0
            assert abs(novelty - expected) < 0.01
        finally:
            trend._TREND_WEIGHTS.pop("novelty_decay_lambda", None)
            conn.close()

    def test_negative_age_clamped(self, tmp_path):
        """Negative age (future first_seen) should clamp to 0, giving novelty=1.0."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        # first_seen is 5 days in the future
        future = (date.today() + timedelta(days=5)).isoformat()
        insert_entity(conn, "org:future", "FutureCo", "Org", first_seen=future)
        trend._TREND_WEIGHTS["novelty_decay_lambda"] = 0.05
        try:
            novelty = trend.compute_novelty(conn, "org:future")
            # max(0, negative_age) = 0, so exp(0) = 1.0
            assert novelty >= 0.95
        finally:
            trend._TREND_WEIGHTS.pop("novelty_decay_lambda", None)
            conn.close()

    def test_monotonically_decreasing_with_age(self, tmp_path):
        """Novelty must decrease monotonically as age increases."""
        trend = _get_trend_module()
        trend._TREND_WEIGHTS["novelty_decay_lambda"] = 0.05
        try:
            prev_novelty = float("inf")
            for age in [0, 1, 7, 14, 30, 60, 90, 180, 365]:
                db_path = tmp_path / f"test_{age}.db"
                conn = init_db(db_path)
                insert_entity(conn, "org:test", "Test", "Org",
                              first_seen=_days_ago(age))
                novelty = trend.compute_novelty(conn, "org:test")
                assert novelty <= prev_novelty, (
                    f"Novelty increased from age={age-1} to age={age}"
                )
                prev_novelty = novelty
                conn.close()
        finally:
            trend._TREND_WEIGHTS.pop("novelty_decay_lambda", None)

    def test_linear_behavior_not_preserved(self, tmp_path):
        """Regression guard: old linear formula must NOT be preserved.

        Linear formula: 1 - (age/365) at age=30 gives ~0.918 for age component.
        Exponential: exp(-0.05 * 30) ≈ 0.223. These are very different.
        """
        trend, conn = self._make_entity_at_age(tmp_path, 30)
        trend._TREND_WEIGHTS["novelty_decay_lambda"] = 0.05
        try:
            novelty = trend.compute_novelty(conn, "org:test")
            # Old linear age component at 30 days: 1 - 30/365 ≈ 0.918
            # Old combined: 0.6 * 0.918 + 0.4 * 1.0 = 0.951
            # New exponential: 0.6 * 0.223 + 0.4 * 1.0 = 0.534
            # These differ by > 0.3, so check we're NOT near the old value
            assert novelty < 0.8, (
                f"Novelty {novelty:.3f} is suspiciously close to old linear value"
            )
        finally:
            trend._TREND_WEIGHTS.pop("novelty_decay_lambda", None)
            conn.close()


class TestCorpusNormalizedRarity:
    """Tests for 13.7: corpus-normalized rarity formula."""

    def _setup_corpus(self, tmp_path, n_entities, mention_counts):
        """Create a corpus with n_entities entities and varying mention counts.

        Args:
            n_entities: Total entities to create
            mention_counts: Dict of {entity_id: n_mentions}. Other entities get 0.
        """
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        for i in range(n_entities):
            eid = f"org:entity_{i}"
            insert_entity(conn, eid, f"Entity {i}", "Org",
                          first_seen=_days_ago(30))

        # Create mentions for specified entities
        doc_counter = 0
        for eid, n_mentions in mention_counts.items():
            for j in range(n_mentions):
                doc_id = f"doc_{doc_counter}"
                conn.execute(
                    """INSERT INTO documents (doc_id, url, source, title,
                       published_at, fetched_at, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (doc_id, f"http://example.com/{doc_counter}", "Test",
                     f"Doc {doc_counter}", _days_ago(j % 30),
                     _days_ago(j % 30), "extracted")
                )
                insert_relation(conn, f"doc:{doc_id}", "MENTIONS", eid,
                                "asserted", 1.0, doc_id, "1.0.0")
                doc_counter += 1

        return trend, conn

    @pytest.mark.parametrize("mentions,corpus_size", [
        (0, 50), (1, 50), (10, 50), (100, 50),
        (0, 500), (1, 500), (10, 500), (100, 500),
        (0, 5000), (1, 5000), (10, 5000), (100, 5000),
    ])
    def test_rarity_at_various_scales(self, tmp_path, mentions, corpus_size):
        """Rarity should be in [0, 1] for all mention/corpus combinations."""
        trend, conn = self._setup_corpus(
            tmp_path, corpus_size,
            {"org:entity_0": mentions}
        )
        try:
            novelty = trend.compute_novelty(conn, "org:entity_0")
            assert 0.0 <= novelty <= 1.0, (
                f"Novelty {novelty} out of range for mentions={mentions}, N={corpus_size}"
            )
        finally:
            conn.close()

    def test_rarity_decreasing_with_mentions(self, tmp_path):
        """At fixed corpus size, rarity should decrease as mentions increase."""
        trend = _get_trend_module()
        prev_novelty = float("inf")
        for mentions in [0, 1, 5, 10, 50]:
            db_path = tmp_path / f"test_{mentions}.db"
            conn = init_db(db_path)
            # 50 entities, target has `mentions` mentions
            for i in range(50):
                insert_entity(conn, f"org:e_{i}", f"E{i}", "Org",
                              first_seen=_days_ago(30))
            for j in range(mentions):
                doc_id = f"doc_{j}"
                conn.execute(
                    """INSERT INTO documents (doc_id, url, source, title,
                       published_at, fetched_at, status) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (doc_id, f"http://x.com/{j}", "T", f"D{j}",
                     _days_ago(j % 30), _days_ago(j % 30), "extracted")
                )
                insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:e_0",
                                "asserted", 1.0, doc_id, "1.0.0")

            novelty = trend.compute_novelty(conn, "org:e_0")
            assert novelty <= prev_novelty + 0.001, (
                f"Novelty increased from mentions={mentions-1} to {mentions}"
            )
            prev_novelty = novelty
            conn.close()

    def test_rarity_increases_with_corpus_size(self, tmp_path):
        """At fixed mentions, rarity should increase with larger corpus."""
        trend = _get_trend_module()
        fixed_mentions = 5
        prev_novelty = -1.0
        for corpus_size in [10, 50, 200]:
            db_path = tmp_path / f"test_{corpus_size}.db"
            conn = init_db(db_path)
            for i in range(corpus_size):
                insert_entity(conn, f"org:e_{i}", f"E{i}", "Org",
                              first_seen=_days_ago(30))
            for j in range(fixed_mentions):
                doc_id = f"doc_{j}"
                conn.execute(
                    """INSERT INTO documents (doc_id, url, source, title,
                       published_at, fetched_at, status) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (doc_id, f"http://x.com/{j}", "T", f"D{j}",
                     _days_ago(j % 30), _days_ago(j % 30), "extracted")
                )
                insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:e_0",
                                "asserted", 1.0, doc_id, "1.0.0")

            novelty = trend.compute_novelty(conn, "org:e_0")
            assert novelty >= prev_novelty - 0.001, (
                f"Novelty decreased from corpus={corpus_size} (should increase)"
            )
            prev_novelty = novelty
            conn.close()

    def test_single_entity_corpus(self, tmp_path):
        """Edge case: corpus with single entity should return valid novelty."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        insert_entity(conn, "org:solo", "Solo", "Org", first_seen=_days_ago(10))
        novelty = trend.compute_novelty(conn, "org:solo")
        assert 0.0 <= novelty <= 1.0
        conn.close()


class TestMinMentionVelocityGate:
    """Tests for 13.8: min-mention velocity gate."""

    def _setup_velocity_test(self, tmp_path, recent_mentions, prev_mentions):
        """Create entity with specified mention distribution."""
        trend = _get_trend_module()
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        insert_entity(conn, "org:test", "Test", "Org")

        for i in range(recent_mentions):
            doc_id = f"recent_{i}"
            conn.execute(
                """INSERT INTO documents (doc_id, url, source, title,
                   published_at, fetched_at, status) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, f"http://x.com/r/{i}", "T", f"R{i}",
                 _days_ago(i % 7), _days_ago(i % 7), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:test",
                            "asserted", 1.0, doc_id, "1.0.0")

        for i in range(prev_mentions):
            doc_id = f"prev_{i}"
            conn.execute(
                """INSERT INTO documents (doc_id, url, source, title,
                   published_at, fetched_at, status) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, f"http://x.com/p/{i}", "T", f"P{i}",
                 _days_ago(8 + i), _days_ago(8 + i), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:test",
                            "asserted", 1.0, doc_id, "1.0.0")

        return trend, conn

    def test_one_mention_gated(self, tmp_path):
        """Entity with 1 recent mention gets velocity 1.0 (gated)."""
        trend, conn = self._setup_velocity_test(tmp_path, 1, 5)
        trend._TREND_WEIGHTS["min_mentions_for_velocity"] = 3
        try:
            velocity = trend.compute_velocity(conn, "org:test")
            assert velocity == 1.0
        finally:
            trend._TREND_WEIGHTS.pop("min_mentions_for_velocity", None)
            conn.close()

    def test_two_mentions_gated(self, tmp_path):
        """Entity with 2 recent mentions gets velocity 1.0 (gated at threshold=3)."""
        trend, conn = self._setup_velocity_test(tmp_path, 2, 5)
        trend._TREND_WEIGHTS["min_mentions_for_velocity"] = 3
        try:
            velocity = trend.compute_velocity(conn, "org:test")
            assert velocity == 1.0
        finally:
            trend._TREND_WEIGHTS.pop("min_mentions_for_velocity", None)
            conn.close()

    def test_three_mentions_not_gated(self, tmp_path):
        """Entity with 3+ recent mentions gets real velocity."""
        trend, conn = self._setup_velocity_test(tmp_path, 3, 6)
        trend._TREND_WEIGHTS["min_mentions_for_velocity"] = 3
        try:
            velocity = trend.compute_velocity(conn, "org:test")
            # 3/6 = 0.5 (real velocity, not gated)
            assert velocity == 0.5
        finally:
            trend._TREND_WEIGHTS.pop("min_mentions_for_velocity", None)
            conn.close()

    def test_threshold_zero_disables_gate(self, tmp_path):
        """Threshold=0 disables the gate entirely."""
        trend, conn = self._setup_velocity_test(tmp_path, 1, 5)
        trend._TREND_WEIGHTS["min_mentions_for_velocity"] = 0
        try:
            velocity = trend.compute_velocity(conn, "org:test")
            # 1/5 = 0.2 (real velocity, gate disabled)
            assert velocity == pytest.approx(0.2)
        finally:
            trend._TREND_WEIGHTS.pop("min_mentions_for_velocity", None)
            conn.close()

    def test_regression_one_to_two_mentions(self, tmp_path):
        """1→2 mention scenario must NOT produce 2.0x velocity when threshold=3."""
        trend, conn = self._setup_velocity_test(tmp_path, 2, 1)
        trend._TREND_WEIGHTS["min_mentions_for_velocity"] = 3
        try:
            velocity = trend.compute_velocity(conn, "org:test")
            # Gated: recent=2 < threshold=3, so velocity=1.0, NOT 2.0
            assert velocity == 1.0
            assert velocity != 2.0
        finally:
            trend._TREND_WEIGHTS.pop("min_mentions_for_velocity", None)
            conn.close()

    def test_zero_mentions_not_gated(self, tmp_path):
        """Zero recent mentions should return 0.0, not get caught by gate."""
        trend, conn = self._setup_velocity_test(tmp_path, 0, 0)
        trend._TREND_WEIGHTS["min_mentions_for_velocity"] = 3
        try:
            velocity = trend.compute_velocity(conn, "org:test")
            assert velocity == 0.0
        finally:
            trend._TREND_WEIGHTS.pop("min_mentions_for_velocity", None)
            conn.close()


class TestCrossDomainFormulas:
    """Cross-domain tests: same formulas with different domain params produce
    qualitatively different but individually correct results."""

    def _score_entity_with_params(self, tmp_path, label, decay_lambda, min_mentions,
                                   age_days, recent_mentions, prev_mentions,
                                   corpus_size=50):
        """Create an entity and score it with specific domain params."""
        trend = _get_trend_module()
        db_path = tmp_path / f"test_{label}.db"
        conn = init_db(db_path)

        for i in range(corpus_size):
            insert_entity(conn, f"org:e_{i}", f"E{i}", "Org",
                          first_seen=_days_ago(age_days if i == 0 else 100))

        for j in range(recent_mentions):
            doc_id = f"recent_{j}"
            conn.execute(
                """INSERT INTO documents (doc_id, url, source, title,
                   published_at, fetched_at, status) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, f"http://x.com/r/{j}", "T", f"R{j}",
                 _days_ago(j % 7), _days_ago(j % 7), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:e_0",
                            "asserted", 1.0, doc_id, "1.0.0")

        for j in range(prev_mentions):
            doc_id = f"prev_{j}"
            conn.execute(
                """INSERT INTO documents (doc_id, url, source, title,
                   published_at, fetched_at, status) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, f"http://x.com/p/{j}", "T", f"P{j}",
                 _days_ago(8 + j), _days_ago(8 + j), "extracted")
            )
            insert_relation(conn, f"doc:{doc_id}", "MENTIONS", "org:e_0",
                            "asserted", 1.0, doc_id, "1.0.0")

        old_lambda = trend._TREND_WEIGHTS.get("novelty_decay_lambda")
        old_min = trend._TREND_WEIGHTS.get("min_mentions_for_velocity")
        trend._TREND_WEIGHTS["novelty_decay_lambda"] = decay_lambda
        trend._TREND_WEIGHTS["min_mentions_for_velocity"] = min_mentions

        try:
            novelty = trend.compute_novelty(conn, "org:e_0")
            velocity = trend.compute_velocity(conn, "org:e_0")
        finally:
            if old_lambda is not None:
                trend._TREND_WEIGHTS["novelty_decay_lambda"] = old_lambda
            else:
                trend._TREND_WEIGHTS.pop("novelty_decay_lambda", None)
            if old_min is not None:
                trend._TREND_WEIGHTS["min_mentions_for_velocity"] = old_min
            else:
                trend._TREND_WEIGHTS.pop("min_mentions_for_velocity", None)
            conn.close()

        return {"novelty": novelty, "velocity": velocity}

    def test_slow_domain_preserves_novelty_longer(self, tmp_path):
        """Semiconductors (λ=0.02) should give higher novelty at 60 days than AI (λ=0.05)."""
        ai = self._score_entity_with_params(
            tmp_path, "ai", decay_lambda=0.05, min_mentions=3,
            age_days=60, recent_mentions=5, prev_mentions=3,
        )
        semi = self._score_entity_with_params(
            tmp_path, "semi", decay_lambda=0.02, min_mentions=3,
            age_days=60, recent_mentions=5, prev_mentions=3,
        )
        assert semi["novelty"] > ai["novelty"], (
            f"Semiconductor novelty ({semi['novelty']:.3f}) should exceed "
            f"AI novelty ({ai['novelty']:.3f}) at 60 days"
        )

    def test_fast_domain_decays_novelty_faster(self, tmp_path):
        """Film (λ=0.07) should give lower novelty at 30 days than biosafety (λ=0.03)."""
        film = self._score_entity_with_params(
            tmp_path, "film", decay_lambda=0.07, min_mentions=2,
            age_days=30, recent_mentions=4, prev_mentions=2,
        )
        bio = self._score_entity_with_params(
            tmp_path, "bio", decay_lambda=0.03, min_mentions=2,
            age_days=30, recent_mentions=4, prev_mentions=2,
        )
        assert film["novelty"] < bio["novelty"], (
            f"Film novelty ({film['novelty']:.3f}) should be below "
            f"biosafety novelty ({bio['novelty']:.3f}) at 30 days"
        )

    def test_velocity_gate_threshold_varies(self, tmp_path):
        """Biosafety (min=2) lets 2-mention entities through;
        AI (min=3) gates them."""
        bio = self._score_entity_with_params(
            tmp_path, "bio", decay_lambda=0.03, min_mentions=2,
            age_days=10, recent_mentions=2, prev_mentions=4,
        )
        ai = self._score_entity_with_params(
            tmp_path, "ai", decay_lambda=0.05, min_mentions=3,
            age_days=10, recent_mentions=2, prev_mentions=4,
        )
        # Biosafety: recent=2 >= min=2, not gated → real velocity 2/4 = 0.5
        assert bio["velocity"] == 0.5
        # AI: recent=2 < min=3, gated → velocity = 1.0
        assert ai["velocity"] == 1.0

    def test_all_domains_produce_valid_scores(self, tmp_path):
        """All four domain configs produce scores in valid ranges."""
        configs = [
            ("ai", 0.05, 3),
            ("biosafety", 0.03, 2),
            ("semiconductors", 0.02, 3),
            ("film", 0.07, 2),
        ]
        for name, lam, min_m in configs:
            scores = self._score_entity_with_params(
                tmp_path, name, decay_lambda=lam, min_mentions=min_m,
                age_days=14, recent_mentions=5, prev_mentions=3,
            )
            assert 0.0 <= scores["novelty"] <= 1.0, f"{name}: novelty out of range"
            assert scores["velocity"] >= 0.0, f"{name}: negative velocity"
