"""Resolve module for entity resolution and alias merging.

Identifies duplicate entities and merges them into canonical forms.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any, Optional

from util import slugify


# Type prefix mapping
TYPE_PREFIXES = {
    "Org": "org",
    "Person": "person",
    "Program": "program",
    "Tool": "tool",
    "Model": "model",
    "Dataset": "dataset",
    "Benchmark": "benchmark",
    "Paper": "paper",
    "Repo": "repo",
    "Document": "doc",
    "Tech": "tech",
    "Topic": "topic",
    "Event": "event",
    "Location": "location",
    "Other": "other",
}


def normalize_name(name: str) -> str:
    """Normalize a name for comparison.

    - Lowercase
    - Strip whitespace
    - Normalize internal whitespace
    - Remove punctuation (except hyphens in the middle)

    Args:
        name: Entity name

    Returns:
        Normalized name
    """
    if not name:
        return ""

    # Lowercase
    name = name.lower()

    # Strip and normalize whitespace
    name = " ".join(name.split())

    # Remove punctuation except letters, numbers, spaces, and hyphens
    name = re.sub(r"[^\w\s-]", "", name)

    # Normalize whitespace again after punctuation removal
    name = " ".join(name.split())

    return name


def name_similarity(name1: str, name2: str) -> float:
    """Compute similarity between two names.

    Uses normalized comparison with various heuristics.

    Args:
        name1: First name
        name2: Second name

    Returns:
        Similarity score 0.0 to 1.0
    """
    # Normalize both names
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)

    # Exact match after normalization
    if norm1 == norm2:
        return 1.0

    # Handle empty strings
    if not norm1 or not norm2:
        return 0.0

    # Remove spaces and compare (handles "OpenAI" vs "Open AI")
    compact1 = norm1.replace(" ", "").replace("-", "")
    compact2 = norm2.replace(" ", "").replace("-", "")
    if compact1 == compact2:
        return 1.0

    # Check if one is substring of other (partial match)
    if norm1 in norm2 or norm2 in norm1:
        shorter = min(len(norm1), len(norm2))
        longer = max(len(norm1), len(norm2))
        return shorter / longer

    # Check word overlap
    words1 = set(norm1.split())
    words2 = set(norm2.split())

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    # Jaccard similarity
    jaccard = len(intersection) / len(union) if union else 0.0

    # Boost if significant overlap
    if len(intersection) >= min(len(words1), len(words2)):
        jaccard = max(jaccard, 0.7)

    return jaccard


def generate_canonical_id(name: str, entity_type: str) -> str:
    """Generate a canonical entity ID.

    Format: {type_prefix}:{slugified_name}

    Args:
        name: Entity name
        entity_type: Entity type (Org, Model, etc.)

    Returns:
        Canonical ID string
    """
    prefix = TYPE_PREFIXES.get(entity_type, "other")
    slug = slugify(name)

    if not slug:
        slug = "unnamed"

    return f"{prefix}:{slug}"


def find_similar_entities(
    conn: sqlite3.Connection,
    name: str,
    entity_type: str,
    threshold: float = 0.8,
) -> list[dict[str, Any]]:
    """Find similar entities in the database.

    Args:
        conn: Database connection
        name: Name to search for
        entity_type: Entity type to match
        threshold: Minimum similarity score

    Returns:
        List of matching entities with similarity scores
    """
    matches = []

    # First check alias table for exact match
    cursor = conn.execute(
        "SELECT canonical_id FROM entity_aliases WHERE alias = ?",
        (name,)
    )
    alias_row = cursor.fetchone()
    if alias_row:
        entity_cursor = conn.execute(
            "SELECT * FROM entities WHERE entity_id = ?",
            (alias_row[0],)
        )
        entity_row = entity_cursor.fetchone()
        if entity_row:
            entity = dict(entity_row)
            if entity.get("aliases"):
                entity["aliases"] = json.loads(entity["aliases"])
            entity["similarity"] = 1.0
            matches.append(entity)
            return matches

    # Search entities of matching type
    cursor = conn.execute(
        "SELECT * FROM entities WHERE type = ?",
        (entity_type,)
    )

    for row in cursor.fetchall():
        entity = dict(row)
        if entity.get("aliases"):
            entity["aliases"] = json.loads(entity["aliases"])

        # Compute similarity with entity name
        sim = name_similarity(name, entity["name"])

        # Also check against aliases
        if entity.get("aliases"):
            for alias in entity["aliases"]:
                alias_sim = name_similarity(name, alias)
                sim = max(sim, alias_sim)

        if sim >= threshold:
            entity["similarity"] = sim
            matches.append(entity)

    # Sort by similarity descending
    matches.sort(key=lambda x: x["similarity"], reverse=True)

    return matches


def merge_entities(
    conn: sqlite3.Connection,
    duplicate_id: str,
    canonical_id: str,
) -> None:
    """Merge a duplicate entity into a canonical entity.

    - Updates relations to point to canonical
    - Creates alias mapping
    - Combines aliases and preserves earliest first_seen
    - Removes duplicate entity

    Args:
        conn: Database connection
        duplicate_id: ID of entity to merge away
        canonical_id: ID of canonical entity to merge into
    """
    # Get both entities
    dup_cursor = conn.execute(
        "SELECT * FROM entities WHERE entity_id = ?",
        (duplicate_id,)
    )
    dup_row = dup_cursor.fetchone()

    can_cursor = conn.execute(
        "SELECT * FROM entities WHERE entity_id = ?",
        (canonical_id,)
    )
    can_row = can_cursor.fetchone()

    if not dup_row or not can_row:
        return

    dup_entity = dict(dup_row)
    can_entity = dict(can_row)

    # Parse JSON fields
    dup_aliases = json.loads(dup_entity["aliases"]) if dup_entity.get("aliases") else []
    can_aliases = json.loads(can_entity["aliases"]) if can_entity.get("aliases") else []

    # Combine aliases (add duplicate's name and aliases)
    new_aliases = list(set(can_aliases + dup_aliases + [dup_entity["name"]]))

    # Determine earliest first_seen and latest last_seen
    first_seen = can_entity.get("first_seen")
    if dup_entity.get("first_seen"):
        if not first_seen or dup_entity["first_seen"] < first_seen:
            first_seen = dup_entity["first_seen"]

    last_seen = can_entity.get("last_seen")
    if dup_entity.get("last_seen"):
        if not last_seen or dup_entity["last_seen"] > last_seen:
            last_seen = dup_entity["last_seen"]

    # Update canonical entity
    conn.execute(
        """
        UPDATE entities
        SET aliases = ?, first_seen = ?, last_seen = ?
        WHERE entity_id = ?
        """,
        (json.dumps(new_aliases), first_seen, last_seen, canonical_id)
    )

    # Update relations: change source_id
    conn.execute(
        """
        UPDATE relations
        SET source_id = ?
        WHERE source_id = ?
        """,
        (canonical_id, duplicate_id)
    )

    # Update relations: change target_id
    conn.execute(
        """
        UPDATE relations
        SET target_id = ?
        WHERE target_id = ?
        """,
        (canonical_id, duplicate_id)
    )

    # Add alias mapping for the duplicate's name
    conn.execute(
        """
        INSERT OR REPLACE INTO entity_aliases (alias, canonical_id)
        VALUES (?, ?)
        """,
        (dup_entity["name"], canonical_id)
    )

    # Delete the duplicate entity
    conn.execute(
        "DELETE FROM entities WHERE entity_id = ?",
        (duplicate_id,)
    )

    conn.commit()


class EntityResolver:
    """High-level entity resolution interface.

    Provides methods to resolve entity names to canonical IDs,
    create new entities, and run batch resolution.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        threshold: float = 0.85,
    ):
        """Initialize resolver.

        Args:
            conn: Database connection
            threshold: Minimum similarity score for matching
        """
        self.conn = conn
        self.threshold = threshold

    def resolve(
        self,
        name: str,
        entity_type: str,
    ) -> Optional[str]:
        """Resolve a name to an existing entity ID.

        Args:
            name: Entity name
            entity_type: Entity type

        Returns:
            Canonical entity ID or None if no match
        """
        matches = find_similar_entities(
            self.conn, name, entity_type, self.threshold
        )

        if matches:
            return matches[0]["entity_id"]

        return None

    def resolve_or_create(
        self,
        name: str,
        entity_type: str,
        **kwargs,
    ) -> str:
        """Resolve to existing entity or create new one.

        Args:
            name: Entity name
            entity_type: Entity type
            **kwargs: Additional entity fields

        Returns:
            Entity ID (existing or newly created)
        """
        # Try to resolve first
        existing = self.resolve(name, entity_type)
        if existing:
            # Update last_seen if provided
            if kwargs.get("last_seen"):
                self.conn.execute(
                    "UPDATE entities SET last_seen = ? WHERE entity_id = ? AND (last_seen IS NULL OR last_seen < ?)",
                    (kwargs["last_seen"], existing, kwargs["last_seen"]),
                )
                self.conn.commit()
            return existing

        # Create new entity
        from db import insert_entity

        entity_id = generate_canonical_id(name, entity_type)

        # Handle ID collision by appending counter
        base_id = entity_id
        counter = 1
        while True:
            cursor = self.conn.execute(
                "SELECT 1 FROM entities WHERE entity_id = ?",
                (entity_id,)
            )
            if cursor.fetchone() is None:
                break
            counter += 1
            entity_id = f"{base_id}_{counter}"

        insert_entity(
            self.conn,
            entity_id=entity_id,
            name=name,
            entity_type=entity_type,
            **kwargs,
        )

        return entity_id

    def resolve_extraction(
        self,
        extraction: dict[str, Any],
        observed_date: Optional[str] = None,
    ) -> dict[str, str]:
        """Resolve all entities in an extraction.

        Args:
            extraction: Extraction dict with entities list
            observed_date: The article's PUBLISHED date (ISO), used for entity
                first_seen/last_seen. Must be the publication date, not the
                pipeline fetch date, so that trend scoring and date filtering
                reflect real-world timing rather than crawl timing.

        Returns:
            Mapping of entity names to resolved IDs
        """
        resolved = {}

        for entity in extraction.get("entities", []):
            name = entity["name"]
            entity_type = entity["type"]

            entity_id = self.resolve_or_create(
                name, entity_type,
                first_seen=observed_date,
                last_seen=observed_date,
            )
            resolved[name] = entity_id

        return resolved

    def run_resolution_pass(self) -> dict[str, int]:
        """Run resolution on all entities in database.

        Finds and merges duplicate entities.

        Returns:
            Statistics dict with counts
        """
        stats = {
            "entities_checked": 0,
            "merges_performed": 0,
        }

        # Get all entities grouped by type
        cursor = self.conn.execute(
            "SELECT entity_id, name, type FROM entities ORDER BY type, first_seen"
        )
        entities = [dict(row) for row in cursor.fetchall()]

        processed = set()

        for entity in entities:
            stats["entities_checked"] += 1

            if entity["entity_id"] in processed:
                continue

            # Find similar entities of same type
            matches = find_similar_entities(
                self.conn,
                entity["name"],
                entity["type"],
                self.threshold,
            )

            # Filter to only other entities (not self)
            duplicates = [
                m for m in matches
                if m["entity_id"] != entity["entity_id"]
                and m["entity_id"] not in processed
            ]

            # Merge duplicates into this entity (earliest one wins as canonical)
            for dup in duplicates:
                merge_entities(self.conn, dup["entity_id"], entity["entity_id"])
                processed.add(dup["entity_id"])
                stats["merges_performed"] += 1

            processed.add(entity["entity_id"])

        return stats
