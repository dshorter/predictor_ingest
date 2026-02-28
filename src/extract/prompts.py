"""AI-domain extraction prompts and tool schemas.

This module contains domain-specific content for the AI/ML knowledge
graph pipeline.  It is intentionally separated from the framework-level
extraction logic (quality gates, scoring, normalization) in __init__.py
to respect the domain-separation boundary documented in
docs/architecture/domain-separation.md.

If you adapt this pipeline to another domain, create a parallel module
(e.g. prompts_biotech.py) and swap it in via config — do NOT mix domain
content into the framework modules.
"""

from __future__ import annotations

from typing import Any, Optional

from schema import ENTITY_TYPES, RELATION_TYPES


# Stable sorted lists for prompt interpolation and tool schemas
_ENTITY_TYPES_LIST: list[str] = sorted(ENTITY_TYPES)
_RELATION_TYPES_LIST: list[str] = sorted(RELATION_TYPES)

# Hyper-generic terms that are noise in an AI-domain knowledge graph.
# These should NOT be extracted as standalone entities. They are too broad
# to create meaningful graph structure — they would connect to nearly
# everything and obscure real signals.
SUPPRESSED_ENTITIES: list[str] = [
    "AI", "artificial intelligence",
    "machine learning", "ML",
    "deep learning", "DL",
    "technology", "tech",
    "software", "hardware",
    "data", "algorithm", "algorithms",
    "computer", "computing",
    "internet", "web", "cloud",
    "system", "platform", "solution",
    "research", "science",
    "model", "models",        # too generic; use the specific model name
    "tool", "tools",          # too generic; use the specific tool name
    "API", "APIs",
    "app", "application",
    "startup", "company",
    "industry", "market",
]

_SUPPRESSED_STR = ", ".join(f'"{t}"' for t in SUPPRESSED_ENTITIES[:15])  # first 15 for prompt brevity

# Current extractor version — imported from the parent package at call
# time to avoid circular imports.  Callers pass it in explicitly.


def build_extraction_prompt(
    doc: dict[str, Any],
    extractor_version: str,
) -> str:
    """Build prompt for LLM extraction (single-message Anthropic style).

    Args:
        doc: Document dict with docId, title, text, url, published
        extractor_version: Version string to include in output

    Returns:
        Prompt string for LLM
    """
    return f"""Extract entities, relationships, and technical terms from the following document.

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
   - type: One of {_ENTITY_TYPES_LIST}
   - aliases: Optional list of alternative names
   - idHint: Optional suggested canonical ID (e.g., "org:openai")

2. **relations**: Relationships between entities
   - source: Entity name
   - rel: One of {_RELATION_TYPES_LIST}
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
  "extractorVersion": "{extractor_version}",
  "entities": [...],
  "relations": [...],
  "techTerms": [...],
  "dates": [...],
  "notes": [...]
}}
```

## Entity Specificity
This is an AI-domain graph. Do NOT extract generic terms like {_SUPPRESSED_STR}
as standalone entities. Extract SPECIFIC names (e.g., "GPT-4o" not "model",
"OpenAI" not "company"). Use full formal names for orgs. Put broad concepts
in techTerms[] instead.

## Critical Rules
- Asserted relations MUST include evidence with a snippet from the document
- Do not fabricate entities or relations not supported by the text
- Mark uncertain relations as "inferred" or "hypothesis"
- Keep evidence snippets short (≤200 chars)
"""


def build_extraction_system_prompt(
    extractor_version: str,
) -> str:
    """Build the static system prompt for extraction (cacheable prefix).

    This contains all instructions, schema rules, and enums. It stays
    identical across documents so OpenAI can cache it.

    Args:
        extractor_version: Version string to include in output

    Returns:
        System prompt string
    """
    return f"""You are an entity/relation extraction system for AI-domain articles.
Your job is to extract structured data and return it via the emit_extraction tool.

## Extractor Version
{extractor_version}

## Entity Types (use exactly these values)
{', '.join(_ENTITY_TYPES_LIST)}

## Relation Types (use exactly these values)
{', '.join(_RELATION_TYPES_LIST)}

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

## Entity Specificity Rules
This is an AI-domain knowledge graph. Do NOT extract hyper-generic terms as
standalone entities — they connect to everything and obscure real signals.

**Suppress these as entities:** {_SUPPRESSED_STR}, and similar umbrella terms.

Instead:
- Extract the SPECIFIC entity: "GPT-4o" not "model", "LangChain" not "tool",
  "OpenAI" not "company", "transformer architecture" not "AI"
- Use full formal names for organizations: "Block Inc." not "Block",
  "Alphabet" or "Google DeepMind" not just "Google"
- If a generic term like "AI" appears only as a modifier ("AI startup",
  "AI safety"), extract the full noun phrase ("AI safety") as a Topic, or
  extract the specific entity being described
- techTerms[] is the right place for broad concepts like "machine learning"
  or "reinforcement learning" — they do NOT need to be graph entities

## Critical Rules
- Asserted relations MUST include evidence with a snippet from the document
- Do NOT fabricate entities, dates, or relations not supported by the text
- Mark uncertain relations as "inferred" or "hypothesis"
- Keep evidence snippets short (≤200 chars)
- Prefer MENTIONS as the base relation; only use semantic relations when evidence supports them
- Every relation source and target MUST exactly match an entity name in your entities list
- Evidence snippets MUST be direct quotes or close paraphrases from the document text, not recalled from memory
- Non-trivial documents should produce at least 3 relations connecting entities
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
