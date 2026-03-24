"""Trend narrative generation — "What's Hot and WHY".

Given trending entities with their scores, generates human-readable
1-3 sentence narratives explaining WHY each entity is trending.

Framework-level code: domain-specific tone/style is controlled via
``features.trend_narratives`` in domain.yaml and the prompt templates
in ``domains/<slug>/prompts/``.

See docs/architecture/domain-separation.md for boundary rules.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

from domain import get_active_profile


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class NarrativeConfig:
    """Settings loaded from domain.yaml ``features.trend_narratives``."""

    enabled: bool = False
    top_n: int = 10
    max_tokens_per_narrative: int = 100
    style: str = "concise"  # "concise", "detailed", "headline"

    @classmethod
    def from_profile(cls, profile: dict[str, Any]) -> "NarrativeConfig":
        features = profile.get("features", {})
        cfg = features.get("trend_narratives", {})
        if not isinstance(cfg, dict):
            return cls()
        return cls(
            enabled=bool(cfg.get("enabled", False)),
            top_n=int(cfg.get("top_n", 10)),
            max_tokens_per_narrative=int(cfg.get("max_tokens_per_narrative", 100)),
            style=str(cfg.get("style", "concise")),
        )


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def ensure_narrative_table(conn: sqlite3.Connection) -> None:
    """Create the trend_narratives table if it doesn't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trend_narratives (
            entity_id TEXT NOT NULL,
            run_date TEXT NOT NULL,
            narrative TEXT NOT NULL,
            model TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (entity_id, run_date)
        );
        CREATE INDEX IF NOT EXISTS idx_tn_date
            ON trend_narratives(run_date);
    """)
    conn.commit()


def _get_cached_narrative(
    conn: sqlite3.Connection,
    entity_id: str,
    run_date: str,
) -> Optional[str]:
    """Return cached narrative for today if it exists."""
    row = conn.execute(
        "SELECT narrative FROM trend_narratives WHERE entity_id = ? AND run_date = ?",
        (entity_id, run_date),
    ).fetchone()
    return row[0] if row else None


def _save_narrative(
    conn: sqlite3.Connection,
    entity_id: str,
    run_date: str,
    narrative: str,
    model: str,
) -> None:
    """Persist a generated narrative."""
    conn.execute(
        """INSERT OR REPLACE INTO trend_narratives
           (entity_id, run_date, narrative, model)
           VALUES (?, ?, ?, ?)""",
        (entity_id, run_date, narrative, model),
    )


# ---------------------------------------------------------------------------
# Context gathering
# ---------------------------------------------------------------------------

@dataclass
class EntityContext:
    """Context for narrative generation about one trending entity."""

    entity_id: str
    name: str
    entity_type: str
    trend_score: float = 0.0
    velocity: float = 0.0
    novelty: float = 0.0
    bridge_score: float = 0.0
    mention_count_7d: int = 0
    mention_count_30d: int = 0
    recent_doc_titles: list[str] = field(default_factory=list)
    recent_relations: list[str] = field(default_factory=list)


def gather_narrative_context(
    conn: sqlite3.Connection,
    entity_scores: list[dict[str, Any]],
    max_docs: int = 5,
    max_relations: int = 8,
) -> list[EntityContext]:
    """Build context objects for trending entities."""
    contexts: list[EntityContext] = []
    skipped = 0

    for scores in entity_scores:
        eid = scores["entity_id"]

        # Get entity info
        row = conn.execute(
            "SELECT name, type FROM entities WHERE entity_id = ?",
            (eid,),
        ).fetchone()
        if not row:
            skipped += 1
            continue

        ctx = EntityContext(
            entity_id=eid,
            name=row[0],
            entity_type=row[1],
            trend_score=scores.get("trend_score", 0),
            velocity=scores.get("velocity", 0),
            novelty=scores.get("novelty", 0),
            bridge_score=scores.get("bridge_score", 0),
            mention_count_7d=scores.get("mention_count_7d", 0),
            mention_count_30d=scores.get("mention_count_30d", 0),
        )

        # Recent document titles
        docs = conn.execute(
            """SELECT DISTINCT d.title
               FROM relations r JOIN documents d ON r.doc_id = d.doc_id
               WHERE (r.source_id = ? OR r.target_id = ?)
               AND r.rel = 'MENTIONS'
               ORDER BY d.published_at DESC LIMIT ?""",
            (eid, eid, max_docs),
        ).fetchall()
        ctx.recent_doc_titles = [d[0] for d in docs if d[0]]

        # Recent semantic relations
        rels = conn.execute(
            """SELECT source_id, rel, target_id
               FROM relations
               WHERE (source_id = ? OR target_id = ?)
               AND rel != 'MENTIONS'
               ORDER BY created_at DESC LIMIT ?""",
            (eid, eid, max_relations),
        ).fetchall()
        ctx.recent_relations = [f"{r[0]} {r[1]} {r[2]}" for r in rels]

        contexts.append(ctx)

    if skipped:
        print(f"  - {skipped} narrative context skipped (entity_id not in entities table)")
    return contexts


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def _load_prompt_template(profile: dict[str, Any], filename: str) -> Optional[str]:
    """Load a narrative prompt template from domain's prompts dir."""
    domain_dir: Path = profile.get("_domain_dir", Path("."))
    prompts_dir = domain_dir / profile.get("prompts", {}).get("dir", "prompts")
    path = prompts_dir / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


