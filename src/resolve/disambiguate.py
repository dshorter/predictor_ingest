"""LLM-powered entity disambiguation.

Extends the fuzzy-matching resolution pass with an LLM step for
"gray zone" entity pairs — those whose string similarity falls between
a configurable lower bound and the auto-merge threshold.

Framework-level code: domain-specific behaviour is controlled entirely
by the ``features.llm_disambiguation`` section of domain.yaml and the
prompt templates in ``domains/<slug>/prompts/``.

See docs/architecture/domain-separation.md for boundary rules.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from domain import get_active_profile
from resolve import find_similar_entities, merge_entities, name_similarity


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class DisambiguationConfig:
    """Settings loaded from domain.yaml ``features.llm_disambiguation``."""

    enabled: bool = False
    similarity_lower_bound: float = 0.40
    similarity_upper_bound: float = 0.85
    max_pairs_per_run: int = 50
    batch_size: int = 15
    entity_types_to_disambiguate: list[str] = field(default_factory=list)
    # context_window_docs: how many recent docs to include per entity
    context_window_docs: int = 5

    @classmethod
    def from_profile(cls, profile: dict[str, Any]) -> "DisambiguationConfig":
        """Build config from a domain profile dict."""
        features = profile.get("features", {})
        cfg = features.get("llm_disambiguation", {})
        if not isinstance(cfg, dict):
            return cls()
        return cls(
            enabled=bool(cfg.get("enabled", False)),
            similarity_lower_bound=float(cfg.get("similarity_lower_bound", 0.40)),
            similarity_upper_bound=float(cfg.get("similarity_upper_bound", 0.85)),
            max_pairs_per_run=int(cfg.get("max_pairs_per_run", 50)),
            batch_size=int(cfg.get("batch_size", 15)),
            entity_types_to_disambiguate=list(cfg.get("entity_types_to_disambiguate", [])),
            context_window_docs=int(cfg.get("context_window_docs", 5)),
        )


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EntityPair:
    """A candidate pair for LLM disambiguation."""

    entity_a_id: str
    entity_a_name: str
    entity_b_id: str
    entity_b_name: str
    entity_type: str
    similarity: float
    context_a: str = ""
    context_b: str = ""


@dataclass
class Decision:
    """LLM verdict for an entity pair."""

    entity_a_id: str
    entity_b_id: str
    verdict: str  # "merge", "keep_separate", "uncertain"
    confidence: float = 0.0
    reason: str = ""


@dataclass
class DisambiguationResult:
    """Summary of a disambiguation run."""

    pairs_evaluated: int = 0
    merges_performed: int = 0
    kept_separate: int = 0
    uncertain: int = 0
    llm_calls: int = 0
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def ensure_disambiguation_table(conn: sqlite3.Connection) -> None:
    """Create the disambiguation_decisions table if it doesn't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS disambiguation_decisions (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_a_id TEXT NOT NULL,
            entity_b_id TEXT NOT NULL,
            similarity_score REAL,
            llm_verdict TEXT NOT NULL,
            llm_model TEXT,
            confidence REAL,
            reason TEXT,
            run_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_disambig_pair
            ON disambiguation_decisions(entity_a_id, entity_b_id);
        CREATE INDEX IF NOT EXISTS idx_disambig_date
            ON disambiguation_decisions(run_date);
    """)
    conn.commit()


def _pair_already_decided(
    conn: sqlite3.Connection,
    entity_a_id: str,
    entity_b_id: str,
) -> Optional[str]:
    """Check if a pair has a cached decision. Returns verdict or None."""
    # Normalise ordering so (A,B) and (B,A) hit the same row.
    a, b = sorted([entity_a_id, entity_b_id])
    row = conn.execute(
        """SELECT llm_verdict FROM disambiguation_decisions
           WHERE entity_a_id = ? AND entity_b_id = ?
           ORDER BY created_at DESC LIMIT 1""",
        (a, b),
    ).fetchone()
    return row[0] if row else None


def _save_decision(
    conn: sqlite3.Connection,
    decision: Decision,
    model: str,
    run_date: str,
    similarity: float,
) -> None:
    """Persist a disambiguation decision."""
    a, b = sorted([decision.entity_a_id, decision.entity_b_id])
    conn.execute(
        """INSERT INTO disambiguation_decisions
           (entity_a_id, entity_b_id, similarity_score, llm_verdict,
            llm_model, confidence, reason, run_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (a, b, similarity, decision.verdict, model,
         decision.confidence, decision.reason, run_date),
    )


