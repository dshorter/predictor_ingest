"""Trend module for velocity, novelty, and bridge scoring.

Computes lightweight trend signals for entities per AGENTS.md specification.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional


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

    # Count MENTIONS relations where the source doc was published in the window
    cursor = conn.execute(
        """
        SELECT COUNT(*)
        FROM relations r
        JOIN documents d ON r.doc_id = d.doc_id
        WHERE r.target_id = ?
        AND r.rel = 'MENTIONS'
        AND d.published_at >= ?
        AND d.published_at <= ?
        """,
        (entity_id, start_date, end_date)
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
        # Caps at 5.0 so brand-new entities don't dominate with
        # nonsensical percentages (was: recent + 1, unbounded).
        return min(float(recent), 5.0)

    return recent / previous


def compute_novelty(
    conn: sqlite3.Connection,
    entity_id: str,
    max_age_days: int = 365,
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

    # Combine age and rarity (weighted average)
    novelty = 0.6 * age_novelty + 0.4 * rarity

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
        AND rel != 'MENTIONS'
        """,
        (entity_id,)
    )
    outgoing = cursor.fetchone()[0] or 0

    # Count distinct entities connected as target
    cursor = conn.execute(
        """
        SELECT COUNT(DISTINCT source_id)
        FROM relations
        WHERE target_id = ?
        AND rel != 'MENTIONS'
        """,
        (entity_id,)
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

        # Compute combined trend score
        for scores in filtered:
            # Combine velocity, novelty, and recent activity
            velocity_factor = min(scores["velocity"], 5.0) / 5.0  # Cap at 5x
            novelty_factor = scores["novelty"]
            activity_factor = min(scores["mention_count_7d"], 20) / 20.0  # Cap at 20

            scores["trend_score"] = (
                0.4 * velocity_factor +
                0.3 * novelty_factor +
                0.3 * activity_factor
            )

        # Sort by trend score
        filtered.sort(key=lambda x: x["trend_score"], reverse=True)

        return filtered[:limit]

    def export_trending(
        self,
        output_dir: Path,
        limit: int = 50,
    ) -> Path:
        """Export trending entities to JSON file.

        Args:
            output_dir: Directory to write to
            limit: Maximum entities to include

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

        output = {
            "generated_at": date.today().isoformat(),
            "entities": trending,
        }

        output_path = output_dir / "trending.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return output_path
