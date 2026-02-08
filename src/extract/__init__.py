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


class ExtractionError(Exception):
    """Raised when extraction fails."""

    pass


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
