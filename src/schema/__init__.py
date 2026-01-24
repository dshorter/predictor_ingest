"""Schema validation for extraction output.

Validates extraction JSON against the schema defined in AGENTS.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


def _schema_dir() -> Path:
    """Return path to schemas directory."""
    return Path(__file__).resolve().parents[2] / "schemas"


def _load_schema() -> dict:
    """Load the extraction JSON schema."""
    schema_path = _schema_dir() / "extraction.json"
    with open(schema_path) as f:
        return json.load(f)


# Entity types from AGENTS.md
ENTITY_TYPES = frozenset([
    "Org", "Person", "Program", "Tool", "Model", "Dataset",
    "Benchmark", "Paper", "Repo", "Document", "Tech", "Topic",
    "Event", "Location", "Other",
])

# Relation types from AGENTS.md
RELATION_TYPES = frozenset([
    "MENTIONS", "CITES", "ANNOUNCES", "REPORTED_BY",
    "LAUNCHED", "PUBLISHED", "UPDATED", "FUNDED", "PARTNERED_WITH",
    "ACQUIRED", "HIRED", "CREATED", "OPERATES", "GOVERNED_BY",
    "GOVERNS", "REGULATES", "COMPLIES_WITH",
    "USES_TECH", "USES_MODEL", "USES_DATASET", "TRAINED_ON",
    "EVALUATED_ON", "INTEGRATES_WITH", "DEPENDS_ON", "REQUIRES",
    "PRODUCES", "MEASURES", "AFFECTS",
    "PREDICTS", "DETECTS", "MONITORS",
])

# Relation kinds
RELATION_KINDS = frozenset(["asserted", "inferred", "hypothesis"])


def validate_extraction(data: dict[str, Any]) -> None:
    """Validate a complete extraction output.

    Args:
        data: Extraction output dictionary

    Raises:
        ValidationError: If validation fails
    """
    schema = _load_schema()
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        # Extract the field name from the error path
        field = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else e.validator_value
        if not field and "required" in str(e.message):
            # Extract field name from "required" error message
            field = e.message.split("'")[1] if "'" in e.message else "unknown"
        raise ValidationError(f"Validation failed for {field}: {e.message}") from e

    # Additional semantic validations
    for relation in data.get("relations", []):
        _validate_relation_semantics(relation)


def validate_entity(data: dict[str, Any]) -> None:
    """Validate an entity object.

    Args:
        data: Entity dictionary

    Raises:
        ValidationError: If validation fails
    """
    if "name" not in data:
        raise ValidationError("Validation failed for name: 'name' is a required property")
    if "type" not in data:
        raise ValidationError("Validation failed for type: 'type' is a required property")
    if data.get("type") not in ENTITY_TYPES:
        raise ValidationError(
            f"Validation failed for type: '{data.get('type')}' is not a valid entity type"
        )


def validate_relation(data: dict[str, Any]) -> None:
    """Validate a relation object.

    Args:
        data: Relation dictionary

    Raises:
        ValidationError: If validation fails
    """
    required = ["source", "rel", "target", "kind", "confidence"]
    for field in required:
        if field not in data:
            raise ValidationError(f"Validation failed for {field}: '{field}' is a required property")

    if data.get("kind") not in RELATION_KINDS:
        raise ValidationError(
            f"Validation failed for kind: '{data.get('kind')}' is not valid"
        )

    if data.get("rel") not in RELATION_TYPES:
        raise ValidationError(
            f"Validation failed for rel: '{data.get('rel')}' is not a valid relation type"
        )

    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        raise ValidationError(
            f"Validation failed for confidence: must be between 0 and 1"
        )

    _validate_relation_semantics(data)


def _validate_relation_semantics(data: dict[str, Any]) -> None:
    """Validate semantic rules for relations.

    Per AGENTS.md: Asserted relations MUST include evidence.
    """
    if data.get("kind") == "asserted":
        evidence = data.get("evidence", [])
        if not evidence:
            raise ValidationError(
                "Validation failed for evidence: asserted relations MUST have non-empty evidence"
            )


def validate_evidence(data: dict[str, Any]) -> None:
    """Validate an evidence object.

    Args:
        data: Evidence dictionary

    Raises:
        ValidationError: If validation fails
    """
    required = ["docId", "url", "snippet"]
    for field in required:
        if field not in data:
            raise ValidationError(f"Validation failed for {field}: '{field}' is a required property")

    # published can be string or null, but must be present
    # Actually per schema, published is not strictly required, just snippet, docId, url
    # But our tests expect it to be validated if missing
    # Let me check the schema... published has type ["string", "null"] but is not in required
    # So we don't need to validate published presence
