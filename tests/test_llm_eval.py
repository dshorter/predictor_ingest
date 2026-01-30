"""LLM evaluation harness for extraction pipeline.

Measures JSON schema compliance of LLM extraction outputs.
Designed to run in two modes:

1. Offline (default): Uses fixture responses to validate the harness itself.
   pytest tests/test_llm_eval.py -v

2. Live: Calls real LLM APIs and measures compliance against sample articles.
   pytest tests/test_llm_eval.py -v -m llm_live --provider=openai
   Requires API keys in environment variables.

See docs/llm-selection.md for evaluation criteria and methodology.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pytest

from extract import (
    build_extraction_prompt,
    parse_extraction_response,
    ExtractionError,
    ENTITY_TYPES,
    RELATION_TYPES,
)
from schema import validate_extraction, ValidationError, RELATION_KINDS


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "llm_eval"
ARTICLES_PATH = FIXTURES_DIR / "sample_articles.json"
RESPONSES_PATH = FIXTURES_DIR / "sample_responses.json"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def load_sample_articles() -> list[dict[str, Any]]:
    """Load sample articles from fixture file."""
    with open(ARTICLES_PATH) as f:
        return json.load(f)


def load_sample_responses() -> dict[str, Any]:
    """Load sample LLM responses from fixture file."""
    with open(RESPONSES_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Evaluation result dataclass
# ---------------------------------------------------------------------------


@dataclass
class EvalResult:
    """Result of evaluating a single LLM response."""

    doc_id: str
    model: str
    json_parseable: bool = False
    schema_valid: bool = False
    schema_valid_after_recovery: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    entity_count: int = 0
    relation_count: int = 0
    tech_term_count: int = 0
    invalid_entity_types: list[str] = field(default_factory=list)
    invalid_relation_types: list[str] = field(default_factory=list)
    invalid_relation_kinds: list[str] = field(default_factory=list)
    asserted_without_evidence: int = 0
    confidence_out_of_range: int = 0
    evidence_snippet_lengths: list[int] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Whether this response passes schema validation (with or without recovery)."""
        return self.schema_valid or self.schema_valid_after_recovery


@dataclass
class ModelEvalSummary:
    """Aggregated results for a single model across all test articles."""

    model: str
    results: list[EvalResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def schema_pass_rate(self) -> float:
        """Fraction of responses that pass schema validation directly."""
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.schema_valid) / len(self.results)

    @property
    def recovery_pass_rate(self) -> float:
        """Fraction passing after post-processing recovery."""
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.passed) / len(self.results)

    @property
    def json_parse_rate(self) -> float:
        """Fraction that are valid JSON (before schema check)."""
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.json_parseable) / len(self.results)

    @property
    def all_invalid_entity_types(self) -> set[str]:
        s: set[str] = set()
        for r in self.results:
            s.update(r.invalid_entity_types)
        return s

    @property
    def all_invalid_relation_types(self) -> set[str]:
        s: set[str] = set()
        for r in self.results:
            s.update(r.invalid_relation_types)
        return s

    def summary_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "total_articles": self.total,
            "json_parse_rate": round(self.json_parse_rate, 3),
            "schema_pass_rate": round(self.schema_pass_rate, 3),
            "recovery_pass_rate": round(self.recovery_pass_rate, 3),
            "invalid_entity_types": sorted(self.all_invalid_entity_types),
            "invalid_relation_types": sorted(self.all_invalid_relation_types),
        }


# ---------------------------------------------------------------------------
# Core evaluation logic
# ---------------------------------------------------------------------------


def evaluate_response(
    response_data: dict[str, Any] | str,
    doc_id: str,
    model: str = "fixture",
) -> EvalResult:
    """Evaluate a single LLM response against the extraction schema.

    Args:
        response_data: Parsed JSON dict, or raw string (for markdown-wrapped tests)
        doc_id: Document ID for this extraction
        model: Model name for labeling

    Returns:
        EvalResult with detailed compliance metrics
    """
    result = EvalResult(doc_id=doc_id, model=model)

    # Step 1: JSON parseability
    if isinstance(response_data, str):
        # Raw string — try parse_extraction_response (handles markdown fences)
        try:
            data = parse_extraction_response(response_data, doc_id=doc_id)
            result.json_parseable = True
            result.schema_valid_after_recovery = True
            result.schema_valid = True
            _collect_field_stats(data, result)
            return result
        except ExtractionError as e:
            result.errors.append(f"parse_extraction_response failed: {e}")
            # Try raw JSON parse to separate parse vs validation failures
            try:
                import re
                json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response_data, re.DOTALL)
                raw = json_match.group(1).strip() if json_match else response_data.strip()
                data = json.loads(raw)
                result.json_parseable = True
            except (json.JSONDecodeError, AttributeError):
                result.json_parseable = False
                return result
    else:
        data = response_data
        result.json_parseable = True

    # Step 2: Direct schema validation
    try:
        validate_extraction(data)
        result.schema_valid = True
        result.schema_valid_after_recovery = True
    except (ValidationError, Exception) as e:
        result.errors.append(str(e))
        result.schema_valid = False

        # Step 3: Recovery — try parse_extraction_response which injects docId
        try:
            recovered = parse_extraction_response(json.dumps(data), doc_id=doc_id)
            result.schema_valid_after_recovery = True
        except ExtractionError as e2:
            result.schema_valid_after_recovery = False
            result.errors.append(f"Recovery also failed: {e2}")

    # Step 4: Collect field-level stats regardless of validation outcome
    _collect_field_stats(data, result)

    return result


