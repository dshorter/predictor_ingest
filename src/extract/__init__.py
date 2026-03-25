"""Extraction module for LLM-based entity and relation extraction.

Supports:
- Mode A: Automated extraction via Anthropic Batch API (submit_batch + collect_batch)
- Mode B: Manual extraction import with validation

Quality gates (Phase 1 — CPU, zero tokens):
  Gate A: Evidence fidelity — snippets must appear in source text
  Gate B: Orphan endpoints — relation source/target must match an entity
  Gate C: Zero-value — non-trivial docs must produce ≥1 entity
  Gate D: High-confidence + bad evidence — worst hallucination pattern

Gates run post-collection as QA logging (quality_metrics table). They no
longer gate escalation — there is no escalation path in ADR-008.

Domain-specific values (entity types, relation taxonomy, normalization map,
gate thresholds) are loaded from the active domain profile.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from schema import (
    validate_extraction,
    ValidationError,
)
from domain import get_active_profile


# Current extractor version - bump when prompts/schema change
# 1.0.0 — initial extraction prompts
# 2.0.0 — quality gates, escalation mode, relation normalization,
#          budget-based document selection, MENTIONS auto-generation
EXTRACTOR_VERSION = "2.0.0"

# --- Domain-derived constants (loaded from active domain profile) ---
# Backward-compatible module-level names so existing code that does
# `from extract import RELATION_NORMALIZATION` continues to work.
_profile = get_active_profile()
ENTITY_TYPES: list[str] = sorted(_profile["entity_types"])
RELATION_TYPES: list[str] = sorted(_profile["relation_taxonomy"]["canonical"])
RELATION_NORMALIZATION: dict[str, str] = dict(_profile["relation_taxonomy"]["normalization"])

# --- Unmapped type tracking ---
# Module-level counter accumulates relation types that the LLM produced but
# could not be mapped via normalization or found in canonical list.
# Call get_unmapped_relation_types() after an extraction run to inspect,
# reset_unmapped_relation_types() before a new run.
_unmapped_relation_types: Counter = Counter()


def get_unmapped_relation_types() -> Counter:
    """Return accumulated unmapped relation types and their counts."""
    return _unmapped_relation_types


def reset_unmapped_relation_types() -> None:
    """Clear the unmapped relation type counter (call before each run)."""
    _unmapped_relation_types.clear()


class ExtractionError(Exception):
    """Raised when extraction fails."""

    pass


def normalize_extraction(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize LLM output variations to canonical forms.

    Args:
        data: Raw extraction dict from LLM

    Returns:
        Normalized extraction dict
    """
    # Normalize relation types — track unmapped types for observability
    unmapped_relations: list[str] = []
    for relation in data.get("relations", []):
        rel = relation.get("rel", "").upper()
        if rel in RELATION_NORMALIZATION:
            relation["rel"] = RELATION_NORMALIZATION[rel]
        elif rel not in RELATION_TYPES:
            # Try to match without underscores/hyphens
            normalized = rel.replace("-", "_").replace(" ", "_")
            if normalized in RELATION_NORMALIZATION:
                relation["rel"] = RELATION_NORMALIZATION[normalized]
            else:
                # Track the unmapped type for downstream reporting
                unmapped_relations.append(rel)
                _unmapped_relation_types[rel] += 1
    if unmapped_relations:
        data["_unmapped_relations"] = unmapped_relations

    # Normalize entity types
    for entity in data.get("entities", []):
        etype = entity.get("type", "")
        # Capitalize first letter for consistency
        if etype and etype.lower() in [t.lower() for t in ENTITY_TYPES]:
            for canonical in ENTITY_TYPES:
                if etype.lower() == canonical.lower():
                    entity["type"] = canonical
                    break

    # Normalize dates - convert null start/end to empty strings or remove
    _DATE_RESOLUTION_MAP = {
        "day": "exact",
        "daily": "exact",
        "month": "exact",
        "year": "exact",
        "weekly": "range",
        "week": "range",
        "season": "range",
        "decade": "range",
        "duration": "range",
        "period": "range",
        "quarterly": "range",
        "annual": "range",
        "approximate": "unknown",
    }
    for date_obj in data.get("dates", []):
        if date_obj.get("start") is None:
            date_obj.pop("start", None)
        if date_obj.get("end") is None:
            date_obj.pop("end", None)
        # Normalize non-standard resolution values
        res = date_obj.get("resolution")
        if res and res in _DATE_RESOLUTION_MAP:
            date_obj["resolution"] = _DATE_RESOLUTION_MAP[res]

    # Normalize techTerms - handle objects with term/definition structure
    if "techTerms" in data:
        normalized_terms = []
        for term in data.get("techTerms", []):
            if isinstance(term, str):
                normalized_terms.append(term)
            elif isinstance(term, dict):
                # Extract just the term from object format
                term_str = term.get("term") or term.get("name") or str(term)
                if term_str:
                    normalized_terms.append(term_str)
        data["techTerms"] = normalized_terms

    return data


