"""Tests for extraction quality gates (Phase 1) and evaluation flow.

Tests cover:
- Gate A: Evidence fidelity (snippet-in-text)
- Gate B: Orphan endpoint detection
- Gate C: Zero-value pattern detection
- Gate D: High-confidence + bad evidence
- Integrated evaluation: gates-first-then-score flow
- DB instrumentation: quality_runs and quality_metrics tables
"""

import json
import pytest

from extract import (
    check_evidence_fidelity,
    check_orphan_endpoints,
    check_zero_value,
    check_high_confidence_bad_evidence,
    run_quality_gates,
    evaluate_extraction,
    GATE_THRESHOLDS,
)
from db import (
    init_db,
    insert_quality_run,
    insert_quality_metric,
    insert_quality_evaluation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SOURCE_TEXT = (
    "OpenAI announced GPT-5 today at their annual developer conference. "
    "The new model uses a transformer architecture and was trained on "
    "a massive dataset. Anthropic's Claude competes in the same space. "
    "Google DeepMind also released Gemini 2.0 last week. "
    "The model achieves state-of-the-art results on MMLU and HumanEval benchmarks."
)


def _make_extraction(
    entities=None,
    relations=None,
    tech_terms=None,
):
    """Build a minimal valid extraction dict for testing."""
    return {
        "docId": "test_doc_001",
        "extractorVersion": "1.0.0",
        "entities": entities or [],
        "relations": relations or [],
        "techTerms": tech_terms or [],
        "dates": [],
        "notes": [],
    }


def _make_relation(
    source="OpenAI",
    rel="CREATED",
    target="GPT-5",
    kind="asserted",
    confidence=0.9,
    snippet="OpenAI announced GPT-5 today",
):
    """Build a relation dict with evidence."""
    evidence = []
    if snippet and kind == "asserted":
        evidence = [{
            "docId": "test_doc_001",
            "url": "https://example.com",
            "published": "2026-02-23",
            "snippet": snippet,
        }]
    return {
        "source": source,
        "rel": rel,
        "target": target,
        "kind": kind,
        "confidence": confidence,
        "verbRaw": "announced",
        "evidence": evidence,
    }


# ---------------------------------------------------------------------------
# Gate A: Evidence Fidelity
# ---------------------------------------------------------------------------


class TestEvidenceFidelity:
    """Gate A — snippet-in-text verification."""

    def test_all_snippets_found(self):
        """All evidence snippets exist in source text → pass."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(snippet="OpenAI announced GPT-5 today"),
            ],
        )
        result = check_evidence_fidelity(extraction, SOURCE_TEXT)
        assert result["passed"] is True
        assert result["match_rate"] == 1.0
        assert result["failed_snippets"] == []

    def test_fabricated_snippet_fails(self):
        """Evidence snippet NOT in source text → fail."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(snippet="OpenAI secretly developed GPT-5 in a bunker"),
            ],
        )
        result = check_evidence_fidelity(extraction, SOURCE_TEXT)
        assert result["passed"] is False
        assert result["match_rate"] == 0.0
        assert len(result["failed_snippets"]) == 1

    def test_whitespace_normalization(self):
        """Snippet with different whitespace should still match."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(snippet="OpenAI  announced   GPT-5  today"),
            ],
        )
        result = check_evidence_fidelity(extraction, SOURCE_TEXT)
        assert result["passed"] is True

    def test_case_insensitive(self):
        """Snippet matching should be case-insensitive."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(snippet="openai announced gpt-5 today"),
            ],
        )
        result = check_evidence_fidelity(extraction, SOURCE_TEXT)
        assert result["passed"] is True

    def test_partial_match_above_threshold(self):
        """3 of 4 snippets found = 75% > 70% threshold → pass."""
        relations = [
            _make_relation(source="OpenAI", target="GPT-5",
                           snippet="OpenAI announced GPT-5 today"),
            _make_relation(source="GPT-5", target="MMLU", rel="EVALUATED_ON",
                           snippet="state-of-the-art results on MMLU"),
            _make_relation(source="Google DeepMind", target="Gemini 2.0", rel="LAUNCHED",
                           snippet="Google DeepMind also released Gemini 2.0"),
            _make_relation(source="OpenAI", target="Meta", rel="PARTNERED_WITH",
                           snippet="This snippet is completely fabricated"),
        ]
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
                {"name": "MMLU", "type": "Benchmark"},
                {"name": "Google DeepMind", "type": "Org"},
                {"name": "Gemini 2.0", "type": "Model"},
                {"name": "Meta", "type": "Org"},
            ],
            relations=relations,
        )
        result = check_evidence_fidelity(extraction, SOURCE_TEXT)
        assert result["passed"] is True
        assert result["match_rate"] == 0.75

    def test_below_threshold_fails(self):
        """1 of 3 snippets found = 33% < 70% threshold → fail."""
        relations = [
            _make_relation(snippet="OpenAI announced GPT-5 today"),
            _make_relation(source="OpenAI", target="Meta",
                           snippet="Fabricated snippet one"),
            _make_relation(source="OpenAI", target="Apple",
                           snippet="Fabricated snippet two"),
        ]
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
                {"name": "Meta", "type": "Org"},
                {"name": "Apple", "type": "Org"},
            ],
            relations=relations,
        )
        result = check_evidence_fidelity(extraction, SOURCE_TEXT)
        assert result["passed"] is False
        assert len(result["failed_snippets"]) == 2

    def test_no_asserted_relations_passes(self):
        """Extraction with only inferred relations → pass (nothing to check)."""
        extraction = _make_extraction(
            entities=[{"name": "OpenAI", "type": "Org"}],
            relations=[
                _make_relation(kind="inferred", snippet=""),
            ],
        )
        result = check_evidence_fidelity(extraction, SOURCE_TEXT)
        assert result["passed"] is True
        assert result["checked"] == 0

    def test_empty_extraction_passes(self):
        """Empty extraction → pass."""
        extraction = _make_extraction()
        result = check_evidence_fidelity(extraction, SOURCE_TEXT)
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Gate B: Orphan Endpoints
# ---------------------------------------------------------------------------