def _collect_field_stats(data: dict[str, Any], result: EvalResult) -> None:
    """Populate field-level statistics on an EvalResult."""
    entities = data.get("entities", [])
    relations = data.get("relations", [])
    tech_terms = data.get("techTerms", [])

    result.entity_count = len(entities)
    result.relation_count = len(relations)
    result.tech_term_count = len(tech_terms)

    # Check entity types
    valid_types = set(ENTITY_TYPES)
    for entity in entities:
        etype = entity.get("type", "")
        if etype not in valid_types:
            result.invalid_entity_types.append(etype)

    # Check relation types, kinds, confidence, evidence
    valid_rels = set(RELATION_TYPES)
    valid_kinds = set(RELATION_KINDS)
    for rel in relations:
        rtype = rel.get("rel", "")
        if rtype not in valid_rels:
            result.invalid_relation_types.append(rtype)

        kind = rel.get("kind", "")
        if kind not in valid_kinds:
            result.invalid_relation_kinds.append(kind)

        confidence = rel.get("confidence")
        if isinstance(confidence, (int, float)) and (confidence < 0 or confidence > 1):
            result.confidence_out_of_range += 1

        if kind == "asserted":
            evidence = rel.get("evidence", [])
            if not evidence:
                result.asserted_without_evidence += 1
            for ev in evidence:
                snippet = ev.get("snippet", "")
                result.evidence_snippet_lengths.append(len(snippet))


def evaluate_model_responses(
    responses: dict[str, dict[str, Any] | str],
    model: str = "fixture",
) -> ModelEvalSummary:
    """Evaluate multiple responses from a single model.

    Args:
        responses: Mapping of doc_id -> response data (dict or raw string)
        model: Model name

    Returns:
        ModelEvalSummary with aggregated metrics
    """
    summary = ModelEvalSummary(model=model)
    for doc_id, response_data in responses.items():
        result = evaluate_response(response_data, doc_id=doc_id, model=model)
        summary.results.append(result)
    return summary


# ---------------------------------------------------------------------------
# LLM provider adapters (for live evaluation)
# ---------------------------------------------------------------------------


class LLMProvider:
    """Base class for LLM API providers."""

    name: str = "base"

    def extract(self, doc: dict[str, Any]) -> str:
        """Send extraction prompt to LLM and return raw response."""
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    """OpenAI API provider (GPT-4.1, GPT-4.1-mini)."""

    name = "openai"

    def __init__(self, model: str = "gpt-4.1-mini"):
        self.model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                pytest.skip("openai package not installed")
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                pytest.skip("OPENAI_API_KEY not set")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def extract(self, doc: dict[str, Any]) -> str:
        client = self._get_client()
        prompt = build_extraction_prompt(doc)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        return response.choices[0].message.content


class AnthropicProvider(LLMProvider):
    """Anthropic API provider (Claude Haiku, Sonnet)."""

    name = "anthropic"

    def __init__(self, model: str = "claude-haiku-4-5-20250901"):
        self.model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                pytest.skip("anthropic package not installed")
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                pytest.skip("ANTHROPIC_API_KEY not set")
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def extract(self, doc: dict[str, Any]) -> str:
        client = self._get_client()
        prompt = build_extraction_prompt(doc)
        response = client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""

    name = "gemini"

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import google.generativeai as genai
            except ImportError:
                pytest.skip("google-generativeai package not installed")
            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                pytest.skip("GOOGLE_API_KEY not set")
            genai.configure(api_key=api_key)
            self._client = genai.GenerativeModel(
                self.model,
                generation_config={"response_mime_type": "application/json"},
            )
        return self._client

    def extract(self, doc: dict[str, Any]) -> str:
        client = self._get_client()
        prompt = build_extraction_prompt(doc)
        response = client.generate_content(prompt)
        return response.text


