"""Trend module for velocity, novelty, and bridge scoring.

Computes lightweight trend signals for entities per AGENTS.md specification.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from domain import get_active_profile

# Load trend configuration from active domain profile
_profile = get_active_profile()
_BASE_RELATION: str = _profile["base_relation"]
_TREND_WEIGHTS: dict[str, Any] = dict(_profile["trend_weights"])
del _profile


def count_mentions(
    conn: sqlite3.Connection,
    entity_id: str,
    days: int = 7,
    as_of: Optional[date] = None,
) -> int:
    """Count mentions of an entity in the last N days.

    Args:
        conn: Database connection
        entity_id: Entity ID to count mentions for
        days: Number of days to look back
        as_of: Reference date (defaults to today)

    Returns:
        Number of MENTIONS relations in the time period
    """
    if as_of is None:
        as_of = date.today()

    start_date = (as_of - timedelta(days=days)).isoformat()
    end_date = as_of.isoformat()

    # Count base-relation edges where the source doc was published in the window
    cursor = conn.execute(
        """
        SELECT COUNT(*)
        FROM relations r
        JOIN documents d ON r.doc_id = d.doc_id
        WHERE r.target_id = ?
        AND r.rel = ?
        AND d.published_at >= ?
        AND d.published_at <= ?
        """,
        (entity_id, _BASE_RELATION, start_date, end_date)
    )

    row = cursor.fetchone()
    return row[0] if row else 0


def compute_velocity(
    conn: sqlite3.Connection,
    entity_id: str,
    window: int = 7,
    as_of: Optional[date] = None,
) -> float:
    """Compute velocity (ratio of recent to previous mentions).

    Args:
        conn: Database connection
        entity_id: Entity ID
        window: Window size in days
        as_of: Reference date

    Returns:
        Velocity ratio (>1 = increasing, <1 = decreasing)
    """
    if as_of is None:
        as_of = date.today()

    # Recent window
    recent = count_mentions(conn, entity_id, days=window, as_of=as_of)

    # Previous window
    prev_date = as_of - timedelta(days=window)
    previous = count_mentions(conn, entity_id, days=window, as_of=prev_date)

    if previous == 0 and recent == 0:
        return 0.0

    if previous == 0:
        # First appearance — use Laplace-smoothed ratio: recent / 1
        # Caps at velocity_cap so brand-new entities don't dominate with
        # nonsensical percentages (was: recent + 1, unbounded).
        velocity_cap = float(_TREND_WEIGHTS.get("velocity_cap", 5.0))
        return min(float(recent), velocity_cap)

    return recent / previous


def compute_novelty(
    conn: sqlite3.Connection,
    entity_id: str,
    max_age_days: Optional[int] = None,
    as_of: Optional[date] = None,
) -> float:
    """Compute novelty score based on age and rarity.

    Args:
        conn: Database connection
        entity_id: Entity ID
        max_age_days: Age at which novelty reaches minimum
        as_of: Reference date

    Returns:
        Novelty score 0.0 to 1.0
    """
    if max_age_days is None:
        max_age_days = int(_TREND_WEIGHTS.get("max_age_days", 365))
    if as_of is None:
        as_of = date.today()

    # Get entity first_seen date
    cursor = conn.execute(
        "SELECT first_seen FROM entities WHERE entity_id = ?",
        (entity_id,)
    )
    row = cursor.fetchone()

    if not row or not row[0]:
        return 0.5  # Unknown age, medium novelty

    first_seen = row[0]

    # Calculate age in days
    try:
        first_seen_date = date.fromisoformat(first_seen[:10])
        age_days = (as_of - first_seen_date).days
    except (ValueError, TypeError):
        return 0.5

    # Age-based novelty (1.0 for new, decreasing with age)
    age_novelty = max(0.0, 1.0 - (age_days / max_age_days))

    # Rarity factor (fewer mentions = rarer = more novel)
    total_mentions = count_mentions(conn, entity_id, days=max_age_days, as_of=as_of)

    if total_mentions == 0:
        rarity = 1.0
    else:
        # Logarithmic rarity (high mentions = low rarity)
        import math
        rarity = 1.0 / (1.0 + math.log1p(total_mentions))

    # Combine age and rarity (weighted average from domain profile)
    age_w = _TREND_WEIGHTS.get("novelty_age_weight", 0.6)
    rarity_w = _TREND_WEIGHTS.get("novelty_rarity_weight", 0.4)
    novelty = age_w * age_novelty + rarity_w * rarity

    return novelty


def compute_bridge_score(
    conn: sqlite3.Connection,
    entity_id: str,
) -> float:
    """Compute bridge/connector score.

    Measures how much an entity connects different clusters.
    Higher score = entity connects many different entities.

    Args:
        conn: Database connection
        entity_id: Entity ID

    Returns:
        Bridge score (0 = isolated, higher = more connections)
    """
    # Count distinct entities connected as source
    cursor = conn.execute(
        """
        SELECT COUNT(DISTINCT target_id)
        FROM relations
        WHERE source_id = ?
        AND rel != ?
        """,
        (entity_id, _BASE_RELATION)
    )
    outgoing = cursor.fetchone()[0] or 0

    # Count distinct entities connected as target
    cursor = conn.execute(
        """
        SELECT COUNT(DISTINCT source_id)
        FROM relations
        WHERE target_id = ?
        AND rel != ?
        """,
        (entity_id, _BASE_RELATION)
    )
    incoming = cursor.fetchone()[0] or 0

    # Bridge score is product of connections (high when connecting many)
    # Using geometric mean to balance
    import math
    if outgoing == 0 and incoming == 0:
        return 0.0

    return math.sqrt((outgoing + 1) * (incoming + 1)) - 1


class TrendScorer:
    """High-level trend scoring interface.

    Computes and manages trend signals for entities.
    """

    def __init__(self, conn: sqlite3.Connection):
        """Initialize scorer.

        Args:
            conn: Database connection
        """
        self.conn = conn

    def score_entity(self, entity_id: str) -> dict[str, Any]:
        """Compute all trend scores for an entity.

        Args:
            entity_id: Entity to score

        Returns:
            Dict with all trend metrics
        """
        return {
            "entity_id": entity_id,
            "mention_count_7d": count_mentions(self.conn, entity_id, days=7),
            "mention_count_30d": count_mentions(self.conn, entity_id, days=30),
            "velocity": compute_velocity(self.conn, entity_id),
            "novelty": compute_novelty(self.conn, entity_id),
            "bridge_score": compute_bridge_score(self.conn, entity_id),
        }

    def score_all(self) -> dict[str, dict[str, Any]]:
        """Score all entities in database.

        Returns:
            Dict mapping entity_id to scores
        """
        cursor = self.conn.execute("SELECT entity_id FROM entities")
        entities = [row[0] for row in cursor.fetchall()]

        scores = {}
        for entity_id in entities:
            scores[entity_id] = self.score_entity(entity_id)

        return scores

    def get_trending(
        self,
        limit: int = 20,
        min_mentions: int = 0,
    ) -> list[dict[str, Any]]:
        """Get top trending entities.

        Ranks by combined score of velocity, novelty, and mentions.

        Args:
            limit: Maximum entities to return
            min_mentions: Minimum 7d mentions to include

        Returns:
            List of entity scores, sorted by trend score
        """
        all_scores = self.score_all()

        # Filter by minimum mentions
        filtered = [
            s for s in all_scores.values()
            if s["mention_count_7d"] >= min_mentions
        ]

        # Compute combined trend score using domain profile weights
        velocity_cap = float(_TREND_WEIGHTS.get("velocity_cap", 5.0))
        activity_cap = float(_TREND_WEIGHTS.get("activity_cap", 20))
        w_velocity = float(_TREND_WEIGHTS.get("velocity", 0.4))
        w_novelty = float(_TREND_WEIGHTS.get("novelty", 0.3))
        w_activity = float(_TREND_WEIGHTS.get("activity", 0.3))

        for scores in filtered:
            velocity_factor = min(scores["velocity"], velocity_cap) / velocity_cap
            novelty_factor = scores["novelty"]
            activity_factor = min(scores["mention_count_7d"], activity_cap) / activity_cap

            scores["trend_score"] = (
                w_velocity * velocity_factor +
                w_novelty * novelty_factor +
                w_activity * activity_factor
            )

        # Sort by trend score
        filtered.sort(key=lambda x: x["trend_score"], reverse=True)

        top = filtered[:limit]

        # Persist trend scores to trend_history table
        self._save_trend_history(all_scores, top)

        return top

    def _save_trend_history(
        self,
        all_scores: dict[str, dict[str, Any]],
        trending: list[dict[str, Any]],
    ) -> None:
        """Persist trend scores to trend_history table."""
        run_date = date.today().isoformat()
        trending_ids = {s["entity_id"] for s in trending}

        # Only save entities with at least one mention (skip the dormant mass)
        to_save = [
            s for s in all_scores.values()
            if s.get("mention_count_30d", 0) > 0
        ]

        for scores in to_save:
            try:
                self.conn.execute(
                    """INSERT OR REPLACE INTO trend_history
                       (entity_id, run_date, mention_count_7d, mention_count_30d,
                        velocity, novelty, bridge_score, trend_score, in_trending_view)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (scores["entity_id"], run_date,
                     scores.get("mention_count_7d", 0),
                     scores.get("mention_count_30d", 0),
                     scores.get("velocity", 0),
                     scores.get("novelty", 0),
                     scores.get("bridge_score", 0),
                     scores.get("trend_score", 0),
                     1 if scores["entity_id"] in trending_ids else 0),
                )
            except Exception:
                pass  # table may not exist in older DBs; don't block pipeline

        try:
            self.conn.commit()
        except Exception:
            pass

    def export_trending(
        self,
        output_dir: Path,
        limit: int = 50,
        generate_narratives: bool = False,
        narrative_model: str = "gpt-5-nano",
    ) -> Path:
        """Export trending entities to JSON file.

        Args:
            output_dir: Directory to write to
            limit: Maximum entities to include
            generate_narratives: If True, generate "WHY" narratives via LLM
            narrative_model: Model to use for narrative generation

        Returns:
            Path to created file
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        trending = self.get_trending(limit=limit)

        # Enrich with entity info
        for item in trending:
            cursor = self.conn.execute(
                "SELECT name, type FROM entities WHERE entity_id = ?",
                (item["entity_id"],)
            )
            row = cursor.fetchone()
            if row:
                item["name"] = row[0]
                item["type"] = row[1]

        # Generate trend narratives ("What's Hot and WHY")
        if generate_narratives and trending:
            try:
                from trend.narratives import generate_narratives as _gen_narratives
                narratives = _gen_narratives(
                    self.conn, trending, model=narrative_model,
                )
                for item in trending:
                    narrative = narratives.get(item["entity_id"])
                    if narrative:
                        item["narrative"] = narrative
            except Exception as e:
                # Graceful degradation: export without narratives
                print(f"  [trending] Narrative generation failed: {e}")

        output = {
            "generated_at": date.today().isoformat(),
            "entities": trending,
        }

        output_path = output_dir / "trending.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return output_path
