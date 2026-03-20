"""Rule-based relation inference engine.

Evaluates domain-defined inference rules against the knowledge graph to
create new relations from implicit patterns.  For example, in the film
domain: if Person DIRECTS Production and Production DISTRIBUTES Studio,
infer Person WORKS_WITH Studio.

Framework-level code: inference rules are defined entirely in the domain
config (``features.relation_inference`` in domain.yaml or a separate
``inference_rules.yaml``).  The AI domain can disable inference entirely.

See docs/architecture/domain-separation.md for boundary rules.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

import yaml

from domain import get_active_profile


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class InferenceConfig:
    """Settings loaded from domain.yaml ``features.relation_inference``."""

    enabled: bool = False
    confidence_discount: float = 0.8
    max_inferences_per_run: int = 500
    require_llm_validation: bool = False
    rules_file: str = "inference_rules.yaml"

    @classmethod
    def from_profile(cls, profile: dict[str, Any]) -> "InferenceConfig":
        features = profile.get("features", {})
        cfg = features.get("relation_inference", {})
        if not isinstance(cfg, dict):
            return cls()
        return cls(
            enabled=bool(cfg.get("enabled", False)),
            confidence_discount=float(cfg.get("confidence_discount", 0.8)),
            max_inferences_per_run=int(cfg.get("max_inferences_per_run", 500)),
            require_llm_validation=bool(cfg.get("require_llm_validation", False)),
            rules_file=str(cfg.get("rules_file", "inference_rules.yaml")),
        )


# ---------------------------------------------------------------------------
# Rule structures
# ---------------------------------------------------------------------------

@dataclass
class Antecedent:
    """One condition in an inference rule."""

    source_type: str
    rel: str
    target_type: str


@dataclass
class InferenceRule:
    """A domain-defined inference rule."""

    name: str
    description: str
    antecedents: list[Antecedent]
    consequent_rel: str
    # Which antecedent provides source/target for the new relation.
    # Format: "antecedent[N].source" or "antecedent[N].target"
    consequent_source: str  # e.g. "antecedent[0].source"
    consequent_target: str  # e.g. "antecedent[1].target"
    confidence_discount: Optional[float] = None  # per-rule override


@dataclass
class InferenceResult:
    """Summary of an inference run."""

    rules_evaluated: int = 0
    relations_inferred: int = 0
    relations_skipped: int = 0  # already existed
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def ensure_inference_tables(conn: sqlite3.Connection) -> None:
    """Create inference tracking tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS inference_runs (
            inference_id TEXT PRIMARY KEY,
            run_date TEXT NOT NULL,
            rules_evaluated INTEGER,
            relations_inferred INTEGER,
            relations_skipped INTEGER,
            duration_ms INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_inf_date
            ON inference_runs(run_date);
    """)
    conn.commit()

    # Add inferred_from column to relations if missing
    cols = {row[1] for row in conn.execute("PRAGMA table_info(relations)").fetchall()}
    if "inferred_from" not in cols:
        conn.execute("ALTER TABLE relations ADD COLUMN inferred_from TEXT")
        conn.commit()


def _relation_exists(
    conn: sqlite3.Connection,
    source_id: str,
    rel: str,
    target_id: str,
) -> bool:
    """Check if a relation already exists (any kind)."""
    row = conn.execute(
        """SELECT 1 FROM relations
           WHERE source_id = ? AND rel = ? AND target_id = ?
           LIMIT 1""",
        (source_id, rel, target_id),
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Rule loading
# ---------------------------------------------------------------------------

def _parse_antecedent(data: dict[str, str]) -> Antecedent:
    return Antecedent(
        source_type=data["source_type"],
        rel=data["rel"],
        target_type=data["target_type"],
    )


def _parse_rule(data: dict[str, Any]) -> InferenceRule:
    """Parse a single rule from YAML dict."""
    antecedents = [_parse_antecedent(a) for a in data["antecedents"]]
    consequent = data["consequent"]
    return InferenceRule(
        name=data.get("name", "unnamed"),
        description=data.get("description", ""),
        antecedents=antecedents,
        consequent_rel=consequent["rel"],
        consequent_source=consequent["source"],
        consequent_target=consequent["target"],
        confidence_discount=data.get("confidence_discount"),
    )


def load_inference_rules(profile: dict[str, Any]) -> list[InferenceRule]:
    """Load inference rules from the domain's config.

    Checks two locations:
    1. Inline ``features.relation_inference.rules`` list in domain.yaml
    2. Separate file at ``domains/<slug>/<rules_file>``
    """
    features = profile.get("features", {})
    cfg = features.get("relation_inference", {})
    if not isinstance(cfg, dict):
        return []

    # Check inline rules first
    inline = cfg.get("rules", [])
    if inline:
        return [_parse_rule(r) for r in inline]

    # Check external file
    rules_file = cfg.get("rules_file", "inference_rules.yaml")
    domain_dir: Path = profile.get("_domain_dir", Path("."))
    rules_path = domain_dir / rules_file
    if not rules_path.exists():
        return []

    with open(rules_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or not isinstance(data, dict):
        return []

    rules_list = data.get("inference_rules", data.get("rules", []))
    return [_parse_rule(r) for r in rules_list]


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------

def _resolve_endpoint(ref: str, matches: list[dict[str, str]]) -> Optional[str]:
    """Resolve an endpoint reference like 'antecedent[0].source' to an entity_id."""
    import re
    m = re.match(r"antecedent\[(\d+)\]\.(source|target)", ref)
    if not m:
        return None
    idx = int(m.group(1))
    field = m.group(2)
    if idx >= len(matches):
        return None
    return matches[idx].get(f"{field}_id")


def find_matching_patterns(
    conn: sqlite3.Connection,
    rule: InferenceRule,
) -> list[dict[str, Any]]:
    """Find all entity combinations that match a rule's antecedents.

    For 2-antecedent rules, performs a SQL join to find matching chains.

    Returns:
        List of dicts with source_id, target_id, and antecedent_confidences.
    """
    if len(rule.antecedents) == 0:
        return []

    if len(rule.antecedents) == 1:
        a = rule.antecedents[0]
        rows = conn.execute(
            """SELECT r.source_id, r.target_id, r.confidence, r.relation_id,
                      e_s.type AS source_type, e_t.type AS target_type
               FROM relations r
               JOIN entities e_s ON r.source_id = e_s.entity_id
               JOIN entities e_t ON r.target_id = e_t.entity_id
               WHERE r.rel = ? AND e_s.type = ? AND e_t.type = ?""",
            (a.rel, a.source_type, a.target_type),
        ).fetchall()

        results = []
        for row in rows:
            results.append({
                "antecedent_matches": [
                    {"source_id": row[0], "target_id": row[1],
                     "confidence": row[2], "relation_id": row[3]},
                ],
                "confidences": [row[2]],
            })
        return results

    if len(rule.antecedents) == 2:
        a0, a1 = rule.antecedents

        # Two-antecedent join: find chains where a0.target == a1.source
        # (the shared entity in the chain)
        rows = conn.execute(
            """SELECT r1.source_id, r1.target_id, r1.confidence, r1.relation_id,
                      r2.source_id, r2.target_id, r2.confidence, r2.relation_id
               FROM relations r1
               JOIN relations r2 ON r1.target_id = r2.source_id
               JOIN entities e1s ON r1.source_id = e1s.entity_id
               JOIN entities e1t ON r1.target_id = e1t.entity_id
               JOIN entities e2t ON r2.target_id = e2t.entity_id
               WHERE r1.rel = ? AND r2.rel = ?
               AND e1s.type = ? AND e1t.type = ?
               AND e2t.type = ?""",
            (a0.rel, a1.rel, a0.source_type, a0.target_type, a1.target_type),
        ).fetchall()

        results = []
        for row in rows:
            results.append({
                "antecedent_matches": [
                    {"source_id": row[0], "target_id": row[1],
                     "confidence": row[2], "relation_id": row[3]},
                    {"source_id": row[4], "target_id": row[5],
                     "confidence": row[6], "relation_id": row[7]},
                ],
                "confidences": [row[2], row[6]],
            })
        return results

    # For rules with 3+ antecedents, not supported in V1
    return []


# ---------------------------------------------------------------------------
# Inference creation
# ---------------------------------------------------------------------------

def create_inferred_relation(
    conn: sqlite3.Connection,
    source_id: str,
    target_id: str,
    rel: str,
    confidence: float,
    antecedent_ids: list[int],
) -> bool:
    """Insert an inferred relation. Returns True if created, False if already exists."""
    if _relation_exists(conn, source_id, rel, target_id):
        return False

    # Also skip self-referential relations
    if source_id == target_id:
        return False

    conn.execute(
        """INSERT INTO relations
           (source_id, rel, target_id, kind, confidence, extractor_version, inferred_from)
           VALUES (?, ?, ?, 'inferred', ?, 'inference-1.0', ?)""",
        (source_id, rel, target_id, confidence,
         json.dumps(antecedent_ids)),
    )
    return True


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_inference_pass(
    conn: sqlite3.Connection,
    profile: Optional[dict[str, Any]] = None,
    run_date: Optional[str] = None,
) -> InferenceResult:
    """Run inference rules over the knowledge graph.

    Args:
        conn: Database connection.
        profile: Domain profile. Uses active if None.
        run_date: ISO date for logging.

    Returns:
        InferenceResult with counts.
    """
    if profile is None:
        profile = get_active_profile()

    config = InferenceConfig.from_profile(profile)
    if not config.enabled:
        return InferenceResult()

    if run_date is None:
        run_date = date.today().isoformat()

    ensure_inference_tables(conn)

    rules = load_inference_rules(profile)
    if not rules:
        return InferenceResult()

    start = time.time()
    result = InferenceResult()
    total_inferred = 0

    for rule in rules:
        result.rules_evaluated += 1
        matches = find_matching_patterns(conn, rule)

        for match_data in matches:
            if total_inferred >= config.max_inferences_per_run:
                break

            antecedent_matches = match_data["antecedent_matches"]
            confidences = match_data["confidences"]

            # Resolve source and target for the consequent
            source_id = _resolve_endpoint(rule.consequent_source, antecedent_matches)
            target_id = _resolve_endpoint(rule.consequent_target, antecedent_matches)

            if not source_id or not target_id:
                continue

            # Compute confidence as product of antecedents * discount
            discount = rule.confidence_discount or config.confidence_discount
            inferred_conf = 1.0
            for c in confidences:
                inferred_conf *= c
            inferred_conf *= discount
            inferred_conf = round(min(inferred_conf, 1.0), 3)

            antecedent_ids = [m["relation_id"] for m in antecedent_matches]

            created = create_inferred_relation(
                conn, source_id, target_id, rule.consequent_rel,
                inferred_conf, antecedent_ids,
            )

            if created:
                result.relations_inferred += 1
                total_inferred += 1
            else:
                result.relations_skipped += 1

        if total_inferred >= config.max_inferences_per_run:
            break

    conn.commit()

    # Log the run
    inference_id = str(uuid.uuid4())[:8]
    conn.execute(
        """INSERT INTO inference_runs
           (inference_id, run_date, rules_evaluated, relations_inferred,
            relations_skipped, duration_ms)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (inference_id, run_date, result.rules_evaluated,
         result.relations_inferred, result.relations_skipped,
         int((time.time() - start) * 1000)),
    )
    conn.commit()

    result.duration_ms = int((time.time() - start) * 1000)
    return result