# ---------------------------------------------------------------------------
# Context gathering
# ---------------------------------------------------------------------------

def _entity_context(
    conn: sqlite3.Connection,
    entity_id: str,
    max_docs: int = 5,
) -> str:
    """Build a text context block for an entity (for the LLM prompt)."""
    # Fetch entity basics
    row = conn.execute(
        "SELECT name, type, aliases FROM entities WHERE entity_id = ?",
        (entity_id,),
    ).fetchone()
    if not row:
        return f"[Entity {entity_id} not found]"

    name = row[0]
    etype = row[1]
    aliases = json.loads(row[2]) if row[2] else []

    parts = [f"Name: {name}", f"Type: {etype}"]
    if aliases:
        parts.append(f"Aliases: {', '.join(aliases[:5])}")

    # Fetch recent relations (as source)
    rels = conn.execute(
        """SELECT rel, target_id FROM relations
           WHERE source_id = ? AND rel != 'MENTIONS'
           LIMIT 10""",
        (entity_id,),
    ).fetchall()
    if rels:
        rel_strs = [f"{r[0]} → {r[1]}" for r in rels]
        parts.append(f"Relations (as source): {'; '.join(rel_strs)}")

    # Fetch recent relations (as target)
    rels_t = conn.execute(
        """SELECT source_id, rel FROM relations
           WHERE target_id = ? AND rel != 'MENTIONS'
           LIMIT 10""",
        (entity_id,),
    ).fetchall()
    if rels_t:
        rel_strs = [f"{r[0]} {r[1]}" for r in rels_t]
        parts.append(f"Relations (as target): {'; '.join(rel_strs)}")

    # Fetch doc titles that mention this entity
    docs = conn.execute(
        """SELECT DISTINCT d.title
           FROM relations r JOIN documents d ON r.doc_id = d.doc_id
           WHERE (r.source_id = ? OR r.target_id = ?)
           ORDER BY d.published_at DESC LIMIT ?""",
        (entity_id, entity_id, max_docs),
    ).fetchall()
    if docs:
        titles = [d[0] for d in docs if d[0]]
        if titles:
            parts.append(f"Recent documents: {'; '.join(titles[:max_docs])}")

    return "\n".join(parts)


def collect_gray_zone_pairs(
    conn: sqlite3.Connection,
    config: DisambiguationConfig,
) -> list[EntityPair]:
    """Find entity pairs in the similarity gray zone.

    Returns pairs where ``lower_bound <= similarity < upper_bound``,
    capped at ``max_pairs_per_run``.
    """
    # Get all entities, optionally filtered by type
    type_filter = config.entity_types_to_disambiguate
    if type_filter:
        placeholders = ",".join("?" for _ in type_filter)
        query = f"SELECT entity_id, name, type FROM entities WHERE type IN ({placeholders}) ORDER BY type, name"
        entities = [dict(r) for r in conn.execute(query, type_filter).fetchall()]
    else:
        entities = [
            dict(r) for r in conn.execute(
                "SELECT entity_id, name, type FROM entities ORDER BY type, name"
            ).fetchall()
        ]

    pairs: list[EntityPair] = []
    seen: set[tuple[str, str]] = set()

    # Group by type for O(n^2) within type (small groups)
    from itertools import groupby
    from operator import itemgetter

    for etype, group in groupby(entities, key=itemgetter("type")):
        members = list(group)
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                if len(pairs) >= config.max_pairs_per_run:
                    return pairs

                pair_key = tuple(sorted([a["entity_id"], b["entity_id"]]))
                if pair_key in seen:
                    continue
                seen.add(pair_key)

                # Skip if already decided
                if _pair_already_decided(conn, a["entity_id"], b["entity_id"]):
                    continue

                sim = name_similarity(a["name"], b["name"])
                if config.similarity_lower_bound <= sim < config.similarity_upper_bound:
                    pairs.append(EntityPair(
                        entity_a_id=a["entity_id"],
                        entity_a_name=a["name"],
                        entity_b_id=b["entity_id"],
                        entity_b_name=b["name"],
                        entity_type=etype,
                        similarity=sim,
                    ))

    return pairs


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def _load_prompt_template(profile: dict[str, Any], filename: str) -> Optional[str]:
    """Load a disambiguation prompt template from the domain's prompts dir."""
    domain_dir: Path = profile.get("_domain_dir", Path("."))
    prompts_dir = domain_dir / profile.get("prompts", {}).get("dir", "prompts")
    path = prompts_dir / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


