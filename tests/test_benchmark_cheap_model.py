"""Tests for the benchmark_cheap_model script.

Tests the tallying and summary logic using mocked API responses.
No network calls required.
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts/ and src/ to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from benchmark_cheap_model import run_benchmark, print_summary


def _make_docpack(docs: list[dict], tmp_path: Path) -> Path:
    """Write docs as JSONL and return the path."""
    p = tmp_path / "test_bundle.jsonl"
    with open(p, "w") as f:
        for doc in docs:
            f.write(json.dumps(doc) + "\n")
    return p


def _good_extraction(doc_id: str) -> str:
    """Return a schema-valid extraction JSON that should pass all gates."""
    return json.dumps({
        "docId": doc_id,
        "extractorVersion": "1.0.0",
        "entities": [
            {"name": "OpenAI", "type": "Org"},
            {"name": "GPT-5", "type": "Model"},
            {"name": "Anthropic", "type": "Org"},
            {"name": "Claude", "type": "Model"},
            {"name": "Google", "type": "Org"},
            {"name": "Gemini", "type": "Model"},
        ],
        "relations": [
            {
                "source": "OpenAI", "rel": "CREATED", "target": "GPT-5",
                "kind": "asserted", "confidence": 0.95,
                "evidence": [{"snippet": "openai announced gpt-5", "docId": doc_id, "url": "https://example.com/1"}],
            },
            {
                "source": "Anthropic", "rel": "CREATED", "target": "Claude",
                "kind": "asserted", "confidence": 0.90,
                "evidence": [{"snippet": "anthropic released claude", "docId": doc_id, "url": "https://example.com/1"}],
            },
            {
                "source": "Google", "rel": "LAUNCHED", "target": "Gemini",
                "kind": "asserted", "confidence": 0.85,
                "evidence": [{"snippet": "google launched gemini", "docId": doc_id, "url": "https://example.com/1"}],
            },
            {
                "source": "GPT-5", "rel": "USES_TECH", "target": "Claude",
                "kind": "inferred", "confidence": 0.5,
            },
            {
                "source": "GPT-5", "rel": "INTEGRATES_WITH", "target": "Gemini",
                "kind": "inferred", "confidence": 0.6,
            },
            {
                "source": "Claude", "rel": "DEPENDS_ON", "target": "GPT-5",
                "kind": "inferred", "confidence": 0.4,
            },
            {
                "source": "OpenAI", "rel": "PARTNERED_WITH", "target": "Google",
                "kind": "inferred", "confidence": 0.3,
            },
        ],
        "techTerms": ["transformer", "RLHF", "multimodal"],
        "dates": [{"text": "2025", "start": "2025-01-01"}],
    })


def _weak_extraction(doc_id: str) -> str:
    """Return a schema-valid but low-quality extraction (should escalate on score)."""
    return json.dumps({
        "docId": doc_id,
        "extractorVersion": "1.0.0",
        "entities": [
            {"name": "SomeCo", "type": "Org"},
        ],
        "relations": [
            {
                "source": "SomeCo", "rel": "MENTIONS", "target": "SomeCo",
                "kind": "asserted", "confidence": 0.9,
                "evidence": [{"snippet": "someco was mentioned", "docId": doc_id, "url": "https://example.com/3"}],
            },
        ],
        "techTerms": [],
        "dates": [],
    })


SAMPLE_SOURCE_TEXT = (
    "OpenAI announced GPT-5 today. Anthropic released Claude. "
    "Google launched Gemini. SomeCo was mentioned in the article. "
    "This is a long enough article to pass the zero-value gate check. "
    "It contains information about transformer architectures and RLHF "
    "training methods as well as multimodal capabilities. "
) * 5  # repeat to get >500 chars


SAMPLE_DOCS = [
    {
        "docId": "doc_good_1",
        "title": "AI News",
        "text": SAMPLE_SOURCE_TEXT,
        "url": "https://example.com/1",
        "published": "2025-12-01",
    },
    {
        "docId": "doc_good_2",
        "title": "More AI News",
        "text": SAMPLE_SOURCE_TEXT,
        "url": "https://example.com/2",
        "published": "2025-12-02",
    },
    {
        "docId": "doc_weak_3",
        "title": "Weak Article",
        "text": SAMPLE_SOURCE_TEXT,
        "url": "https://example.com/3",
        "published": "2025-12-03",
    },
]


def _mock_extract_document(doc, model):
    """Mock that returns good extraction for first two docs, weak for third."""
    doc_id = doc.get("docId", "unknown")
    if "weak" in doc_id:
        return _weak_extraction(doc_id), 150
    return _good_extraction(doc_id), 200


def _mock_extract_always_fail(doc, model):
    """Mock that always raises an exception."""
    raise ConnectionError("API unavailable")


class TestRunBenchmark:
    """Test the run_benchmark function with mocked API calls."""

    @patch("benchmark_cheap_model.extract_document", side_effect=_mock_extract_document)
    def test_basic_tally(self, mock_extract, tmp_path):
        """Two good docs + one weak doc -> correct accept/escalate counts."""
        docpack = _make_docpack(SAMPLE_DOCS, tmp_path)

        summary = run_benchmark(
            docpack_path=docpack,
            model="gpt-5-nano",
            max_docs=None,
            output_path=None,
        )

        assert summary["total_docs"] == 3
        assert summary["api_failed"] == 0
        assert summary["parse_failed"] == 0
        assert summary["evaluated"] == 3
        # The two good docs should be accepted, the weak one escalated
        assert summary["accepted"] == 2
        assert summary["escalated"] == 1
        assert summary["escalation_rate_pct"] > 0

    @patch("benchmark_cheap_model.extract_document", side_effect=_mock_extract_document)
    def test_max_docs_limits(self, mock_extract, tmp_path):
        """--max-docs should limit processing."""
        docpack = _make_docpack(SAMPLE_DOCS, tmp_path)

        summary = run_benchmark(
            docpack_path=docpack,
            model="gpt-5-nano",
            max_docs=1,
        )

        assert summary["total_docs"] == 1
        assert summary["evaluated"] == 1

    @patch("benchmark_cheap_model.extract_document", side_effect=_mock_extract_always_fail)
    def test_api_failures_tallied(self, mock_extract, tmp_path):
        """API failures should be counted, not crash."""
        docpack = _make_docpack(SAMPLE_DOCS[:1], tmp_path)

        summary = run_benchmark(
            docpack_path=docpack,
            model="gpt-5-nano",
        )

        assert summary["total_docs"] == 1
        assert summary["api_failed"] == 1
        assert summary["evaluated"] == 0
        assert summary["escalation_rate_pct"] == 0

    @patch("benchmark_cheap_model.extract_document", side_effect=_mock_extract_document)
    def test_output_jsonl_written(self, mock_extract, tmp_path):
        """Per-doc JSONL output should be written when --output is specified."""
        docpack = _make_docpack(SAMPLE_DOCS, tmp_path)
        output_path = tmp_path / "results.jsonl"

        run_benchmark(
            docpack_path=docpack,
            model="gpt-5-nano",
            output_path=output_path,
        )

        assert output_path.exists()
        lines = output_path.read_text().strip().split("\n")
        assert len(lines) == 3

        for line in lines:
            record = json.loads(line)
            assert "docId" in record
            assert "outcome" in record
            assert record["outcome"] in ("accept", "escalate", "api_failed", "parse_failed")

    @patch("benchmark_cheap_model.extract_document", side_effect=_mock_extract_document)
    def test_score_stats_populated(self, mock_extract, tmp_path):
        """Summary should include score statistics."""
        docpack = _make_docpack(SAMPLE_DOCS, tmp_path)

        summary = run_benchmark(
            docpack_path=docpack,
            model="gpt-5-nano",
        )

        assert "score_stats" in summary
        stats = summary["score_stats"]
        assert "mean" in stats
        assert "median" in stats
        assert stats["mean"] > 0
        assert stats["min"] <= stats["mean"] <= stats["max"]

    @patch("benchmark_cheap_model.extract_document", side_effect=_mock_extract_document)
    def test_sub_score_means_populated(self, mock_extract, tmp_path):
        """Summary should include per-dimension sub-score means."""
        docpack = _make_docpack(SAMPLE_DOCS, tmp_path)

        summary = run_benchmark(
            docpack_path=docpack,
            model="gpt-5-nano",
        )

        assert "sub_score_means" in summary
        means = summary["sub_score_means"]
        for key in ("density", "evidence", "confidence", "connectivity", "diversity", "tech"):
            assert key in means, f"Missing sub-score: {key}"
            assert 0 <= means[key] <= 1.0

    @patch("benchmark_cheap_model.extract_document", side_effect=_mock_extract_document)
    def test_gate_failure_breakdown(self, mock_extract, tmp_path):
        """Escalated docs should have gate failure details."""
        docpack = _make_docpack(SAMPLE_DOCS, tmp_path)

        summary = run_benchmark(
            docpack_path=docpack,
            model="gpt-5-nano",
        )

        # The weak doc should trigger either gate or score failure
        assert summary["escalated"] >= 1
        # At least one of these should be non-zero
        assert (summary["gate_fail_escalations"] + summary["score_fail_escalations"]) >= 1


class TestParseFailed:
    """Test that parse failures are tallied correctly."""

    @patch("benchmark_cheap_model.extract_document", return_value=("not valid json {{{", 100))
    def test_parse_failure_counted(self, mock_extract, tmp_path):
        """Invalid JSON from model should count as parse failure."""
        docpack = _make_docpack(SAMPLE_DOCS[:1], tmp_path)

        summary = run_benchmark(
            docpack_path=docpack,
            model="gpt-5-nano",
        )

        assert summary["parse_failed"] == 1
        assert summary["evaluated"] == 0


class TestPrintSummary:
    """Test that print_summary doesn't crash on various inputs."""

    def test_print_empty_summary(self, capsys):
        """Should handle zero-doc summary without errors."""
        summary = {
            "model": "test-model",
            "total_docs": 0,
            "api_failed": 0,
            "parse_failed": 0,
            "evaluated": 0,
            "accepted": 0,
            "escalated": 0,
            "escalation_rate_pct": 0,
            "gate_fail_escalations": 0,
            "score_fail_escalations": 0,
            "gate_fail_rate_pct": 0,
            "score_fail_rate_pct": 0,
            "gate_failure_breakdown": {},
            "score_stats": {},
            "duration_stats": {},
            "fidelity_stats": {},
            "sub_score_means": {},
        }
        print_summary(summary)
        captured = capsys.readouterr()
        assert "BENCHMARK RESULTS" in captured.out
        assert "test-model" in captured.out

    def test_print_full_summary(self, capsys):
        """Should render all sections when data is present."""
        summary = {
            "model": "gpt-5-nano",
            "total_docs": 10,
            "api_failed": 1,
            "parse_failed": 1,
            "evaluated": 8,
            "accepted": 5,
            "escalated": 3,
            "escalation_rate_pct": 37.5,
            "gate_fail_escalations": 2,
            "score_fail_escalations": 1,
            "gate_fail_rate_pct": 25.0,
            "score_fail_rate_pct": 12.5,
            "gate_failure_breakdown": {"orphan_endpoints": 2},
            "score_stats": {"mean": 0.65, "median": 0.68, "stdev": 0.12, "min": 0.3, "max": 0.9},
            "duration_stats": {"mean_ms": 200, "median_ms": 180, "p95_ms": 350},
            "fidelity_stats": {"mean": 0.85, "below_70pct": 1},
            "sub_score_means": {
                "density": 0.8, "evidence": 0.9, "confidence": 0.7,
                "connectivity": 0.5, "diversity": 0.4, "tech": 0.85,
            },
        }
        print_summary(summary)
        captured = capsys.readouterr()
        assert "37.5%" in captured.out
        assert "orphan_endpoints" in captured.out