# ---------------------------------------------------------------------------
# Domain-specific prompts and tool schemas — delegated to extract.prompts
# for domain-separation (see docs/architecture/domain-separation.md).
# Re-exported here so existing callers (run_extract.py, tests) continue
# to import from "extract" without changes.
# ---------------------------------------------------------------------------
from extract.prompts import (                          # noqa: E402
    build_extraction_prompt as _build_prompt,
    build_extraction_system_prompt as _build_system,
    build_extraction_user_prompt,                       # pass-through
    OPENAI_EXTRACTION_TOOL,                             # pass-through
    ANTHROPIC_EXTRACTION_SCHEMA,                        # pass-through
)


def build_extraction_prompt(
    doc: dict[str, Any],
    extractor_version: Optional[str] = None,
) -> str:
    """Build prompt for LLM extraction (backward-compat wrapper)."""
    return _build_prompt(doc, extractor_version or EXTRACTOR_VERSION)


def build_extraction_system_prompt(
    extractor_version: Optional[str] = None,
) -> str:
    """Build the static system prompt for extraction (backward-compat wrapper)."""
    return _build_system(extractor_version or EXTRACTOR_VERSION)


def parse_extraction_response(
    response: str,
    doc_id: str,
) -> dict[str, Any]:
    """Parse LLM response and validate against schema.

    Args:
        response: Raw LLM response (may contain markdown)
        doc_id: Document ID to inject if missing

    Returns:
        Validated extraction dict

    Raises:
        ExtractionError: If parsing or validation fails
    """
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # Try to find JSON object directly
        json_str = response.strip()

    # Parse JSON
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"Failed to parse JSON: {e}") from e

    # Inject docId if missing
    if "docId" not in data:
        data["docId"] = doc_id

    # Normalize LLM output variations before validation
    data = normalize_extraction(data)

    # Validate against schema
    try:
        validate_extraction(data)
    except ValidationError as e:
        raise ExtractionError(str(e)) from e

    return data