_DEFAULT_SYSTEM_PROMPT = """\
You are an entity disambiguation system for a knowledge graph.
Given pairs of entities that might refer to the same real-world thing,
decide whether they should be MERGED into one entity or KEPT SEPARATE.

For each pair, respond with a JSON object:
{{"verdict": "merge"|"keep_separate"|"uncertain", "confidence": 0.0-1.0, "reason": "brief explanation"}}

Return a JSON array of verdict objects, one per pair, in the same order as presented.
Only output the JSON array — no other text."""

_DEFAULT_USER_TEMPLATE = """\
Evaluate these {count} entity pairs. For each, decide: MERGE (same real-world entity), \
KEEP_SEPARATE (different entities), or UNCERTAIN.

{pairs_block}

Respond with a JSON array of {count} objects:
[{{"verdict": "merge"|"keep_separate"|"uncertain", "confidence": 0.0-1.0, "reason": "..."}}]"""


def build_disambiguation_prompt(
    pairs: list[EntityPair],
    profile: dict[str, Any],
) -> tuple[str, str]:
    """Build system and user prompts for a batch of pairs.

    Returns:
        (system_prompt, user_prompt)
    """
    system = _load_prompt_template(profile, "disambiguate_system.txt")
    if not system:
        system = _DEFAULT_SYSTEM_PROMPT

    pair_blocks: list[str] = []
    for i, p in enumerate(pairs, 1):
        block = (
            f"--- Pair {i} ---\n"
            f"Entity A ({p.entity_type}): \"{p.entity_a_name}\"\n"
            f"{p.context_a}\n\n"
            f"Entity B ({p.entity_type}): \"{p.entity_b_name}\"\n"
            f"{p.context_b}\n"
            f"String similarity: {p.similarity:.2f}"
        )
        pair_blocks.append(block)

    pairs_block = "\n\n".join(pair_blocks)

    user_template = _load_prompt_template(profile, "disambiguate_user.txt")
    if user_template:
        user_prompt = user_template.format(count=len(pairs), pairs_block=pairs_block)
    else:
        user_prompt = _DEFAULT_USER_TEMPLATE.format(count=len(pairs), pairs_block=pairs_block)

    return system, user_prompt


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-5-nano",
) -> tuple[str, int]:
    """Call an LLM for disambiguation. Returns (response_text, duration_ms).

    Follows the same provider-detection pattern as run_extract.py.
    """
    openai_prefixes = ("gpt-", "o1", "o3", "o4")
    is_openai = any(model.startswith(p) for p in openai_prefixes)

    start = time.time()

    if is_openai:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
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
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text

    duration_ms = int((time.time() - start) * 1000)
    return text, duration_ms


def _parse_llm_response(
    text: str,
    pairs: list[EntityPair],
) -> list[Decision]:
    """Parse the LLM JSON response into Decision objects."""
    import re

    # Extract JSON array from response (may be wrapped in markdown fences)
    text = text.strip()
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        verdicts = json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON array in the text
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            verdicts = json.loads(match.group())
        else:
            return [
                Decision(
                    entity_a_id=p.entity_a_id,
                    entity_b_id=p.entity_b_id,
                    verdict="uncertain",
                    reason="LLM response parse failure",
                )
                for p in pairs
            ]

    if not isinstance(verdicts, list):
        verdicts = [verdicts]

    decisions: list[Decision] = []
    for i, pair in enumerate(pairs):
        if i < len(verdicts):
            v = verdicts[i]
            verdict = str(v.get("verdict", "uncertain")).lower().strip()
            if verdict not in ("merge", "keep_separate", "uncertain"):
                verdict = "uncertain"
            decisions.append(Decision(
                entity_a_id=pair.entity_a_id,
                entity_b_id=pair.entity_b_id,
                verdict=verdict,
                confidence=float(v.get("confidence", 0.0)),
                reason=str(v.get("reason", "")),
            ))
        else:
            decisions.append(Decision(
                entity_a_id=pair.entity_a_id,
                entity_b_id=pair.entity_b_id,
                verdict="uncertain",
                reason="No verdict returned for this pair",
            ))

    return decisions


