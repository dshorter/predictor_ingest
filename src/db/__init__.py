"""Database operations for entities, relations, and evidence.

Provides CRUD operations for the knowledge graph storage.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional


def _schema_path() -> Path:
    """Return path to SQL schema file."""
    return Path(__file__).resolve().parents[2] / "schemas" / "sqlite.sql"


def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize database with schema.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Database connection
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    schema = _schema_path().read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()

    return conn


def insert_entity(
    conn: sqlite3.Connection,
    entity_id: str,
    name: str,
    entity_type: str,
    aliases: Optional[list[str]] = None,
    external_ids: Optional[dict[str, str]] = None,
    first_seen: Optional[str] = None,
    last_seen: Optional[str] = None,
) -> str:
    """Insert or update an entity.

    On conflict, updates last_seen but preserves first_seen.

    Args:
        conn: Database connection
        entity_id: Canonical entity ID (e.g. "org:openai")
        name: Display name
        entity_type: Entity type (Org, Person, Model, etc.)
        aliases: List of alias strings
        external_ids: Dict of external ID mappings
        first_seen: First observation date (ISO)
        last_seen: Last observation date (ISO)

    Returns:
        The entity_id
    """
    aliases_json = json.dumps(aliases) if aliases else None
    external_ids_json = json.dumps(external_ids) if external_ids else None

    # Check if entity exists
    existing = get_entity(conn, entity_id)

    if existing:
        # Update: preserve first_seen, update last_seen
        conn.execute(
            """
            UPDATE entities
            SET name = COALESCE(?, name),
                type = COALESCE(?, type),
                aliases = COALESCE(?, aliases),
                external_ids = COALESCE(?, external_ids),
                last_seen = COALESCE(?, last_seen)
            WHERE entity_id = ?
            """,
            (name, entity_type, aliases_json, external_ids_json, last_seen, entity_id),
        )
    else:
        # Insert new entity
        conn.execute(
            """
            INSERT INTO entities (entity_id, name, type, aliases, external_ids, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (entity_id, name, entity_type, aliases_json, external_ids_json, first_seen, last_seen),
        )

    conn.commit()
    return entity_id