def save_extraction(
    extraction: dict[str, Any],
    output_dir: Path,
) -> Path:
    """Save extraction to JSON file.

    Args:
        extraction: Validated extraction dict
        output_dir: Directory to save to

    Returns:
        Path to saved file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    doc_id = extraction["docId"]
    output_path = output_dir / f"{doc_id}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(extraction, f, indent=2, ensure_ascii=False)

    return output_path


# ---------------------------------------------------------------------------
# Phase 1: Non-negotiable quality gates (CPU deterministic, zero tokens)
# ---------------------------------------------------------------------------

# Gate thresholds — loaded from domain profile
GATE_THRESHOLDS: dict[str, Any] = dict(_profile["gate_thresholds"])
del _profile  # don't leak the full profile as a module attr


def _normalize_for_match(text: str) -> str:
    """Normalize text for substring matching: lowercase, collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def check_evidence_fidelity(
    extraction: dict[str, Any],
    source_text: str,
) -> dict[str, Any]:
    """Gate A: Check that evidence snippets actually appear in the source text.

    For each asserted relation with evidence, normalize both the snippet and
    the source text, then check for substring match.

    Args:
        extraction: Validated extraction dict
        source_text: The cleaned article text the model was given

    Returns:
        Dict with passed, match_rate, and failed_snippets list
    """
    asserted = [r for r in extraction.get("relations", []) if r.get("kind") == "asserted"]
    if not asserted:
        return {"passed": True, "match_rate": 1.0, "checked": 0, "failed_snippets": []}

    normalized_source = _normalize_for_match(source_text)

    total_snippets = 0
    matched = 0
    failed_snippets = []

    for rel in asserted:
        for ev in rel.get("evidence", []):
            snippet = ev.get("snippet", "")
            if not snippet:
                continue
            total_snippets += 1
            normalized_snippet = _normalize_for_match(snippet)
            if normalized_snippet in normalized_source:
                matched += 1
            else:
                failed_snippets.append({
                    "snippet": snippet[:200],
                    "source": rel.get("source", ""),
                    "rel": rel.get("rel", ""),
                    "target": rel.get("target", ""),
                })

    if total_snippets == 0:
        return {"passed": True, "match_rate": 1.0, "checked": 0, "failed_snippets": []}

    match_rate = matched / total_snippets
    threshold = GATE_THRESHOLDS["evidence_fidelity_min"]

    return {
        "passed": match_rate >= threshold,
        "match_rate": round(match_rate, 3),
        "checked": total_snippets,
        "matched": matched,
        "failed_snippets": failed_snippets,
    }


def check_orphan_endpoints(
    extraction: dict[str, Any],
) -> dict[str, Any]:
    """Gate B: Check that every relation endpoint maps to an extracted entity.

    Args:
        extraction: Validated extraction dict

    Returns:
        Dict with passed, orphan_rate, and orphans list
    """
    entity_names = {e.get("name", "").lower() for e in extraction.get("entities", [])}
    relations = extraction.get("relations", [])

    if not relations:
        return {"passed": True, "orphan_rate": 0.0, "orphans": []}

    orphans = []
    for rel in relations:
        source = rel.get("source", "")
        target = rel.get("target", "")
        if source.lower() not in entity_names:
            orphans.append({"endpoint": "source", "name": source, "rel": rel.get("rel", "")})
        if target.lower() not in entity_names:
            orphans.append({"endpoint": "target", "name": target, "rel": rel.get("rel", "")})

    orphan_rate = len(orphans) / (len(relations) * 2)  # 2 endpoints per relation
    threshold = GATE_THRESHOLDS["orphan_max"]

    return {
        "passed": orphan_rate <= threshold,
        "orphan_rate": round(orphan_rate, 3),
        "orphan_count": len(orphans),
        "orphans": orphans[:20],  # cap debug output
    }


def check_zero_value(
    extraction: dict[str, Any],
    source_text_length: int,
) -> dict[str, Any]:
    """Gate C: Catch schema-valid but empty/useless extractions.

    Args:
        extraction: Validated extraction dict
        source_text_length: Length of source document in chars

    Returns:
        Dict with passed and reason
    """
    min_chars = GATE_THRESHOLDS["zero_value_min_doc_chars"]
    if source_text_length < min_chars:
        return {"passed": True, "reason": "doc_too_short_to_gate"}

    n_entities = len(extraction.get("entities", []))
    n_relations = len(extraction.get("relations", []))

    min_entities = GATE_THRESHOLDS["zero_value_min_entities"]

    if n_entities == 0:
        return {"passed": False, "reason": f"zero_entities (doc={source_text_length} chars)"}

    if n_entities > 3 and n_relations == 0:
        return {"passed": False, "reason": f"no_relations ({n_entities} entities, 0 relations)"}

    return {"passed": True, "reason": "ok"}