PROVIDERS = {
    "openai": OpenAIProvider,
    "openai-4.1": lambda: OpenAIProvider(model="gpt-4.1"),
    "openai-mini": lambda: OpenAIProvider(model="gpt-4.1-mini"),
    "anthropic-haiku": lambda: AnthropicProvider(model="claude-haiku-4-5-20250901"),
    "anthropic-sonnet": lambda: AnthropicProvider(model="claude-sonnet-4-20250514"),
    "gemini-flash": lambda: GeminiProvider(model="gemini-2.5-flash"),
    "gemini-pro": lambda: GeminiProvider(model="gemini-2.5-pro"),
}


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_articles() -> list[dict[str, Any]]:
    return load_sample_articles()


@pytest.fixture
def sample_responses() -> dict[str, Any]:
    return load_sample_responses()


# ---------------------------------------------------------------------------
# Offline tests (validate the harness with fixture data)
# ---------------------------------------------------------------------------


class TestEvalHarnessOffline:
    """Tests that validate the evaluation harness itself using fixture data."""

    def test_good_response_passes(self, sample_responses):
        """A well-formed response should pass schema validation."""
        good = sample_responses["good_response"]
        result = evaluate_response(good, doc_id=good["docId"])

        assert result.json_parseable
        assert result.schema_valid
        assert result.passed
        assert len(result.errors) == 0
        assert result.entity_count > 0
        assert result.relation_count > 0
        assert len(result.invalid_entity_types) == 0
        assert len(result.invalid_relation_types) == 0
        assert result.asserted_without_evidence == 0

    def test_invalid_enum_detected(self, sample_responses):
        """Response with invalid entity/relation enums should fail."""
        bad = sample_responses["bad_response_invalid_enum"]
        result = evaluate_response(bad, doc_id=bad["docId"])

        assert result.json_parseable
        assert not result.schema_valid
        assert not result.passed
        assert len(result.invalid_entity_types) > 0
        assert "Algorithm" in result.invalid_entity_types
        assert "Company" in result.invalid_entity_types
        assert len(result.invalid_relation_types) > 0
        assert "INVENTED" in result.invalid_relation_types

    def test_missing_evidence_detected(self, sample_responses):
        """Asserted relation without evidence should fail."""
        bad = sample_responses["bad_response_missing_evidence"]
        result = evaluate_response(bad, doc_id=bad["docId"])

        assert result.json_parseable
        assert not result.schema_valid
        assert result.asserted_without_evidence > 0

    def test_missing_fields_detected(self, sample_responses):
        """Response missing required fields should fail."""
        bad = sample_responses["bad_response_missing_fields"]
        result = evaluate_response(bad, doc_id=bad["docId"])

        assert result.json_parseable
        assert not result.schema_valid
        assert not result.passed

    def test_confidence_out_of_range_detected(self, sample_responses):
        """Confidence > 1.0 should be flagged."""
        bad = sample_responses["bad_response_confidence_out_of_range"]
        result = evaluate_response(bad, doc_id=bad["docId"])

        assert result.json_parseable
        assert not result.schema_valid
        assert result.confidence_out_of_range > 0

    def test_markdown_wrapped_recovery(self, sample_responses):
        """JSON wrapped in markdown fences should be recoverable."""
        bad = sample_responses["bad_response_markdown_wrapped"]
        raw_string = bad["_raw"]
        result = evaluate_response(raw_string, doc_id="2026-01-15_arxiv_transformer_efficiency")

        assert result.json_parseable
        assert result.passed

    def test_evidence_snippet_lengths_collected(self, sample_responses):
        """Should collect evidence snippet lengths for analysis."""
        good = sample_responses["good_response"]
        result = evaluate_response(good, doc_id=good["docId"])

        assert len(result.evidence_snippet_lengths) > 0
        assert all(length > 0 for length in result.evidence_snippet_lengths)


class TestModelEvalSummary:
    """Tests for aggregated model evaluation."""

    def test_summary_with_mixed_results(self, sample_responses):
        """Summary should correctly aggregate pass/fail rates."""
        responses = {
            "doc1": sample_responses["good_response"],
            "doc2": sample_responses["bad_response_invalid_enum"],
        }
        summary = evaluate_model_responses(responses, model="test_model")

        assert summary.total == 2
        assert summary.json_parse_rate == 1.0
        assert summary.schema_pass_rate == 0.5
        assert len(summary.all_invalid_entity_types) > 0

    def test_summary_dict_format(self, sample_responses):
        """Summary dict should contain all required fields."""
        responses = {"doc1": sample_responses["good_response"]}
        summary = evaluate_model_responses(responses, model="test_model")
        d = summary.summary_dict()

        assert "model" in d
        assert "total_articles" in d
        assert "json_parse_rate" in d
        assert "schema_pass_rate" in d
        assert "recovery_pass_rate" in d
        assert "invalid_entity_types" in d
        assert "invalid_relation_types" in d