def get_entity(conn: sqlite3.Connection, entity_id: str) -> Optional[dict[str, Any]]:
    """Get entity by ID.

    Args:
        conn: Database connection
        entity_id: Canonical entity ID

    Returns:
        Entity dict or None if not found
    """
    cursor = conn.execute(
        "SELECT * FROM entities WHERE entity_id = ?",
        (entity_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    entity = dict(row)
    # Parse JSON fields
    if entity.get("aliases"):
        entity["aliases"] = json.loads(entity["aliases"])
    if entity.get("external_ids"):
        entity["external_ids"] = json.loads(entity["external_ids"])
    return entity


def get_entity_by_name(conn: sqlite3.Connection, name: str) -> list[dict[str, Any]]:
    """Find entities by name.

    Args:
        conn: Database connection
        name: Entity name to search for

    Returns:
        List of matching entity dicts
    """
    cursor = conn.execute(
        "SELECT * FROM entities WHERE name = ?",
        (name,),
    )
    entities = []
    for row in cursor.fetchall():
        entity = dict(row)
        if entity.get("aliases"):
            entity["aliases"] = json.loads(entity["aliases"])
        if entity.get("external_ids"):
            entity["external_ids"] = json.loads(entity["external_ids"])
        entities.append(entity)
    return entities


def list_entities(
    conn: sqlite3.Connection,
    entity_type: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List all entities, optionally filtered by type.

    Args:
        conn: Database connection
        entity_type: Optional type filter

    Returns:
        List of entity dicts
    """
    if entity_type:
        cursor = conn.execute(
            "SELECT * FROM entities WHERE type = ?",
            (entity_type,),
        )
    else:
        cursor = conn.execute("SELECT * FROM entities")

    entities = []
    for row in cursor.fetchall():
        entity = dict(row)
        if entity.get("aliases"):
            entity["aliases"] = json.loads(entity["aliases"])
        if entity.get("external_ids"):
            entity["external_ids"] = json.loads(entity["external_ids"])
        entities.append(entity)
    return entities


def insert_relation(
    conn: sqlite3.Connection,
    source_id: str,
    rel: str,
    target_id: str,
    kind: str,
    confidence: float,
    doc_id: str,
    extractor_version: str,
    verb_raw: Optional[str] = None,
    polarity: Optional[str] = None,
    modality: Optional[str] = None,
    time_text: Optional[str] = None,
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
) -> int:
    """Insert a relation between entities.

    Args:
        conn: Database connection
        source_id: Source entity ID
        rel: Relation type (CREATED, MENTIONS, etc.)
        target_id: Target entity ID
        kind: Relation kind (asserted, inferred, hypothesis)
        confidence: Confidence score 0-1
        doc_id: Source document ID
        extractor_version: Version of extractor
        verb_raw: Original verb from text
        polarity: pos, neg, unclear
        modality: observed, planned, speculative
        time_text: Raw time text
        time_start: ISO date for time range start
        time_end: ISO date for time range end

    Returns:
        The relation_id
    """
    cursor = conn.execute(
        """
        INSERT INTO relations (
            source_id, rel, target_id, kind, confidence,
            doc_id, extractor_version, verb_raw, polarity, modality,
            time_text, time_start, time_end
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id, rel, target_id, kind, confidence,
            doc_id, extractor_version, verb_raw, polarity, modality,
            time_text, time_start, time_end,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_relations_for_entity(
    conn: sqlite3.Connection,
    entity_id: str,
) -> list[dict[str, Any]]:
    """Get all relations involving an entity (as source or target).

    Args:
        conn: Database connection
        entity_id: Entity ID to search for

    Returns:
        List of relation dicts
    """
    cursor = conn.execute(
        """
        SELECT * FROM relations
        WHERE source_id = ? OR target_id = ?
        """,
        (entity_id, entity_id),
    )
    return [dict(row) for row in cursor.fetchall()]


def insert_evidence(
    conn: sqlite3.Connection,
    relation_id: int,
    doc_id: str,
    url: str,
    published: Optional[str],
    snippet: str,
    char_start: Optional[int] = None,
    char_end: Optional[int] = None,
) -> int:
    """Insert evidence for a relation.

    Args:
        conn: Database connection
        relation_id: ID of the relation this evidence supports
        doc_id: Source document ID
        url: URL of the source
        published: Publication date (ISO)
        snippet: Evidence text snippet
        char_start: Character offset start
        char_end: Character offset end

    Returns:
        The evidence_id
    """
    cursor = conn.execute(
        """
        INSERT INTO evidence (relation_id, doc_id, url, published, snippet, char_start, char_end)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (relation_id, doc_id, url, published, snippet, char_start, char_end),
    )
    conn.commit()
    return cursor.lastrowid


def add_alias(conn: sqlite3.Connection, alias: str, canonical_id: str) -> None:
    """Add an alias mapping for entity resolution.

    Args:
        conn: Database connection
        alias: Alias string (e.g. "Open AI")
        canonical_id: Canonical entity ID (e.g. "org:openai")
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO entity_aliases (alias, canonical_id)
        VALUES (?, ?)
        """,
        (alias, canonical_id),
    )
    conn.commit()


def resolve_alias(conn: sqlite3.Connection, alias: str) -> Optional[str]:
    """Resolve an alias to canonical entity ID.

    Args:
        conn: Database connection
        alias: Alias to resolve

    Returns:
        Canonical entity ID or None if not found
    """
    cursor = conn.execute(
        "SELECT canonical_id FROM entity_aliases WHERE alias = ?",
        (alias,),
    )
    row = cursor.fetchone()
    return row["canonical_id"] if row else None
