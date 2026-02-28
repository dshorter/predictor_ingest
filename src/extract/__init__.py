"""Extraction module for LLM-based entity and relation extraction.

Supports:
- Mode A: Automated extraction via LLM API
- Mode B: Manual extraction import with validation

Quality evaluation (Phase 0+1):
- Phase 0: Structured quality report per extraction (instrumentation)
- Phase 1: Non-negotiable CPU gates (evidence fidelity, orphan endpoints,
  zero-value, high-confidence + bad evidence)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from schema import (
    validate_extraction,
    ValidationError,
    ENTITY_TYPES as _ENTITY_TYPES_SET,
    RELATION_TYPES as _RELATION_TYPES_SET,
)


# Current extractor version - bump when prompts/schema change
# 1.0.0 — initial extraction prompts
# 2.0.0 — quality gates, escalation mode, relation normalization,
#          budget-based document selection, MENTIONS auto-generation
EXTRACTOR_VERSION = "2.0.0"

# Entity and relation types — derived from the single source of truth
# in schemas/extraction.json (loaded via schema module).
# Kept as sorted lists here because prompt templates and the OpenAI
# tool schema need a stable, ordered sequence.
ENTITY_TYPES: list[str] = sorted(_ENTITY_TYPES_SET)
RELATION_TYPES: list[str] = sorted(_RELATION_TYPES_SET)

# Map common LLM variations to canonical relation types
RELATION_NORMALIZATION = {
    "ANNOUNCED": "ANNOUNCES",
    "ANNOUNCING": "ANNOUNCES",
    "MENTIONED": "MENTIONS",
    "MENTIONING": "MENTIONS",
    "CITED": "CITES",
    "CITING": "CITES",
    "LAUNCHED_BY": "LAUNCHED",
    "PUBLISHED_BY": "PUBLISHED",
    "CREATED_BY": "CREATED",
    "FUNDED_BY": "FUNDED",
    "USED": "USES_TECH",
    "USING": "USES_TECH",
    "USES_TOOL": "USES_TECH",
    "DEVELOPED": "CREATED",
    "DEVELOPED_BY": "CREATED",
    "BUILT": "CREATED",
    "BUILT_BY": "CREATED",
    "FOUNDED": "CREATED",
    "FOUNDED_BY": "CREATED",
    "RELEASED": "LAUNCHED",
    "RELEASED_BY": "LAUNCHED",
    "PARTNERS_WITH": "PARTNERED_WITH",
    "PARTNERING_WITH": "PARTNERED_WITH",
    "OPERATED": "OPERATES",
    "OPERATED_BY": "OPERATES",
    "OPERATES_ON": "OPERATES",
    "IMPLEMENTS": "INTEGRATES_WITH",
    "IMPLEMENTED": "INTEGRATES_WITH",
    "IMPLEMENTED_BY": "INTEGRATES_WITH",
    "IMPLEMENTING": "INTEGRATES_WITH",
    "INTEGRATED_WITH": "INTEGRATES_WITH",
    "PROVIDES": "PRODUCES",
    "UPDATES": "UPDATED",
    "CREATES": "CREATED",
    "DISCOVERED": "CREATED",
    "COMPETED_IN": "EVALUATED_ON",
    # Past-tense of canonical present-tense relation types
    "PRODUCED": "PRODUCES",
    "MEASURED": "MEASURES",
    "AFFECTED": "AFFECTS",
    "PREDICTED": "PREDICTS",
    "DETECTED": "DETECTS",
    "MONITORED": "MONITORS",
    "REQUIRED": "REQUIRES",
    "DEPENDED_ON": "DEPENDS_ON",
    "INTEGRATED": "INTEGRATES_WITH",
    "GOVERNED": "GOVERNS",
    "REGULATED": "REGULATES",
    "COMPLIED_WITH": "COMPLIES_WITH",
    # Present-tense gerund forms of canonical types
    "PRODUCING": "PRODUCES",
    "MEASURING": "MEASURES",
    "AFFECTING": "AFFECTS",
    "PREDICTING": "PREDICTS",
    "DETECTING": "DETECTS",
    "MONITORING": "MONITORS",
    "REQUIRING": "REQUIRES",
    "GOVERNING": "GOVERNS",
    "REGULATING": "REGULATES",
    # Other common near-misses
    "TRAINED": "TRAINED_ON",
    "EVALUATED": "EVALUATED_ON",
    "DEPENDED": "DEPENDS_ON",
}


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
    # Normalize relation types
    for relation in data.get("relations", []):
        rel = relation.get("rel", "").upper()
        if rel in RELATION_NORMALIZATION:
            relation["rel"] = RELATION_NORMALIZATION[rel]
        elif rel not in RELATION_TYPES:
            # Try to match without underscores/hyphens
            normalized = rel.replace("-", "_").replace(" ", "_")
            if normalized in RELATION_NORMALIZATION:
                relation["rel"] = RELATION_NORMALIZATION[normalized]

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
    for date_obj in data.get("dates", []):
        if date_obj.get("start") is None:
            date_obj.pop("start", None)
        if date_obj.get("end") is None:
            date_obj.pop("end", None)

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
# Extraction quality scoring (for escalation mode)
# ---------------------------------------------------------------------------

# Thresholds represent "good extraction" targets — scores are proportional
# to how close the extraction is to these targets.  A cheap model that
# merely produces plausible-looking output shouldn't max out every signal.
QUALITY_THRESHOLDS = {
    "entity_density_target": 5.0,     # entities per 1000 chars — target, not floor
    "evidence_coverage_min": 0.8,     # fraction of asserted relations with evidence
    "avg_confidence_target": 0.85,    # cheap models output ~0.8; good ones are calibrated
    "relation_entity_ratio_target": 0.5,  # semantic relations / entities — 1:2 is solid
    "tech_terms_min": 2,              # AI articles should have ≥2 tech terms
    "relation_type_diversity_target": 6,  # distinct semantic relation types used
}

# Combined score below this triggers escalation
ESCALATION_THRESHOLD = 0.6


def score_extraction_quality(
    extraction: dict[str, Any],
    source_text_length: int,
) -> dict[str, Any]:
    """Score the quality of an extraction to decide if escalation is needed.

    Returns a dict with individual signal scores (0-1), a combined score,
    and whether escalation is recommended.

    Args:
        extraction: Validated extraction dict
        source_text_length: Length of the source document text in chars

    Returns:
        Dict with scores and escalation recommendation
    """
    entities = extraction.get("entities", [])
    relations = extraction.get("relations", [])
    tech_terms = extraction.get("techTerms", [])

    n_entities = len(entities)
    n_relations = len(relations)
    n_tech = len(tech_terms)

    # Semantic relations = everything except MENTIONS
    semantic_relations = [r for r in relations if r.get("rel") != "MENTIONS"]
    n_semantic = len(semantic_relations)

    # 1. Entity density: entities per 1000 chars (proportional, not binary)
    text_k = max(source_text_length / 1000, 0.1)
    entity_density = n_entities / text_k
    density_score = min(entity_density / QUALITY_THRESHOLDS["entity_density_target"], 1.0)

    # 2. Evidence coverage: fraction of asserted relations that have evidence
    asserted = [r for r in relations if r.get("kind") == "asserted"]
    if asserted:
        with_evidence = sum(1 for r in asserted if r.get("evidence"))
        evidence_coverage = with_evidence / len(asserted)
    else:
        # No asserted relations — could be fine (all inferred) or empty
        evidence_coverage = 1.0 if n_relations > 0 else 0.0
    evidence_score = min(evidence_coverage / QUALITY_THRESHOLDS["evidence_coverage_min"], 1.0)

    # 3. Average confidence — penalise suspiciously uniform high confidence.
    #    A well-calibrated model shouldn't output 0.9 for everything.
    if relations:
        confidences = [r.get("confidence", 0) for r in relations]
        avg_confidence = sum(confidences) / len(confidences)
        # Variance penalty: if stddev < 0.05 and avg > 0.8, model isn't
        # differentiating confidence — apply a 30% penalty.
        if len(confidences) > 2:
            mean_c = avg_confidence
            variance = sum((c - mean_c) ** 2 for c in confidences) / len(confidences)
            stddev = variance ** 0.5
            if stddev < 0.05 and avg_confidence > 0.8:
                avg_confidence *= 0.7  # penalise flat-high confidence
    else:
        avg_confidence = 0.0
    confidence_score = min(avg_confidence / QUALITY_THRESHOLDS["avg_confidence_target"], 1.0)

    # 4. Semantic relation-to-entity ratio (MENTIONS excluded)
    if n_entities > 0:
        rel_entity_ratio = n_semantic / n_entities
    else:
        rel_entity_ratio = 0.0
    connectivity_score = min(
        rel_entity_ratio / QUALITY_THRESHOLDS["relation_entity_ratio_target"], 1.0
    )

    # 5. Relation type diversity: how many distinct semantic relation types?
    #    Cheap models tend to emit only 2-3 types (USES_TECH, CREATED, etc.)
    #    while good extractions use 5+ distinct types.
    rel_types = {r.get("rel") for r in semantic_relations if r.get("rel")}
    n_rel_types = len(rel_types)
    diversity_target = QUALITY_THRESHOLDS["relation_type_diversity_target"]
    diversity_score = min(n_rel_types / diversity_target, 1.0)

    # 6. Tech terms presence
    tech_score = min(n_tech / QUALITY_THRESHOLDS["tech_terms_min"], 1.0)

    # Combined score (weighted — diversity and connectivity are the hardest
    # for cheap models to game, so they get the most weight)
    combined = (
        0.15 * density_score
        + 0.15 * evidence_score
        + 0.10 * confidence_score
        + 0.20 * connectivity_score
        + 0.25 * diversity_score
        + 0.15 * tech_score
    )

    return {
        "entity_density": round(entity_density, 2),
        "density_score": round(density_score, 2),
        "evidence_coverage": round(evidence_coverage, 2),
        "evidence_score": round(evidence_score, 2),
        "avg_confidence": round(avg_confidence, 2),
        "confidence_score": round(confidence_score, 2),
        "rel_entity_ratio": round(rel_entity_ratio, 2),
        "connectivity_score": round(connectivity_score, 2),
        "n_rel_types": n_rel_types,
        "diversity_score": round(diversity_score, 2),
        "n_tech_terms": n_tech,
        "tech_score": round(tech_score, 2),
        "combined_score": round(combined, 2),
        "escalate": combined < ESCALATION_THRESHOLD,
    }


# ---------------------------------------------------------------------------
# Phase 1: Non-negotiable quality gates (CPU deterministic, zero tokens)
# ---------------------------------------------------------------------------

# Gate thresholds — start conservative, tune after calibration data
GATE_THRESHOLDS = {
    "evidence_fidelity_min": 0.70,  # fraction of asserted snippets found in source
    "orphan_max": 0.0,              # fraction of relations with orphan endpoints
    "zero_value_min_entities": 1,   # minimum entities for non-trivial docs
    "zero_value_min_doc_chars": 500,  # docs shorter than this skip zero-value gate
}


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
        if rel.get("confidence", 0) < 0.8:
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


def evaluate_extraction(
    extraction: dict[str, Any],
    source_text: str,
) -> dict[str, Any]:
    """Full quality evaluation: gates first, then scoring.

    This is the unified entry point for Phase 0+1 quality evaluation.
    Gates are checked first — if any gate fails, escalation is immediate
    regardless of the quality score. If all gates pass, the existing
    scoring function determines whether to escalate.

    Args:
        extraction: Validated extraction dict
        source_text: The cleaned article text the model was given

    Returns:
        Dict with:
            escalate: bool — should we escalate to specialist?
            decision: str — 'accept' or 'escalate'
            decision_reason: str — why
            gates: gate results
            quality: scoring results
    """
    source_text_length = len(source_text)

    # Phase 1: Run non-negotiable gates
    gate_results = run_quality_gates(extraction, source_text)

    # Phase existing: Run quality scoring
    quality = score_extraction_quality(extraction, source_text_length)

    if not gate_results["overall_passed"]:
        # Gate failure — escalate immediately regardless of score
        reason = "gate_failed: " + "; ".join(gate_results["escalation_reasons"])
        return {
            "escalate": True,
            "decision": "escalate",
            "decision_reason": reason,
            "gates": gate_results,
            "quality": quality,
        }

    if quality["escalate"]:
        # Gates passed but score is low
        return {
            "escalate": True,
            "decision": "escalate",
            "decision_reason": f"quality_low: score={quality['combined_score']:.2f}",
            "gates": gate_results,
            "quality": quality,
        }

    return {
        "escalate": False,
        "decision": "accept",
        "decision_reason": "gates_passed+quality_ok",
        "gates": gate_results,
        "quality": quality,
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


# ---------------------------------------------------------------------------
# Shadow mode comparison utilities
# ---------------------------------------------------------------------------


def compute_entity_overlap(
    primary: dict[str, Any],
    understudy: dict[str, Any],
) -> float:
    """Compute entity name overlap between two extractions.

    Args:
        primary: Primary extraction dict
        understudy: Understudy extraction dict

    Returns:
        Overlap percentage (0-100)
    """
    primary_names = {e.get("name", "").lower() for e in primary.get("entities", [])}
    understudy_names = {e.get("name", "").lower() for e in understudy.get("entities", [])}

    if not primary_names:
        return 100.0 if not understudy_names else 0.0

    intersection = primary_names & understudy_names
    return len(intersection) / len(primary_names) * 100


def compute_relation_overlap(
    primary: dict[str, Any],
    understudy: dict[str, Any],
) -> float:
    """Compute relation overlap between two extractions.

    Relations are compared by (source, rel, target) tuples, case-insensitive.

    Args:
        primary: Primary extraction dict
        understudy: Understudy extraction dict

    Returns:
        Overlap percentage (0-100)
    """
    def relation_key(r: dict[str, Any]) -> tuple[str, str, str]:
        return (
            r.get("source", "").lower(),
            r.get("rel", "").upper(),
            r.get("target", "").lower(),
        )

    primary_rels = {relation_key(r) for r in primary.get("relations", [])}
    understudy_rels = {relation_key(r) for r in understudy.get("relations", [])}

    if not primary_rels:
        return 100.0 if not understudy_rels else 0.0

    intersection = primary_rels & understudy_rels
    return len(intersection) / len(primary_rels) * 100


def compare_extractions(
    primary: dict[str, Any],
    understudy: dict[str, Any],
    understudy_model: str,
    schema_valid: bool,
    parse_error: Optional[str] = None,
    primary_duration_ms: Optional[int] = None,
    understudy_duration_ms: Optional[int] = None,
) -> dict[str, Any]:
    """Compare primary and understudy extractions for shadow mode tracking.

    Args:
        primary: Primary (Sonnet) extraction dict
        understudy: Understudy extraction dict (may be empty if failed)
        understudy_model: Model name of understudy
        schema_valid: Whether understudy passed schema validation
        parse_error: Error message if understudy failed
        primary_duration_ms: Primary extraction time
        understudy_duration_ms: Understudy extraction time

    Returns:
        Comparison stats dict ready for insert_extraction_comparison()
    """
    primary_entities = len(primary.get("entities", []))
    primary_relations = len(primary.get("relations", []))
    primary_tech_terms = len(primary.get("techTerms", []))

    if schema_valid and understudy:
        understudy_entities = len(understudy.get("entities", []))
        understudy_relations = len(understudy.get("relations", []))
        understudy_tech_terms = len(understudy.get("techTerms", []))
        entity_overlap = compute_entity_overlap(primary, understudy)
        relation_overlap = compute_relation_overlap(primary, understudy)
    else:
        understudy_entities = None
        understudy_relations = None
        understudy_tech_terms = None
        entity_overlap = None
        relation_overlap = None

    return {
        "doc_id": primary.get("docId", ""),
        "understudy_model": understudy_model,
        "schema_valid": schema_valid,
        "parse_error": parse_error,
        "primary_entities": primary_entities,
        "primary_relations": primary_relations,
        "primary_tech_terms": primary_tech_terms,
        "understudy_entities": understudy_entities,
        "understudy_relations": understudy_relations,
        "understudy_tech_terms": understudy_tech_terms,
        "entity_overlap_pct": entity_overlap,
        "relation_overlap_pct": relation_overlap,
        "primary_duration_ms": primary_duration_ms,
        "understudy_duration_ms": understudy_duration_ms,
    }