def check_high_confidence_bad_evidence(
    extraction: dict[str, Any],
    source_text: str,
) -> dict[str, Any]:
    """Gate D: Detect the worst failure mode — high confidence + fabricated evidence.

    If a relation is asserted with high confidence but its evidence snippet
    can't be found in the source text, that's the most dangerous kind of
    hallucination (looks trustworthy, is fake).

    Args:
        extraction: Validated extraction dict
        source_text: The cleaned article text

    Returns:
        Dict with passed and flagged_relations list
    """
    normalized_source = _normalize_for_match(source_text)
    flagged = []

    for rel in extraction.get("relations", []):
        if rel.get("kind") != "asserted":
            continue
        high_conf_threshold = GATE_THRESHOLDS.get("high_confidence_threshold", 0.8)
        if rel.get("confidence", 0) < high_conf_threshold:
            continue

        for ev in rel.get("evidence", []):
            snippet = ev.get("snippet", "")
            if not snippet:
                continue
            normalized_snippet = _normalize_for_match(snippet)
            if normalized_snippet not in normalized_source:
                flagged.append({
                    "source": rel.get("source", ""),
                    "rel": rel.get("rel", ""),
                    "target": rel.get("target", ""),
                    "confidence": rel.get("confidence"),
                    "snippet": snippet[:200],
                })
                break  # one bad snippet per relation is enough

    return {
        "passed": len(flagged) == 0,
        "flagged_count": len(flagged),
        "flagged_relations": flagged[:10],  # cap debug output
    }


def run_quality_gates(
    extraction: dict[str, Any],
    source_text: str,
) -> dict[str, Any]:
    """Run all Phase 1 non-negotiable gates.

    Returns a combined result with per-gate details and an overall pass/fail.
    If any gate fails, the overall result is 'escalate'.

    Args:
        extraction: Validated extraction dict
        source_text: The cleaned article text

    Returns:
        Dict with overall_passed, gate results, and escalation_reasons
    """
    source_text_length = len(source_text)

    evidence = check_evidence_fidelity(extraction, source_text)
    orphans = check_orphan_endpoints(extraction)
    zero_value = check_zero_value(extraction, source_text_length)
    high_conf = check_high_confidence_bad_evidence(extraction, source_text)

    gates = {
        "evidence_fidelity": evidence,
        "orphan_endpoints": orphans,
        "zero_value": zero_value,
        "high_confidence_bad_evidence": high_conf,
    }

    escalation_reasons = []
    if not evidence["passed"]:
        escalation_reasons.append(
            f"evidence_fidelity: {evidence['match_rate']:.0%} "
            f"< {GATE_THRESHOLDS['evidence_fidelity_min']:.0%}"
        )
    if not orphans["passed"]:
        escalation_reasons.append(
            f"orphan_endpoints: {orphans['orphan_count']} orphans"
        )
    if not zero_value["passed"]:
        escalation_reasons.append(f"zero_value: {zero_value['reason']}")
    if not high_conf["passed"]:
        escalation_reasons.append(
            f"high_conf_bad_evidence: {high_conf['flagged_count']} flagged"
        )

    return {
        "overall_passed": all(g["passed"] for g in gates.values()),
        "gates": gates,
        "escalation_reasons": escalation_reasons,
    }


def load_extraction(
    doc_id: str,
    extractions_dir: Path,
) -> Optional[dict[str, Any]]:
    """Load extraction from JSON file.

    Args:
        doc_id: Document ID
        extractions_dir: Directory containing extractions

    Returns:
        Extraction dict or None if not found
    """
    path = extractions_dir / f"{doc_id}.json"
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def import_manual_extraction(
    input_file: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Import and validate manual extraction (Mode B).

    Args:
        input_file: Path to JSON file with extraction
        output_dir: Directory to save validated extraction

    Returns:
        Validated extraction dict

    Raises:
        ExtractionError: If validation fails
    """
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate against schema
    try:
        validate_extraction(data)
    except ValidationError as e:
        raise ExtractionError(str(e)) from e

    # Save to output directory
    save_extraction(data, output_dir)

    return data