class TestOrphanEndpoints:
    """Gate B — every relation endpoint must map to an entity."""

    def test_all_endpoints_resolved(self):
        """All relation endpoints match entities → pass."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(source="OpenAI", target="GPT-5"),
            ],
        )
        result = check_orphan_endpoints(extraction)
        assert result["passed"] is True
        assert result["orphan_rate"] == 0.0

    def test_orphan_source(self):
        """Relation source not in entities → fail."""
        extraction = _make_extraction(
            entities=[
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(source="OpenAI", target="GPT-5"),
            ],
        )
        result = check_orphan_endpoints(extraction)
        assert result["passed"] is False
        assert result["orphan_count"] == 1
        assert result["orphans"][0]["endpoint"] == "source"
        assert result["orphans"][0]["name"] == "OpenAI"

    def test_orphan_target(self):
        """Relation target not in entities → fail."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
            ],
            relations=[
                _make_relation(source="OpenAI", target="GPT-5"),
            ],
        )
        result = check_orphan_endpoints(extraction)
        assert result["passed"] is False
        assert result["orphan_count"] == 1
        assert result["orphans"][0]["endpoint"] == "target"

    def test_case_insensitive_match(self):
        """Entity matching should be case-insensitive."""
        extraction = _make_extraction(
            entities=[
                {"name": "openai", "type": "Org"},
                {"name": "gpt-5", "type": "Model"},
            ],
            relations=[
                _make_relation(source="OpenAI", target="GPT-5"),
            ],
        )
        result = check_orphan_endpoints(extraction)
        assert result["passed"] is True

    def test_no_relations_passes(self):
        """No relations → pass."""
        extraction = _make_extraction(
            entities=[{"name": "OpenAI", "type": "Org"}],
        )
        result = check_orphan_endpoints(extraction)
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Gate C: Zero-Value Patterns
# ---------------------------------------------------------------------------


