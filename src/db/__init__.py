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

    On existing databases, runs a one-time migration to remove duplicate
    relations and add the dedup unique index if it doesn't exist yet.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Database connection
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    is_existing = db_path.exists() and db_path.stat().st_size > 0
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # For existing DBs, clean duplicates before applying schema (which
    # includes the UNIQUE INDEX that would fail if dupes exist).
    if is_existing:
        # Check if the dedup index already exists
        idx = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_relations_dedup'"
        ).fetchone()
        if not idx:
            # Check if the relations table exists (it should for any existing DB)
            tbl = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='relations'"
            ).fetchone()
            if tbl:
                removed = deduplicate_relations(conn)
                if removed:
                    print(f"[db] Removed {removed} duplicate relation(s) during migration")

    schema = _schema_path().read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()

    # Migrations: add new columns to existing databases
    if is_existing:
        _migrate_documents_extraction_cols(conn)
        _migrate_documents_source_type(conn)

    return conn


def _migrate_documents_extraction_cols(conn: sqlite3.Connection) -> None:
    """Add extracted_by, quality_score, escalation_failed columns if missing."""
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(documents)").fetchall()
    }
    new_cols = [
        ("extracted_by", "TEXT"),
        ("quality_score", "REAL"),
        ("escalation_failed", "TEXT"),
    ]
    for col_name, col_type in new_cols:
        if col_name not in cols:
            conn.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}")
    conn.commit()


def _migrate_documents_source_type(conn: sqlite3.Connection) -> None:
    """Add source_type column if missing. Defaults to 'rss' for existing rows."""
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(documents)").fetchall()
    }
    if "source_type" not in cols:
        conn.execute(
            "ALTER TABLE documents ADD COLUMN source_type TEXT NOT NULL DEFAULT 'rss'"
        )
        conn.commit()


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


def list_entities_in_date_range(
    conn: sqlite3.Connection,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    entity_type: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List entities active within a date range.

    An entity is "active" if its last_seen >= start_date AND first_seen <= end_date.
    Dates here are article publication dates (see schemas/sqlite.sql).

    Args:
        conn: Database connection
        start_date: Earliest date (ISO), inclusive. None = no lower bound.
        end_date: Latest date (ISO), inclusive. None = no upper bound.
        entity_type: Optional type filter

    Returns:
        List of entity dicts
    """
    clauses: list[str] = []
    params: list[Any] = []

    if start_date:
        clauses.append("(last_seen IS NULL OR last_seen >= ?)")
        params.append(start_date)
    if end_date:
        clauses.append("(first_seen IS NULL OR first_seen <= ?)")
        params.append(end_date)
    if entity_type:
        clauses.append("type = ?")
        params.append(entity_type)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    cursor = conn.execute(f"SELECT * FROM entities{where}", params)

    entities = []
    for row in cursor.fetchall():
        entity = dict(row)
        if entity.get("aliases"):
            entity["aliases"] = json.loads(entity["aliases"])
        if entity.get("external_ids"):
            entity["external_ids"] = json.loads(entity["external_ids"])
        entities.append(entity)
    return entities


def list_relations_in_date_range(
    conn: sqlite3.Connection,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List relations whose source document was published within a date range.

    Joins on documents.published_at (the article publication date).

    Args:
        conn: Database connection
        start_date: Earliest published date (ISO), inclusive. None = no lower bound.
        end_date: Latest published date (ISO), inclusive. None = no upper bound.

    Returns:
        List of relation dicts
    """
    clauses: list[str] = []
    params: list[Any] = []

    if start_date:
        clauses.append("d.published_at >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("d.published_at <= ?")
        params.append(end_date)

    where = (" AND " + " AND ".join(clauses)) if clauses else ""
    query = f"""
        SELECT r.*
        FROM relations r
        JOIN documents d ON r.doc_id = d.doc_id
        WHERE 1=1{where}
    """
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


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
    """Insert a relation between entities, skipping duplicates.

    A relation is considered duplicate if (source_id, rel, target_id, kind,
    doc_id) already exists.  When a duplicate is found the existing
    relation_id is returned and no new row is created.

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
        The relation_id (existing if duplicate, new otherwise)
    """
    # Check for existing duplicate
    existing = conn.execute(
        """SELECT relation_id FROM relations
           WHERE source_id = ? AND rel = ? AND target_id = ? AND kind = ? AND doc_id = ?""",
        (source_id, rel, target_id, kind, doc_id),
    ).fetchone()
    if existing:
        return existing["relation_id"] if isinstance(existing, sqlite3.Row) else existing[0]

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


def deduplicate_relations(conn: sqlite3.Connection) -> int:
    """Remove duplicate relations from the database.

    Keeps the row with the lowest relation_id for each
    (source_id, rel, target_id, kind, doc_id) group.  Also reassigns
    evidence rows from deleted duplicates to the surviving relation.

    Args:
        conn: Database connection

    Returns:
        Number of duplicate rows removed
    """
    # Find relation_ids to keep (one per unique group)
    keep_ids = conn.execute(
        """
        SELECT MIN(relation_id) AS keep_id
        FROM relations
        GROUP BY source_id, rel, target_id, kind, COALESCE(doc_id, '')
        """
    ).fetchall()
    keep_set = {row[0] for row in keep_ids}

    # Find all duplicates (relation_ids NOT in the keep set)
    all_ids = conn.execute("SELECT relation_id FROM relations").fetchall()
    dup_ids = [row[0] for row in all_ids if row[0] not in keep_set]

    if not dup_ids:
        return 0

    # For each duplicate, reassign its evidence to the surviving relation
    for dup_id in dup_ids:
        # Find the group key for this dup
        dup_row = conn.execute(
            "SELECT source_id, rel, target_id, kind, doc_id FROM relations WHERE relation_id = ?",
            (dup_id,),
        ).fetchone()
        if not dup_row:
            continue

        # Find the keep_id for this group
        survivor = conn.execute(
            """SELECT MIN(relation_id) AS keep_id FROM relations
               WHERE source_id = ? AND rel = ? AND target_id = ? AND kind = ?
                     AND COALESCE(doc_id, '') = COALESCE(?, '')""",
            (dup_row[0], dup_row[1], dup_row[2], dup_row[3], dup_row[4]),
        ).fetchone()
        if survivor and survivor[0] != dup_id:
            conn.execute(
                "UPDATE evidence SET relation_id = ? WHERE relation_id = ?",
                (survivor[0], dup_id),
            )

    # Delete duplicates
    placeholders = ",".join("?" for _ in dup_ids)
    conn.execute(f"DELETE FROM relations WHERE relation_id IN ({placeholders})", dup_ids)
    conn.commit()
    return len(dup_ids)


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


