"""Extraction module for LLM-based entity and relation extraction.

Supports:
- Mode A: Automated extraction via LLM API
- Mode B: Manual extraction import with validation
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from schema import validate_extraction, ValidationError


# Current extractor version - bump when prompts/schema change
EXTRACTOR_VERSION = "1.0.0"

# Entity types from AGENTS.md
ENTITY_TYPES = [
    "Org", "Person", "Program", "Tool", "Model", "Dataset",
    "Benchmark", "Paper", "Repo", "Document", "Tech", "Topic",
    "Event", "Location", "Other",
]

# Relation types from AGENTS.md
RELATION_TYPES = [
    "MENTIONS", "CITES", "ANNOUNCES", "REPORTED_BY",
    "LAUNCHED", "PUBLISHED", "UPDATED", "FUNDED", "PARTNERED_WITH",
    "ACQUIRED", "HIRED", "CREATED", "OPERATES", "GOVERNED_BY",
    "GOVERNS", "REGULATES", "COMPLIES_WITH",
    "USES_TECH", "USES_MODEL", "USES_DATASET", "TRAINED_ON",
    "EVALUATED_ON", "INTEGRATES_WITH", "DEPENDS_ON", "REQUIRES",
    "PRODUCES", "MEASURES", "AFFECTS",
    "PREDICTS", "DETECTS", "MONITORS",
]

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


def build_extraction_prompt(
    doc: dict[str, Any],
    extractor_version: Optional[str] = None,
) -> str:
    """Build prompt for LLM extraction.

    Args:
        doc: Document dict with docId, title, text, url, published
        extractor_version: Version string to include in output

    Returns:
        Prompt string for LLM
    """
    version = extractor_version or EXTRACTOR_VERSION

    prompt = f"""Extract entities, relationships, and technical terms from the following document.

## Document Metadata
- docId: {doc['docId']}
- Title: {doc.get('title', 'Unknown')}
- URL: {doc.get('url', 'Unknown')}
- Published: {doc.get('published', 'Unknown')}

## Document Text
{doc['text']}

## Instructions

Extract the following and return as JSON:

1. **entities**: List of entities mentioned in the document
   - name: Surface form of the entity name
   - type: One of {ENTITY_TYPES}
   - aliases: Optional list of alternative names
   - idHint: Optional suggested canonical ID (e.g., "org:openai")

2. **relations**: Relationships between entities
   - source: Entity name
   - rel: One of {RELATION_TYPES}
   - target: Entity name
   - kind: "asserted" (explicitly stated), "inferred", or "hypothesis"
   - confidence: 0.0 to 1.0
   - evidence: For asserted relations, include at least one evidence object:
     - docId: "{doc['docId']}"
     - url: "{doc.get('url', '')}"
     - published: "{doc.get('published', '')}"
     - snippet: Short quote from the text (≤200 chars)

3. **techTerms**: List of technical terms, technologies, or concepts mentioned

4. **dates**: Important dates mentioned
   - text: Raw date text (e.g., "this fall", "Q3 2025")
   - start/end: ISO dates if determinable

5. **notes**: Any ambiguities or extraction notes

## Output Format

Return valid JSON with this structure:
```json
{{
  "docId": "{doc['docId']}",
  "extractorVersion": "{version}",
  "entities": [...],
  "relations": [...],
  "techTerms": [...],
  "dates": [...],
  "notes": [...]
}}
```

## Critical Rules
- Asserted relations MUST include evidence with a snippet from the document
- Do not fabricate entities or relations not supported by the text
- Mark uncertain relations as "inferred" or "hypothesis"
- Keep evidence snippets short (≤200 chars)
"""

    return prompt


def build_extraction_system_prompt(
    extractor_version: Optional[str] = None,
) -> str:
    """Build the static system prompt for extraction (cacheable prefix).

    This contains all instructions, schema rules, and enums. It stays
    identical across documents so OpenAI can cache it.

    Args:
        extractor_version: Version string to include in output

    Returns:
        System prompt string
    """
    version = extractor_version or EXTRACTOR_VERSION

    return f"""You are an entity/relation extraction system for AI-domain articles.