class TestZeroValue:
    """Gate C — detect schema-valid but empty/useless output."""

    def test_normal_extraction_passes(self):
        """Non-empty extraction for non-trivial doc → pass."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(),
            ],
        )
        result = check_zero_value(extraction, source_text_length=2000)
        assert result["passed"] is True

    def test_zero_entities_fails(self):
        """Zero entities for a long doc → fail."""
        extraction = _make_extraction(entities=[], relations=[])
        result = check_zero_value(extraction, source_text_length=2000)
        assert result["passed"] is False
        assert "zero_entities" in result["reason"]

    def test_entities_but_no_relations_fails(self):
        """Many entities but zero relations → fail."""
        extraction = _make_extraction(
            entities=[
                {"name": f"Entity{i}", "type": "Org"} for i in range(5)
            ],
            relations=[],
        )
        result = check_zero_value(extraction, source_text_length=2000)
        assert result["passed"] is False
        assert "no_relations" in result["reason"]

    def test_short_doc_skips_gate(self):
        """Very short doc → skip gate (too short to expect entities)."""
        extraction = _make_extraction(entities=[], relations=[])
        result = check_zero_value(extraction, source_text_length=100)
        assert result["passed"] is True
        assert "too_short" in result["reason"]

    def test_few_entities_no_relations_passes(self):
        """3 or fewer entities with 0 relations → pass (small doc, maybe OK)."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[],
        )
        result = check_zero_value(extraction, source_text_length=2000)
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Gate D: High-Confidence + Bad Evidence
# ---------------------------------------------------------------------------


class TestHighConfidenceBadEvidence:
    """Gate D — worst failure mode: confident assertion with fake evidence."""

    def test_high_conf_real_evidence_passes(self):
        """High confidence + real snippet → pass."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(confidence=0.95, snippet="OpenAI announced GPT-5 today"),
            ],
        )
        result = check_high_confidence_bad_evidence(extraction, SOURCE_TEXT)
        assert result["passed"] is True
        assert result["flagged_count"] == 0

    def test_high_conf_fake_evidence_fails(self):
        """High confidence + fabricated snippet → fail."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(
                    confidence=0.95,
                    snippet="OpenAI secretly built GPT-5 underground",
                ),
            ],
        )
        result = check_high_confidence_bad_evidence(extraction, SOURCE_TEXT)
        assert result["passed"] is False
        assert result["flagged_count"] == 1
        assert result["flagged_relations"][0]["confidence"] == 0.95

    def test_low_conf_fake_evidence_passes(self):
        """Low confidence + fabricated snippet → pass (not flagged by this gate)."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(
                    confidence=0.5,
                    snippet="This snippet is completely made up",
                ),
            ],
        )
        result = check_high_confidence_bad_evidence(extraction, SOURCE_TEXT)
        assert result["passed"] is True

    def test_inferred_skipped(self):
        """Inferred relations are not checked (no evidence expected)."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(kind="inferred", confidence=0.95, snippet=""),
            ],
        )
        result = check_high_confidence_bad_evidence(extraction, SOURCE_TEXT)
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Integrated: run_quality_gates
# ---------------------------------------------------------------------------


class TestRunQualityGates:
    """Test the combined gate runner."""

    def test_all_gates_pass(self):
        """Clean extraction passes all gates."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(snippet="OpenAI announced GPT-5 today"),
            ],
        )
        result = run_quality_gates(extraction, SOURCE_TEXT)
        assert result["overall_passed"] is True
        assert result["escalation_reasons"] == []

    def test_evidence_gate_triggers_escalation(self):
        """Bad evidence → overall fail + escalation reason."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(snippet="Completely fabricated evidence snippet"),
            ],
        )
        result = run_quality_gates(extraction, SOURCE_TEXT)
        assert result["overall_passed"] is False
        assert any("evidence_fidelity" in r for r in result["escalation_reasons"])

    def test_orphan_gate_triggers_escalation(self):
        """Orphan endpoint → overall fail."""
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                # GPT-5 entity is missing!
            ],
            relations=[
                _make_relation(
                    source="OpenAI", target="GPT-5",
                    snippet="OpenAI announced GPT-5 today",
                ),
            ],
        )
        result = run_quality_gates(extraction, SOURCE_TEXT)
        assert result["overall_passed"] is False
        assert any("orphan" in r for r in result["escalation_reasons"])

    def test_multiple_gate_failures(self):
        """Multiple gates can fail simultaneously."""
        extraction = _make_extraction(
            entities=[],  # zero entities + orphan endpoints
            relations=[
                _make_relation(snippet="Fabricated snippet here"),
            ],
        )
        result = run_quality_gates(extraction, SOURCE_TEXT)
        assert result["overall_passed"] is False
        assert len(result["escalation_reasons"]) >= 2


# ---------------------------------------------------------------------------
# Integrated: evaluate_extraction (gates + scoring)
# ---------------------------------------------------------------------------