# ---------------------------------------------------------------------------
# Batch disambiguation
# ---------------------------------------------------------------------------

def batch_disambiguate(
    pairs: list[EntityPair],
    profile: dict[str, Any],
    model: str = "gpt-5-nano",
) -> tuple[list[Decision], int]:
    """Send a batch of pairs to the LLM and return decisions.

    Returns:
        (list of decisions, duration_ms)
    """
    system_prompt, user_prompt = build_disambiguation_prompt(pairs, profile)
    response_text, duration_ms = _call_llm(system_prompt, user_prompt, model=model)
    decisions = _parse_llm_response(response_text, pairs)
    return decisions, duration_ms


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_llm_disambiguation(
    conn: sqlite3.Connection,
    profile: Optional[dict[str, Any]] = None,
    model: str = "gpt-5-nano",
    run_date: Optional[str] = None,
    dry_run: bool = False,
) -> DisambiguationResult:
    """Run LLM disambiguation on gray-zone entity pairs.

    Args:
        conn: Database connection.
        profile: Domain profile dict. Uses active profile if None.
        model: LLM model ID for disambiguation calls.
        run_date: ISO date string for logging. Defaults to today.
        dry_run: If True, evaluate but don't merge.

    Returns:
        DisambiguationResult with counts.
    """
    if profile is None:
        profile = get_active_profile()

    config = DisambiguationConfig.from_profile(profile)
    if not config.enabled:
        return DisambiguationResult()

    if run_date is None:
        from datetime import date
        run_date = date.today().isoformat()

    ensure_disambiguation_table(conn)

    start = time.time()
    result = DisambiguationResult()

    # Collect gray-zone pairs
    pairs = collect_gray_zone_pairs(conn, config)
    if not pairs:
        return result

    # Enrich with context
    for pair in pairs:
        pair.context_a = _entity_context(conn, pair.entity_a_id, config.context_window_docs)
        pair.context_b = _entity_context(conn, pair.entity_b_id, config.context_window_docs)

    # Process in batches
    for batch_start in range(0, len(pairs), config.batch_size):
        batch = pairs[batch_start:batch_start + config.batch_size]

        try:
            decisions, _ = batch_disambiguate(batch, profile, model=model)
            result.llm_calls += 1
        except Exception as e:
            print(f"  [disambiguate] LLM call failed: {e}")
            # Mark all as uncertain
            decisions = [
                Decision(
                    entity_a_id=p.entity_a_id,
                    entity_b_id=p.entity_b_id,
                    verdict="uncertain",
                    reason=f"LLM error: {e}",
                )
                for p in batch
            ]

        for decision, pair in zip(decisions, batch):
            result.pairs_evaluated += 1

            # Save decision to DB
            _save_decision(conn, decision, model, run_date, pair.similarity)

            if decision.verdict == "merge" and not dry_run:
                # Merge: keep the entity with more relations as canonical
                a_rels = conn.execute(
                    "SELECT COUNT(*) FROM relations WHERE source_id = ? OR target_id = ?",
                    (pair.entity_a_id, pair.entity_a_id),
                ).fetchone()[0]
                b_rels = conn.execute(
                    "SELECT COUNT(*) FROM relations WHERE source_id = ? OR target_id = ?",
                    (pair.entity_b_id, pair.entity_b_id),
                ).fetchone()[0]

                if a_rels >= b_rels:
                    canonical, duplicate = pair.entity_a_id, pair.entity_b_id
                else:
                    canonical, duplicate = pair.entity_b_id, pair.entity_a_id

                merge_entities(conn, duplicate, canonical)
                result.merges_performed += 1
                print(f"  [disambiguate] MERGE: \"{pair.entity_a_name}\" + \"{pair.entity_b_name}\" → {canonical}")

            elif decision.verdict == "keep_separate":
                result.kept_separate += 1
            else:
                result.uncertain += 1

    conn.commit()
    result.duration_ms = int((time.time() - start) * 1000)
    return result