Your job is to extract structured data and return it via the emit_extraction tool.

## Extractor Version
{version}

## Entity Types (use exactly these values)
{', '.join(ENTITY_TYPES)}

## Relation Types (use exactly these values)
{', '.join(RELATION_TYPES)}

## Extraction Rules

1. **entities**: Extract all notable entities (organizations, people, models, tools, etc.)
   - name: Surface form as it appears in the text
   - type: Must be one of the entity types listed above
   - aliases: Optional alternative names
   - idHint: Optional canonical ID suggestion (e.g., "org:openai")

2. **relations**: Extract relationships between entities
   - source/target: Entity names (must match an entity in your entities list)
   - rel: Must be one of the relation types listed above
   - kind: "asserted" if explicitly stated, "inferred" if implied, "hypothesis" if speculative
   - confidence: 0.0 to 1.0
   - evidence: REQUIRED for asserted relations — include docId, url, published, and a short snippet (≤200 chars) from the source text

3. **techTerms**: List of technical terms, technologies, or concepts mentioned

4. **dates**: Important dates mentioned
   - text: Raw date text as it appears (e.g., "this fall", "Q3 2025")
   - start/end: ISO dates if determinable
   - resolution: "exact", "range", "anchored_to_published", or "unknown"

5. **notes**: Any ambiguities or extraction warnings

## Critical Rules
- Asserted relations MUST include evidence with a snippet from the document
- Do NOT fabricate entities, dates, or relations not supported by the text
- Mark uncertain relations as "inferred" or "hypothesis"
- Keep evidence snippets short (≤200 chars)
- Prefer MENTIONS as the base relation; only use semantic relations when evidence supports them
"""


def build_extraction_user_prompt(doc: dict[str, Any]) -> str:
    """Build the per-document user prompt (variable part).

    This is the part that changes per document. It goes after the
    cached system prompt.

    Args:
        doc: Document dict with docId, title, text, url, published

    Returns:
        User prompt string
    """
    return f"""Extract entities, relations, and tech terms from this document.

## Document Metadata
- docId: {doc['docId']}
- Title: {doc.get('title', 'Unknown')}
- URL: {doc.get('url', 'Unknown')}
- Published: {doc.get('published', 'Unknown')}

## Document Text
{doc['text']}