class TestPromptGeneration:
    """Verify prompts are well-formed for each sample article."""

    def test_all_articles_produce_prompts(self, sample_articles):
        """Every sample article should produce a non-empty prompt."""
        for article in sample_articles:
            prompt = build_extraction_prompt(article)
            assert len(prompt) > 100
            assert article["docId"] in prompt
            assert article["text"][:50] in prompt


class TestEvidenceGrounding:
    """Tests for evidence quality metrics."""

    def test_snippet_appears_in_source(self, sample_articles, sample_responses):
        """Evidence snippets from good response should appear in source text."""
        good = sample_responses["good_response"]
        doc_id = good["docId"]
        article = next(a for a in sample_articles if a["docId"] == doc_id)
        source_text = article["text"]

        for rel in good.get("relations", []):
            for evidence in rel.get("evidence", []):
                snippet = evidence.get("snippet", "")
                # Check that snippet is a substring or close match of source
                # Allow minor variations (LLMs may paraphrase slightly)
                assert len(snippet) <= 200, (
                    f"Snippet too long ({len(snippet)} chars): {snippet[:50]}..."
                )
                # At minimum, key words from snippet should appear in source
                words = [w for w in snippet.split() if len(w) > 4]
                matches = sum(1 for w in words if w in source_text)
                match_rate = matches / len(words) if words else 0
                assert match_rate > 0.5, (
                    f"Snippet doesn't match source text well enough "
                    f"({match_rate:.0%}): {snippet[:80]}..."
                )


# ---------------------------------------------------------------------------
# Live LLM evaluation tests (require API keys)
# ---------------------------------------------------------------------------


@pytest.mark.llm_live
class TestLiveLLMEvaluation:
    """Run extraction against real LLM APIs.

    Usage:
        # Single provider
        OPENAI_API_KEY=sk-... pytest tests/test_llm_eval.py::TestLiveLLMEvaluation -v -m llm_live -k openai

        # All providers with keys set
        pytest tests/test_llm_eval.py::TestLiveLLMEvaluation -v -m llm_live
    """

    @pytest.fixture
    def first_article(self, sample_articles) -> dict[str, Any]:
        """Use first article for quick single-doc tests."""
        return sample_articles[0]

    @pytest.mark.parametrize("provider_key", [
        "openai-mini",
        "anthropic-haiku",
        "gemini-flash",
    ])
    def test_single_article_schema_compliance(self, first_article, provider_key):
        """Test schema compliance with a single article."""
        provider_factory = PROVIDERS[provider_key]
        provider = provider_factory() if callable(provider_factory) else provider_factory

        raw_response = provider.extract(first_article)
        result = evaluate_response(
            raw_response,
            doc_id=first_article["docId"],
            model=provider_key,
        )

        print(f"\n--- {provider_key} ---")
        print(f"JSON parseable: {result.json_parseable}")
        print(f"Schema valid: {result.schema_valid}")
        print(f"Valid after recovery: {result.schema_valid_after_recovery}")
        print(f"Entities: {result.entity_count}")
        print(f"Relations: {result.relation_count}")
        print(f"Tech terms: {result.tech_term_count}")
        if result.invalid_entity_types:
            print(f"Invalid entity types: {result.invalid_entity_types}")
        if result.invalid_relation_types:
            print(f"Invalid relation types: {result.invalid_relation_types}")
        if result.errors:
            print(f"Errors: {result.errors}")

        # Minimum bar: JSON must parse
        assert result.json_parseable, f"{provider_key} failed to produce valid JSON"

    @pytest.mark.parametrize("provider_key", [
        "openai-mini",
        "anthropic-haiku",
        "gemini-flash",
    ])
    def test_full_article_set(self, sample_articles, provider_key):
        """Run all sample articles through a provider and report summary."""
        provider_factory = PROVIDERS[provider_key]
        provider = provider_factory() if callable(provider_factory) else provider_factory

        responses = {}
        for article in sample_articles:
            try:
                raw = provider.extract(article)
                responses[article["docId"]] = raw
            except Exception as e:
                responses[article["docId"]] = f'{{"error": "{e}"}}'

        summary = evaluate_model_responses(responses, model=provider_key)

        print(f"\n{'='*60}")
        print(f"MODEL: {provider_key}")
        print(f"{'='*60}")
        print(json.dumps(summary.summary_dict(), indent=2))
        for r in summary.results:
            status = "PASS" if r.passed else "FAIL"
            print(f"  [{status}] {r.doc_id}: entities={r.entity_count} "
                  f"relations={r.relation_count} errors={len(r.errors)}")
        print(f"{'='*60}")

        # Report but don't hard-fail — this is comparative evaluation
        assert summary.json_parse_rate > 0.5, (
            f"{provider_key} failed to parse JSON for >50% of articles"
        )