class TestEvaluateExtraction:
    """Test the unified evaluation entry point."""

    def test_good_extraction_accepted(self):
        """High-quality extraction with real evidence → accept."""
        # Build a rich extraction that will score well
        entities = [
            {"name": "OpenAI", "type": "Org"},
            {"name": "GPT-5", "type": "Model"},
            {"name": "Anthropic", "type": "Org"},
            {"name": "Claude", "type": "Model"},
            {"name": "Google DeepMind", "type": "Org"},
            {"name": "Gemini 2.0", "type": "Model"},
            {"name": "MMLU", "type": "Benchmark"},
            {"name": "HumanEval", "type": "Benchmark"},
        ]
        relations = [
            _make_relation(source="OpenAI", rel="LAUNCHED", target="GPT-5",
                           confidence=0.95, snippet="OpenAI announced GPT-5 today"),
            _make_relation(source="GPT-5", rel="USES_TECH", target="Claude",
                           kind="inferred", confidence=0.4, snippet=""),
            _make_relation(source="GPT-5", rel="EVALUATED_ON", target="MMLU",
                           confidence=0.90, snippet="state-of-the-art results on MMLU"),
            _make_relation(source="GPT-5", rel="EVALUATED_ON", target="HumanEval",
                           confidence=0.88, snippet="results on MMLU and HumanEval benchmarks"),
            _make_relation(source="Google DeepMind", rel="CREATED", target="Gemini 2.0",
                           confidence=0.92, snippet="Google DeepMind also released Gemini 2.0"),
            _make_relation(source="Anthropic", rel="CREATED", target="Claude",
                           confidence=0.70, snippet="Anthropic's Claude competes"),
            _make_relation(source="GPT-5", rel="TRAINED_ON", target="MMLU",
                           kind="hypothesis", confidence=0.3, snippet=""),
        ]
        extraction = _make_extraction(
            entities=entities,
            relations=relations,
            tech_terms=["transformer", "language model", "benchmark"],
        )
        result = evaluate_extraction(extraction, SOURCE_TEXT)
        assert result["escalate"] is False
        assert result["decision"] == "accept"
        assert result["gates"]["overall_passed"] is True

    def test_gate_failure_overrides_score(self):
        """Even if the scoring would pass, a gate failure forces escalation."""
        # Build extraction that has decent stats but fabricated evidence
        entities = [
            {"name": "OpenAI", "type": "Org"},
            {"name": "GPT-5", "type": "Model"},
            {"name": "Anthropic", "type": "Org"},
            {"name": "Claude", "type": "Model"},
            {"name": "Google DeepMind", "type": "Org"},
            {"name": "Gemini 2.0", "type": "Model"},
        ]
        relations = [
            _make_relation(source="OpenAI", rel="LAUNCHED", target="GPT-5",
                           confidence=0.9, snippet="Fabricated snippet number one"),
            _make_relation(source="Anthropic", rel="CREATED", target="Claude",
                           confidence=0.9, snippet="Another fabricated snippet here"),
            _make_relation(source="Google DeepMind", rel="CREATED", target="Gemini 2.0",
                           confidence=0.9, snippet="Third fabricated snippet goes here"),
        ]
        extraction = _make_extraction(
            entities=entities,
            relations=relations,
            tech_terms=["transformer", "attention"],
        )
        result = evaluate_extraction(extraction, SOURCE_TEXT)
        assert result["escalate"] is True
        assert result["decision"] == "escalate"
        assert "gate_failed" in result["decision_reason"]

    def test_gates_pass_but_score_low(self):
        """Gates pass but quality score is below threshold → escalate."""
        # Minimal extraction: real evidence but very sparse
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(source="OpenAI", rel="CREATED", target="GPT-5",
                               confidence=0.9, snippet="OpenAI announced GPT-5 today"),
            ],
            tech_terms=[],  # no tech terms → low score
        )
        result = evaluate_extraction(extraction, SOURCE_TEXT)
        # This may or may not escalate depending on score, but gates should pass
        assert result["gates"]["overall_passed"] is True
        # The score for this sparse extraction should be low
        assert result["quality"]["combined_score"] < 0.8


# ---------------------------------------------------------------------------
# DB: Quality tables instrumentation
# ---------------------------------------------------------------------------


