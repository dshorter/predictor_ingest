"""Domain-aware extraction prompts and tool schemas.

Loads prompt templates from the active domain's prompts/ directory and
populates them with domain-specific values (entity types, relation types,
suppressed entities, base relation) from the domain profile.

The tool schema (OPENAI_EXTRACTION_TOOL) is also built dynamically from
the domain profile so that entity and relation type enums match the
active domain.

See docs/architecture/domain-separation.md for boundary rules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from domain import get_active_profile
from schema import ENTITY_TYPES, RELATION_TYPES


# --- Domain-derived values ---
_profile = get_active_profile()
_ENTITY_TYPES_LIST: list[str] = sorted(ENTITY_TYPES)
_RELATION_TYPES_LIST: list[str] = sorted(RELATION_TYPES)

SUPPRESSED_ENTITIES: list[str] = list(_profile.get("suppressed_entities", []))
_SUPPRESSED_STR = ", ".join(f'"{t}"' for t in SUPPRESSED_ENTITIES[:15])

_BASE_RELATION: str = _profile["base_relation"]
_DOMAIN_DIR: Path = _profile["_domain_dir"]
_PROMPTS_DIR: Path = _DOMAIN_DIR / _profile.get("prompts", {}).get("dir", "prompts")


# --- Template loading ---

def _load_template(filename: str) -> str:
    """Load a prompt template file from the domain's prompts directory.

    Args:
        filename: Template filename (e.g. "system.txt")

    Returns:
        Template string with {placeholders} intact

    Raises:
        FileNotFoundError: If the template file does not exist
    """
    path = _PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Prompt template not found: {path}\n"
            f"Domain '{_profile.get('_domain_slug', '?')}' must provide "
            f"prompts/{filename}"
        )
    return path.read_text(encoding="utf-8")


def _template_vars(
    doc: Optional[dict[str, Any]] = None,
    extractor_version: str = "",
) -> dict[str, str]:
    """Build the variable dict for prompt template interpolation.

    Args:
        doc: Optional document dict (for per-document templates)
        extractor_version: Extractor version string

    Returns:
        Dict of {placeholder: value} for str.format_map()
    """
    vars_ = {
        "extractor_version": extractor_version,
        "entity_types": ", ".join(_ENTITY_TYPES_LIST),
        "relation_types": ", ".join(_RELATION_TYPES_LIST),
        "suppressed_entities_sample": _SUPPRESSED_STR,
        "base_relation": _BASE_RELATION,
    }
    if doc:
        vars_.update({
            "docId": doc.get("docId", ""),
            "title": doc.get("title", "Unknown"),
            "url": doc.get("url", "Unknown"),
            "published": doc.get("published", "Unknown"),
            "text": doc.get("text", ""),
        })
    return vars_


# Cache loaded templates (they don't change within a run)
_SYSTEM_TEMPLATE: Optional[str] = None
_USER_TEMPLATE: Optional[str] = None
_SINGLE_MSG_TEMPLATE: Optional[str] = None


def _get_system_template() -> str:
    global _SYSTEM_TEMPLATE
    if _SYSTEM_TEMPLATE is None:
        prompts_cfg = _profile.get("prompts", {})
        _SYSTEM_TEMPLATE = _load_template(prompts_cfg.get("system_prompt", "system.txt"))
    return _SYSTEM_TEMPLATE


def _get_user_template() -> str:
    global _USER_TEMPLATE
    if _USER_TEMPLATE is None:
        prompts_cfg = _profile.get("prompts", {})
        _USER_TEMPLATE = _load_template(prompts_cfg.get("user_prompt", "user.txt"))
    return _USER_TEMPLATE


def _get_single_message_template() -> str:
    global _SINGLE_MSG_TEMPLATE
    if _SINGLE_MSG_TEMPLATE is None:
        prompts_cfg = _profile.get("prompts", {})
        _SINGLE_MSG_TEMPLATE = _load_template(
            prompts_cfg.get("single_message_prompt", "single_message.txt")
        )
    return _SINGLE_MSG_TEMPLATE


# --- Public API (same signatures as before) ---

def build_extraction_prompt(
    doc: dict[str, Any],
    extractor_version: str,
) -> str:
    """Build prompt for LLM extraction (single-message style).

    Loads the single_message.txt template from the active domain's
    prompts directory and fills in document and domain values.

    Args:
        doc: Document dict with docId, title, text, url, published
        extractor_version: Version string to include in output

    Returns:
        Prompt string for LLM
    """
    template = _get_single_message_template()
    return template.format_map(_template_vars(doc, extractor_version))


def build_extraction_system_prompt(
    extractor_version: str,
) -> str:
    """Build the static system prompt for extraction (cacheable prefix).

    Loads system.txt from the active domain's prompts directory.

    Args:
        extractor_version: Version string to include in output

    Returns:
        System prompt string
    """
    template = _get_system_template()
    return template.format_map(_template_vars(extractor_version=extractor_version))


def build_extraction_user_prompt(doc: dict[str, Any]) -> str:
    """Build the per-document user prompt (variable part).

    Loads user.txt from the active domain's prompts directory.

    Args:
        doc: Document dict with docId, title, text, url, published

    Returns:
        User prompt string
    """
    template = _get_user_template()
    return template.format_map(_template_vars(doc))


# --- OpenAI tool schema (built from domain profile) ---

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
                                "enum": _ENTITY_TYPES_LIST,
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
                                "enum": _RELATION_TYPES_LIST,
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