_DEFAULT_SYSTEM_PROMPT = """\
You are a trend analyst for a knowledge graph. Given trending entities with their \
scores and recent activity, write a brief 1-2 sentence narrative explaining WHY \
each entity is trending. Be factual — only reference data provided in the context.

Style: {style}

Respond with a JSON object mapping entity names to narrative strings:
{{"Entity Name": "narrative text", ...}}

Only output the JSON — no other text."""

_DEFAULT_USER_TEMPLATE = """\
Generate trend narratives for these {count} entities:

{entities_block}

Respond with JSON: {{"Entity Name": "1-2 sentence narrative explaining why trending"}}"""


def _build_entity_block(ctx: EntityContext) -> str:
    """Format one entity's context for the prompt."""
    parts = [
        f"--- {ctx.name} ({ctx.entity_type}) ---",
        f"Trend score: {ctx.trend_score:.2f} | Velocity: {ctx.velocity:.1f}x | "
        f"Mentions (7d): {ctx.mention_count_7d} | Mentions (30d): {ctx.mention_count_30d}",
    ]
    if ctx.recent_doc_titles:
        parts.append(f"Recent articles: {'; '.join(ctx.recent_doc_titles[:5])}")
    if ctx.recent_relations:
        parts.append(f"Key relations: {'; '.join(ctx.recent_relations[:5])}")
    return "\n".join(parts)


def build_narrative_prompt(
    contexts: list[EntityContext],
    profile: dict[str, Any],
    config: NarrativeConfig,
) -> tuple[str, str]:
    """Build system and user prompts for narrative generation.

    Returns:
        (system_prompt, user_prompt)
    """
    system = _load_prompt_template(profile, "narrative_system.txt")
    if not system:
        system = _DEFAULT_SYSTEM_PROMPT.format(style=config.style)

    entities_block = "\n\n".join(_build_entity_block(ctx) for ctx in contexts)

    user = _load_prompt_template(profile, "narrative_user.txt")
    if user:
        user_prompt = user.format(count=len(contexts), entities_block=entities_block)
    else:
        user_prompt = _DEFAULT_USER_TEMPLATE.format(
            count=len(contexts), entities_block=entities_block
        )

    return system, user_prompt


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-5-nano",
) -> tuple[str, int]:
    """Call LLM for narrative generation. Returns (text, duration_ms)."""
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
        _temp_kwargs = {} if _reasoning else {"temperature": 0.3}
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
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text

    duration_ms = int((time.time() - start) * 1000)
    return text, duration_ms


def _parse_narratives(text: str) -> dict[str, str]:
    """Parse LLM JSON response into name→narrative mapping."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            result = json.loads(match.group())
        else:
            return {}

    if isinstance(result, dict):
        return {str(k): str(v) for k, v in result.items()}
    return {}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_narratives(
    conn: sqlite3.Connection,
    trending_entities: list[dict[str, Any]],
    profile: Optional[dict[str, Any]] = None,
    model: str = "gpt-5-nano",
    run_date: Optional[str] = None,
) -> dict[str, str]:
    """Generate narratives for trending entities.

    Args:
        conn: Database connection.
        trending_entities: List of entity score dicts from TrendScorer.
        profile: Domain profile. Uses active if None.
        model: LLM model for generation.
        run_date: ISO date for caching.

    Returns:
        Dict mapping entity_id to narrative string.
    """
    if profile is None:
        profile = get_active_profile()

    config = NarrativeConfig.from_profile(profile)
    if not config.enabled:
        return {}

    if run_date is None:
        run_date = date.today().isoformat()

    ensure_narrative_table(conn)

    # Take only top_n
    top = trending_entities[:config.top_n]
    if not top:
        return {}

    narratives: dict[str, str] = {}

    # Check cache first
    uncached: list[dict[str, Any]] = []
    for entity in top:
        eid = entity["entity_id"]
        cached = _get_cached_narrative(conn, eid, run_date)
        if cached:
            narratives[eid] = cached
        else:
            uncached.append(entity)

    if not uncached:
        return narratives

    # Build context and call LLM
    contexts = gather_narrative_context(conn, uncached)
    if not contexts:
        return narratives

    try:
        system_prompt, user_prompt = build_narrative_prompt(contexts, profile, config)
        response_text, duration_ms = _call_llm(system_prompt, user_prompt, model=model)
        name_to_narrative = _parse_narratives(response_text)
    except Exception as e:
        print(f"  [narratives] LLM call failed: {e}")
        return narratives

    print(f"  - {len(name_to_narrative)} LLM narratives returned")

    # Map narratives back to entity_ids and save
    # Primary: exact match. Fallback: case-insensitive match.
    name_to_id = {ctx.name: ctx.entity_id for ctx in contexts}
    name_to_id_lower = {ctx.name.lower(): ctx.entity_id for ctx in contexts}
    mapped = 0
    mismatched = 0
    for name, narrative in name_to_narrative.items():
        eid = name_to_id.get(name) or name_to_id_lower.get(name.lower())
        if eid:
            narratives[eid] = narrative
            _save_narrative(conn, eid, run_date, narrative, model)
            mapped += 1
        else:
            mismatched += 1

    print(f"  - {mapped} narratives mapped to entity IDs")
    if mismatched:
        print(f"  - {mismatched} name mismatches dropped (LLM name not in context)")

    conn.commit()
    return narratives
