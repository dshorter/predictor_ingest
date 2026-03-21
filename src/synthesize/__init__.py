"""Cross-document synthesis engine.

After individual document extraction, groups documents by shared entities
and asks a specialist LLM to find connections that single-doc extraction
misses — entity corroboration, implicit cross-doc relations, and event
clustering.

Framework-level code: domain-specific synthesis behaviour is controlled
by ``features.cross_document_synthesis`` in domain.yaml and prompt
templates in ``domains/<slug>/prompts/``.

See docs/architecture/domain-separation.md for boundary rules.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

from domain import get_active_profile


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class SynthesisConfig:
    """Settings from domain.yaml ``features.cross_document_synthesis``."""

    enabled: bool = False
    batch_size: int = 5
    min_shared_entities: int = 1
    max_batches_per_run: int = 10
    synthesis_patterns: list[str] = field(
        default_factory=lambda: ["corroboration", "implicit_relations"]
    )

    @classmethod
    def from_profile(cls, profile: dict[str, Any]) -> "SynthesisConfig":
        features = profile.get("features", {})
        cfg = features.get("cross_document_synthesis", {})
        if not isinstance(cfg, dict):
            return cls()
        return cls(
            enabled=bool(cfg.get("enabled", False)),
            batch_size=int(cfg.get("batch_size", 5)),
            min_shared_entities=int(cfg.get("min_shared_entities", 1)),
            max_batches_per_run=int(cfg.get("max_batches_per_run", 10)),
            synthesis_patterns=list(cfg.get("synthesis_patterns",
                                            ["corroboration", "implicit_relations"])),
        )


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DocCluster:
    """A group of documents sharing entities."""

    doc_ids: list[str]
    shared_entity_ids: list[str]
    entity_summaries: dict[str, dict[str, Any]] = field(default_factory=dict)
    existing_relations: list[dict[str, str]] = field(default_factory=list)


@dataclass
class SynthesisResult:
    """Summary of a synthesis run."""

    batches_processed: int = 0
    entities_corroborated: int = 0
    relations_inferred: int = 0
    llm_calls: int = 0
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def ensure_synthesis_tables(conn: sqlite3.Connection) -> None:
    """Create synthesis tracking tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS synthesis_runs (
            synthesis_id TEXT PRIMARY KEY,
            run_date TEXT NOT NULL,
            batch_docs TEXT NOT NULL,
            model TEXT NOT NULL,
            duration_ms INTEGER,
            entities_corroborated INTEGER,
            relations_inferred INTEGER,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_synth_date
            ON synthesis_runs(run_date);
    """)
    conn.commit()

    # Add synthesis_id column to relations if missing
    cols = {row[1] for row in conn.execute("PRAGMA table_info(relations)").fetchall()}
    if "synthesis_id" not in cols:
        conn.execute("ALTER TABLE relations ADD COLUMN synthesis_id TEXT")
        conn.commit()


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def find_document_clusters(
    conn: sqlite3.Connection,
    run_date: str,
    config: SynthesisConfig,
) -> list[DocCluster]:
    """Find groups of today's documents that share entities.

    Clusters documents extracted on ``run_date`` by shared entity mentions.
    """
    # Get documents extracted today (by their MENTIONS relations)
    docs = conn.execute(
        """SELECT DISTINCT r.doc_id
           FROM relations r
           JOIN documents d ON r.doc_id = d.doc_id
           WHERE d.fetched_at >= ? AND r.rel = 'MENTIONS'""",
        (run_date,),
    ).fetchall()
    doc_ids = [d[0] for d in docs if d[0]]

    if not doc_ids:
        return []

    # Build doc → entity mapping
    doc_entities: dict[str, set[str]] = {}
    for doc_id in doc_ids:
        rows = conn.execute(
            """SELECT DISTINCT target_id FROM relations
               WHERE doc_id = ? AND rel = 'MENTIONS'""",
            (doc_id,),
        ).fetchall()
        doc_entities[doc_id] = {r[0] for r in rows}

    # Find overlapping document pairs/groups using greedy clustering
    clusters: list[DocCluster] = []
    used_docs: set[str] = set()

    # Sort docs by entity count descending (start with most connected)
    sorted_docs = sorted(doc_ids, key=lambda d: len(doc_entities.get(d, set())),
                         reverse=True)

    for seed_doc in sorted_docs:
        if seed_doc in used_docs:
            continue
        seed_entities = doc_entities.get(seed_doc, set())
        if not seed_entities:
            continue

        cluster_docs = [seed_doc]
        cluster_entities = set(seed_entities)

        # Find other docs sharing entities with the cluster
        for other_doc in sorted_docs:
            if other_doc in used_docs or other_doc == seed_doc:
                continue
            if len(cluster_docs) >= config.batch_size:
                break

            other_entities = doc_entities.get(other_doc, set())
            shared = cluster_entities & other_entities
            if len(shared) >= config.min_shared_entities:
                cluster_docs.append(other_doc)
                cluster_entities |= other_entities

        # Only keep clusters with 2+ docs
        if len(cluster_docs) >= 2:
            shared = set()
            for d in cluster_docs:
                if not shared:
                    shared = doc_entities.get(d, set()).copy()
                else:
                    shared &= doc_entities.get(d, set())

            clusters.append(DocCluster(
                doc_ids=cluster_docs,
                shared_entity_ids=list(cluster_entities),
            ))
            used_docs.update(cluster_docs)

        if len(clusters) >= config.max_batches_per_run:
            break

    return clusters


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------

def _enrich_cluster(conn: sqlite3.Connection, cluster: DocCluster) -> None:
    """Add entity summaries and existing relations to a cluster."""
    # Entity summaries
    for eid in cluster.shared_entity_ids[:30]:  # cap for prompt length
        row = conn.execute(
            "SELECT name, type FROM entities WHERE entity_id = ?",
            (eid,),
        ).fetchone()
        if row:
            # Count docs mentioning this entity in this cluster
            mention_count = 0
            for doc_id in cluster.doc_ids:
                has = conn.execute(
                    "SELECT 1 FROM relations WHERE doc_id = ? AND target_id = ? AND rel = 'MENTIONS'",
                    (doc_id, eid),
                ).fetchone()
                if has:
                    mention_count += 1

            cluster.entity_summaries[eid] = {
                "name": row[0],
                "type": row[1],
                "docs_mentioning": mention_count,
            }

    # Existing relations between entities in this cluster
    entity_ids = list(cluster.entity_summaries.keys())
    if len(entity_ids) >= 2:
        placeholders = ",".join("?" for _ in entity_ids)
        rels = conn.execute(
            f"""SELECT source_id, rel, target_id, confidence
                FROM relations
                WHERE source_id IN ({placeholders})
                AND target_id IN ({placeholders})
                AND rel != 'MENTIONS'
                LIMIT 50""",
            entity_ids + entity_ids,
        ).fetchall()
        cluster.existing_relations = [
            {"source": r[0], "rel": r[1], "target": r[2], "confidence": r[3]}
            for r in rels
        ]


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def _load_prompt_template(profile: dict[str, Any], filename: str) -> Optional[str]:
    domain_dir: Path = profile.get("_domain_dir", Path("."))
    prompts_dir = domain_dir / profile.get("prompts", {}).get("dir", "prompts")
    path = prompts_dir / filename
    return path.read_text(encoding="utf-8") if path.exists() else None


_DEFAULT_SYSTEM = """\
You are a cross-document synthesis system for a knowledge graph.
Given entity extractions from multiple documents, identify connections
that single-document extraction missed:

1. **Corroboration**: Entities mentioned in 2+ documents (increases confidence)
2. **Implicit relations**: Relationships implied across documents but not stated in any single one
3. **Event clustering**: Multiple documents covering the same event from different angles

Output a JSON object with:
{{
  "corroborated_entities": [{{"entity_id": "...", "name": "...", "doc_count": N, "confidence_boost": 0.0-0.3}}],
  "new_relations": [{{"source": "entity_name", "rel": "RELATION_TYPE", "target": "entity_name", "kind": "inferred", "confidence": 0.0-1.0, "evidence": "cross-doc reasoning"}}]
}}

Entity types: {entity_types}
Relation types: {relation_types}

Only output the JSON — no other text."""

_DEFAULT_USER = """\
Analyze these {doc_count} documents sharing entities. Find cross-document connections.

Entities in this cluster:
{entity_block}

Existing relations:
{relations_block}

Document titles:
{doc_titles}

Respond with JSON containing corroborated_entities and new_relations."""


def build_synthesis_prompt(
    cluster: DocCluster,
    conn: sqlite3.Connection,
    profile: dict[str, Any],
) -> tuple[str, str]:
    """Build prompts for a document cluster."""
    from schema import ENTITY_TYPES, RELATION_TYPES

    system = _load_prompt_template(profile, "synthesis_system.txt")
    if not system:
        system = _DEFAULT_SYSTEM.format(
            entity_types=", ".join(sorted(ENTITY_TYPES)),
            relation_types=", ".join(sorted(RELATION_TYPES)),
        )

    # Build entity block
    entity_lines = []
    for eid, info in cluster.entity_summaries.items():
        entity_lines.append(
            f"  {info['name']} ({info['type']}) — mentioned in {info['docs_mentioning']}/{len(cluster.doc_ids)} docs"
        )
    entity_block = "\n".join(entity_lines) if entity_lines else "(none)"

    # Build relations block
    rel_lines = []
    for r in cluster.existing_relations[:20]:
        rel_lines.append(f"  {r['source']} {r['rel']} {r['target']} (conf: {r['confidence']:.2f})")
    relations_block = "\n".join(rel_lines) if rel_lines else "(none yet)"

    # Doc titles
    doc_titles_list = []
    for doc_id in cluster.doc_ids:
        row = conn.execute("SELECT title FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
        if row and row[0]:
            doc_titles_list.append(f"  - {row[0]}")
    doc_titles = "\n".join(doc_titles_list) if doc_titles_list else "(untitled)"

    user = _load_prompt_template(profile, "synthesis_user.txt")
    if not user:
        user = _DEFAULT_USER

    user_prompt = user.format(
        doc_count=len(cluster.doc_ids),
        entity_block=entity_block,
        relations_block=relations_block,
        doc_titles=doc_titles,
    )

    return system, user_prompt


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str,
) -> tuple[str, int]:
    """Call specialist LLM for synthesis."""
    openai_prefixes = ("gpt-", "o1", "o3", "o4")
    is_openai = any(model.startswith(p) for p in openai_prefixes)

    start = time.time()

    if is_openai:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        client = OpenAI(api_key=api_key)
        # Reasoning models (o-series, nano) don't support temperature
        _reasoning = any(model.startswith(p) for p in ("o1", "o3", "o4")) or "nano" in model
        _temp_kwargs = {} if _reasoning else {"temperature": 0.1}
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **_temp_kwargs,
        )
        text = response.choices[0].message.content or ""
    else:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text

    duration_ms = int((time.time() - start) * 1000)
    return text, duration_ms


def _parse_synthesis_response(text: str) -> dict[str, Any]:
    """Parse LLM synthesis response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_synthesis(
    conn: sqlite3.Connection,
    profile: Optional[dict[str, Any]] = None,
    model: Optional[str] = None,
    run_date: Optional[str] = None,
) -> SynthesisResult:
    """Run cross-document synthesis.

    Args:
        conn: Database connection.
        profile: Domain profile. Uses active if None.
        model: Specialist LLM model for synthesis.
        run_date: ISO date for clustering docs.

    Returns:
        SynthesisResult with counts.
    """
    if profile is None:
        profile = get_active_profile()

    # Default model: PRIMARY_MODEL env var (specialist tier for cross-doc reasoning)
    if model is None:
        model = os.environ.get("PRIMARY_MODEL", "claude-sonnet-4-5-20250929")

    config = SynthesisConfig.from_profile(profile)
    if not config.enabled:
        return SynthesisResult()

    if run_date is None:
        run_date = date.today().isoformat()

    ensure_synthesis_tables(conn)

    start = time.time()
    result = SynthesisResult()

    clusters = find_document_clusters(conn, run_date, config)
    if not clusters:
        return result

    for cluster in clusters:
        _enrich_cluster(conn, cluster)

        try:
            system_prompt, user_prompt = build_synthesis_prompt(cluster, conn, profile)
            response_text, call_ms = _call_llm(system_prompt, user_prompt, model=model)
            result.llm_calls += 1
        except Exception as e:
            print(f"  [synthesize] LLM call failed: {e}")
            continue

        parsed = _parse_synthesis_response(response_text)
        synthesis_id = str(uuid.uuid4())[:8]

        # Process corroborated entities
        corroborated = parsed.get("corroborated_entities", [])
        result.entities_corroborated += len(corroborated)

        # Process new relations
        new_rels = parsed.get("new_relations", [])
        # Resolve entity names to IDs
        name_to_id = {info["name"]: eid for eid, info in cluster.entity_summaries.items()}

        rels_created = 0
        for rel_data in new_rels:
            source_name = rel_data.get("source", "")
            target_name = rel_data.get("target", "")
            rel_type = rel_data.get("rel", "")
            confidence = float(rel_data.get("confidence", 0.5))

            source_id = name_to_id.get(source_name)
            target_id = name_to_id.get(target_name)

            if not source_id or not target_id or not rel_type:
                continue
            if source_id == target_id:
                continue

            # Check if relation already exists
            existing = conn.execute(
                "SELECT 1 FROM relations WHERE source_id = ? AND rel = ? AND target_id = ? LIMIT 1",
                (source_id, rel_type, target_id),
            ).fetchone()
            if existing:
                continue

            conn.execute(
                """INSERT INTO relations
                   (source_id, rel, target_id, kind, confidence,
                    extractor_version, synthesis_id)
                   VALUES (?, ?, ?, 'inferred', ?, 'synthesis-1.0', ?)""",
                (source_id, rel_type, target_id, confidence, synthesis_id),
            )
            rels_created += 1

        result.relations_inferred += rels_created
        result.batches_processed += 1

        # Log the synthesis run
        conn.execute(
            """INSERT INTO synthesis_runs
               (synthesis_id, run_date, batch_docs, model, duration_ms,
                entities_corroborated, relations_inferred)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (synthesis_id, run_date, json.dumps(cluster.doc_ids), model,
             call_ms, len(corroborated), rels_created),
        )
        conn.commit()

    result.duration_ms = int((time.time() - start) * 1000)
    return result