Call the emit_extraction tool with the complete extraction results."""


# OpenAI strict tool schema for extraction.
# All objects have additionalProperties: false and all properties in required,
# as mandated by OpenAI's strict mode.
OPENAI_EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "emit_extraction",
        "description": "Emit the structured extraction results for this document.",
        "strict": True,
        "parameters": {
            "type": "object",
            "required": [
                "docId", "extractorVersion", "entities", "relations",
                "techTerms", "dates", "notes",
            ],
            "additionalProperties": False,
            "properties": {
                "docId": {"type": "string", "description": "Document identifier"},
                "extractorVersion": {"type": "string", "description": "Extractor version"},
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "type", "aliases", "idHint"],
                        "additionalProperties": False,
                        "properties": {
                            "name": {"type": "string", "description": "Surface form of entity name"},
                            "type": {
                                "type": "string",
                                "enum": ENTITY_TYPES,
                            },
                            "aliases": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Alternative names",
                            },
                            "idHint": {
                                "type": ["string", "null"],
                                "description": "Suggested canonical ID (e.g. org:openai), or null",
                            },
                        },
                    },
                },
                "relations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
                            "source", "rel", "target", "kind",
                            "confidence", "verbRaw", "evidence",
                        ],
                        "additionalProperties": False,
                        "properties": {
                            "source": {"type": "string", "description": "Source entity name"},
                            "rel": {
                                "type": "string",
                                "enum": RELATION_TYPES,
                            },
                            "target": {"type": "string", "description": "Target entity name"},
                            "kind": {
                                "type": "string",
                                "enum": ["asserted", "inferred", "hypothesis"],
                            },
                            "confidence": {"type": "number", "description": "0.0 to 1.0"},
                            "verbRaw": {
                                "type": ["string", "null"],
                                "description": "Original verb from text, or null",
                            },
                            "evidence": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["docId", "url", "published", "snippet"],
                                    "additionalProperties": False,
                                    "properties": {
                                        "docId": {"type": "string"},
                                        "url": {"type": "string"},
                                        "published": {
                                            "type": ["string", "null"],
                                            "description": "ISO date or null",
                                        },
                                        "snippet": {
                                            "type": "string",
                                            "description": "Short quote ≤200 chars",
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
                "techTerms": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "dates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["text", "start", "end", "resolution", "anchor"],
                        "additionalProperties": False,
                        "properties": {
                            "text": {"type": "string", "description": "Raw date text"},
                            "start": {
                                "type": ["string", "null"],
                                "description": "ISO date start, or null",
                            },
                            "end": {
                                "type": ["string", "null"],
                                "description": "ISO date end, or null",
                            },
                            "resolution": {
                                "type": ["string", "null"],
                                "enum": ["exact", "range", "anchored_to_published", "unknown", None],
                                "description": "Date resolution type, or null",
                            },
                            "anchor": {
                                "type": ["string", "null"],
                                "description": "Reference date for anchoring, or null",
                            },
                        },
                    },
                },
                "notes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Warnings, ambiguity flags",
                },
            },
        },
    },
}


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

# Thresholds for "good enough" extraction from a cheap model
QUALITY_THRESHOLDS = {
    "entity_density_min": 3.0,    # entities per 1000 chars of source text
    "evidence_coverage_min": 0.8, # fraction of asserted relations with evidence
    "avg_confidence_min": 0.6,    # mean confidence across all relations
    "relation_entity_ratio_min": 0.1,  # relations / entities (finding connections)
    "tech_terms_min": 1,          # at least 1 tech term for AI articles
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

    # 1. Entity density: entities per 1000 chars
    text_k = max(source_text_length / 1000, 0.1)
    entity_density = n_entities / text_k
    density_score = min(entity_density / QUALITY_THRESHOLDS["entity_density_min"], 1.0)

    # 2. Evidence coverage: fraction of asserted relations that have evidence
    asserted = [r for r in relations if r.get("kind") == "asserted"]
    if asserted:
        with_evidence = sum(1 for r in asserted if r.get("evidence"))
        evidence_coverage = with_evidence / len(asserted)
    else:
        # No asserted relations — could be fine (all inferred) or empty
        evidence_coverage = 1.0 if n_relations > 0 else 0.0
    evidence_score = min(evidence_coverage / QUALITY_THRESHOLDS["evidence_coverage_min"], 1.0)

    # 3. Average confidence across all relations
    if relations:
        confidences = [r.get("confidence", 0) for r in relations]
        avg_confidence = sum(confidences) / len(confidences)
    else:
        avg_confidence = 0.0
    confidence_score = min(avg_confidence / QUALITY_THRESHOLDS["avg_confidence_min"], 1.0)

    # 4. Semantic Relation-to-entity ratio
    # Filter out MENTIONS to ensure the model found actual structural connections
    semantic_relations = [r for r in relations if r.get("rel") != "MENTIONS"]
    n_semantic_relations = len(semantic_relations)

    if n_entities > 0:
        rel_entity_ratio = n_semantic_relations / n_entities
    else:
        rel_entity_ratio = 0.0
        
    connectivity_score = min(
        rel_entity_ratio / QUALITY_THRESHOLDS["relation_entity_ratio_min"], 1.0
    )

    # 5. Tech terms presence
    tech_score = 1.0 if n_tech >= QUALITY_THRESHOLDS["tech_terms_min"] else 0.5

    # Combined score (weighted)
    combined = (
        0.30 * density_score
        + 0.25 * evidence_score
        + 0.20 * confidence_score
        + 0.15 * connectivity_score
        + 0.10 * tech_score
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
        "n_tech_terms": n_tech,
        "tech_score": round(tech_score, 2),
        "combined_score": round(combined, 2),
        "escalate": combined < ESCALATION_THRESHOLD,
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