class TestQualityDB:
    """Test quality_runs and quality_metrics table operations."""

    @pytest.fixture
    def db_conn(self, tmp_path):
        db_path = tmp_path / "test.sqlite"
        conn = init_db(db_path)
        yield conn
        conn.close()

    def test_insert_quality_run(self, db_conn):
        """Should insert and retrieve a quality run."""
        insert_quality_run(
            db_conn,
            run_id="run-001",
            doc_id="test_doc",
            pipeline_stage="cheap_extract",
            model="gpt-5-nano",
            started_at="2026-02-23T00:00:00Z",
            status="ok",
            decision="accept",
            provider="openai",
            duration_ms=1500,
            quality_score=0.73,
            input_chars=5000,
        )
        row = db_conn.execute(
            "SELECT * FROM quality_runs WHERE run_id = ?", ("run-001",)
        ).fetchone()
        assert row is not None
        assert row["doc_id"] == "test_doc"
        assert row["decision"] == "accept"
        assert row["quality_score"] == 0.73

    def test_insert_quality_metric(self, db_conn):
        """Should insert and retrieve a quality metric."""
        insert_quality_run(
            db_conn, "run-002", "doc2", "cheap_extract", "gpt-5-nano",
            "2026-02-23T00:00:00Z", "ok", "escalate",
        )
        insert_quality_metric(
            db_conn,
            run_id="run-002",
            metric_name="evidence_fidelity_rate",
            metric_value=0.50,
            passed=False,
            severity=2,
            threshold_value=0.70,
            notes='[{"snippet": "fake one"}]',
        )
        row = db_conn.execute(
            "SELECT * FROM quality_metrics WHERE run_id = ? AND metric_name = ?",
            ("run-002", "evidence_fidelity_rate"),
        ).fetchone()
        assert row is not None
        assert row["metric_value"] == 0.50
        assert row["passed"] == 0  # False → 0
        assert row["severity"] == 2

    def test_insert_quality_evaluation_full(self, db_conn):
        """Should insert a full evaluation (run + all metrics)."""
        # Create a realistic evaluation result
        extraction = _make_extraction(
            entities=[
                {"name": "OpenAI", "type": "Org"},
                {"name": "GPT-5", "type": "Model"},
            ],
            relations=[
                _make_relation(snippet="OpenAI announced GPT-5 today"),
            ],
            tech_terms=["transformer"],
        )
        evaluation = evaluate_extraction(extraction, SOURCE_TEXT)

        insert_quality_evaluation(
            db_conn,
            run_id="run-003",
            doc_id="test_doc_001",
            pipeline_stage="cheap_extract",
            model="gpt-5-nano",
            started_at="2026-02-23T00:00:00Z",
            duration_ms=2000,
            evaluation=evaluation,
            input_chars=len(SOURCE_TEXT),
            provider="openai",
        )

        # Verify run was inserted
        run = db_conn.execute(
            "SELECT * FROM quality_runs WHERE run_id = ?", ("run-003",)
        ).fetchone()
        assert run is not None
        assert run["doc_id"] == "test_doc_001"

        # Verify gate metrics were inserted
        metrics = db_conn.execute(
            "SELECT metric_name, passed, severity FROM quality_metrics WHERE run_id = ?",
            ("run-003",),
        ).fetchall()
        metric_names = {m["metric_name"] for m in metrics}
        # Should have gate metrics
        assert "evidence_fidelity_rate" in metric_names
        assert "orphan_rate" in metric_names
        assert "zero_value" in metric_names
        assert "high_conf_bad_evidence" in metric_names
        # Should have scoring signal metrics
        assert "density_score" in metric_names
        assert "diversity_score" in metric_names

    def test_quality_metrics_aggregation(self, db_conn):
        """Should support SQL aggregation across runs."""
        # Insert two runs with different evidence fidelity rates
        for run_id, fidelity in [("r1", 0.90), ("r2", 0.60)]:
            insert_quality_run(
                db_conn, run_id, f"doc_{run_id}", "cheap_extract",
                "gpt-5-nano", "2026-02-23T00:00:00Z", "ok", "accept",
            )
            insert_quality_metric(
                db_conn, run_id, "evidence_fidelity_rate",
                metric_value=fidelity, passed=fidelity >= 0.70, severity=2,
            )

        avg = db_conn.execute(
            "SELECT AVG(metric_value) as avg_val FROM quality_metrics "
            "WHERE metric_name = 'evidence_fidelity_rate'"
        ).fetchone()
        assert abs(avg["avg_val"] - 0.75) < 0.01

        fail_count = db_conn.execute(
            "SELECT COUNT(*) as cnt FROM quality_metrics "
            "WHERE metric_name = 'evidence_fidelity_rate' AND passed = 0"
        ).fetchone()
        assert fail_count["cnt"] == 1
