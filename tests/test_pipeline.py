"""Tests for the pipeline orchestrator (scripts/run_pipeline.py).

Tests output parsing, log generation, and dry-run mode.
Does NOT test actual pipeline execution (that requires network + API keys).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts/ to path so we can import run_pipeline
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_pipeline import (
    parse_ingest_output,
    parse_docpack_output,
    parse_extract_output,
    parse_import_output,
    parse_export_output,
    parse_trending_output,
    copy_graphs_to_live,
    run_stage,
    utc_now,
)


class TestUtcNow:
    def test_returns_iso_format(self):
        result = utc_now()
        assert result.endswith("Z")
        assert "T" in result
        assert len(result) == 20  # YYYY-MM-DDTHH:MM:SSZ


class TestParseIngestOutput:
    def test_empty_output(self):
        stats = parse_ingest_output("")
        assert stats["feedsChecked"] == 0
        assert stats["newDocsFound"] == 0

    def test_typical_output(self):
        output = """Processing feed: arXiv CS.AI
    Feed OK: 8 new documents, 12 duplicates skipped
Processing feed: Hugging Face Blog
    Feed OK: 3 new documents, 0 duplicates skipped
Processing feed: OpenAI Blog
    Feed OK: 1 new documents, 0 duplicates skipped
Fetched 12 items, skipped 12, errors 0. Feeds reachable: 3/3.
"""
        stats = parse_ingest_output(output)
        assert stats["feedsChecked"] == 3
        assert stats["feedsReachable"] == 3
        assert stats["newDocsFound"] == 12
        assert stats["duplicatesSkipped"] == 12

    def test_fetch_errors(self):
        output = """Processing feed: arXiv CS.AI
    Feed OK: 20 new documents, 0 duplicates skipped
Processing feed: Broken Feed
    Feed errors: 3 fetch errors, 2 saved, 0 duplicates skipped
"""
        stats = parse_ingest_output(output)
        assert stats["feedsChecked"] == 2
        assert stats["feedsReachable"] == 2  # both reachable; one had article errors
        assert stats["fetchErrors"] == 3
        assert stats["newDocsFound"] == 22  # 20 + 2

    def test_unreachable_feeds(self):
        output = """Processing feed: arXiv CS.AI
    Feed OK: 5 new documents, 0 duplicates skipped
Processing feed: Dead Feed
    Feed UNREACHABLE: Dead Feed
Processing feed: Another Dead
    Feed UNREACHABLE: Another Dead
Fetched 5 items, skipped 0, errors 0. Feeds reachable: 1/3.
"""
        stats = parse_ingest_output(output)
        assert stats["feedsChecked"] == 3
        assert stats["feedsReachable"] == 1
        assert stats["feedsUnreachable"] == 2
        assert stats["newDocsFound"] == 5

    def test_crashed_feeds(self):
        output = """Processing feed: arXiv CS.AI
    Feed OK: 5 new documents, 0 duplicates skipped
Processing feed: Buggy Feed
    Feed CRASHED: Buggy Feed
Processing feed: OpenAI Blog
    Feed OK: 2 new documents, 0 duplicates skipped
"""
        stats = parse_ingest_output(output)
        assert stats["feedsChecked"] == 3
        assert stats["feedsReachable"] == 2
        assert stats["feedsUnreachable"] == 1
        assert stats["fetchErrors"] == 1
        assert stats["newDocsFound"] == 7

    def test_summary_line_no_false_positive(self):
        """Summary line must not trigger the generic error detector."""
        output = """Ingesting 3 feed(s)...
  Processing feed: arXiv CS.AI (limit 50)
    Feed OK: 0 new documents, 25 duplicates skipped
  Processing feed: Hugging Face Blog (limit 15)
    Feed OK: 0 new documents, 10 duplicates skipped
  Processing feed: OpenAI Blog (limit 15)
    Feed OK: 0 new documents, 8 duplicates skipped
Fetched 0 items, skipped 43, errors 0. Feeds reachable: 3/3.
"""
        stats = parse_ingest_output(output)
        assert stats["feedsChecked"] == 3
        assert stats["feedsReachable"] == 3
        assert stats["fetchErrors"] == 0  # Was 1 before fix (false positive)
        assert stats["newDocsFound"] == 0
        assert stats["duplicatesSkipped"] == 43

    def test_skip_existing_all_skipped(self):
        """When --skip-existing skips everything, stats should still be correct."""
        output = """Ingesting 13 feed(s)...
  Processing feed: arXiv CS.AI (limit 50)
    Feed OK: 0 new documents, 25 duplicates skipped
  Processing feed: Hugging Face Blog (limit 15)
    Feed OK: 0 new documents, 10 duplicates skipped
  Processing feed: OpenAI Blog (limit 15)
    Feed OK: 0 new documents, 8 duplicates skipped
  Processing feed: Google DeepMind Blog (limit 15)
    Feed OK: 0 new documents, 12 duplicates skipped
  Processing feed: NIST AI (limit 10)
    Feed OK: 0 new documents, 5 duplicates skipped
  Processing feed: Nextgov AI (limit 10)
    Feed OK: 0 new documents, 7 duplicates skipped
  Processing feed: Ars Technica AI (limit 15)
    Feed OK: 0 new documents, 10 duplicates skipped
  Processing feed: VentureBeat AI (limit 10)
    Feed OK: 0 new documents, 6 duplicates skipped
  Processing feed: MIT Tech Review AI (limit 10)
    Feed OK: 0 new documents, 8 duplicates skipped
  Processing feed: The Verge AI (limit 10)
    Feed OK: 0 new documents, 4 duplicates skipped
  Processing feed: TechCrunch AI (limit 10)
    Feed OK: 0 new documents, 7 duplicates skipped
  Processing feed: Wired AI (limit 10)
    Feed OK: 0 new documents, 3 duplicates skipped
  Processing feed: Anthropic Research Blog (limit 15)
    Feed UNREACHABLE: Anthropic Research Blog
Fetched 0 items, skipped 105, errors 0. Feeds reachable: 12/13.
"""
        stats = parse_ingest_output(output)
        assert stats["feedsChecked"] == 13
        assert stats["feedsReachable"] == 12
        assert stats["feedsUnreachable"] == 1
        assert stats["fetchErrors"] == 0
        assert stats["newDocsFound"] == 0
        assert stats["duplicatesSkipped"] == 105
        assert "erroredFeeds" in stats
        assert len(stats["erroredFeeds"]) == 1
        assert "Anthropic" in stats["erroredFeeds"][0]

    def test_numbered_prefix_format(self):
        """New format with [N/M] prefix should be parsed correctly."""
        output = """Ingesting 3 feed(s)...
  [1/3] Processing feed: arXiv CS.AI (limit 50)  (elapsed 0s)
    Feed OK: 8 new documents, 12 duplicates skipped
  [2/3] Processing feed: Hugging Face Blog (limit 15)  (elapsed 45s)
    Feed OK: 3 new documents, 0 duplicates skipped
  [3/3] Processing feed: OpenAI Blog (limit 15)  (elapsed 90s)
    Feed UNREACHABLE: OpenAI Blog
Fetched 11 items, skipped 12, errors 0. Feeds reachable: 2/3.
"""
        stats = parse_ingest_output(output)
        assert stats["feedsChecked"] == 3
        assert stats["feedsReachable"] == 2
        assert stats["feedsUnreachable"] == 1
        assert stats["newDocsFound"] == 11
        assert stats["duplicatesSkipped"] == 12

    def test_errored_feeds_collected(self):
        """Errored feed names should be collected in erroredFeeds list."""
        output = """Processing feed: arXiv CS.AI
    Feed OK: 5 new documents, 0 duplicates skipped
Processing feed: Dead Feed
    Feed UNREACHABLE: Dead Feed
Processing feed: Buggy Feed
    Feed CRASHED: Buggy Feed
Processing feed: Flaky Feed
    Feed errors: 2 fetch errors, 1 saved, 0 duplicates skipped
"""
        stats = parse_ingest_output(output)
        assert stats["feedsChecked"] == 4
        assert stats["feedsReachable"] == 2  # OK + errors
        assert stats["feedsUnreachable"] == 2  # unreachable + crashed
        errored = stats["erroredFeeds"]
        assert len(errored) == 3
        assert any("Dead Feed" in e for e in errored)
        assert any("Buggy Feed" in e for e in errored)
        assert any("Flaky Feed" in e for e in errored)

    def test_summary_authoritative_for_reachable(self):
        """Summary 'Feeds reachable: N/M' should be used authoritatively."""
        output = """Ingesting 3 feed(s)...
  Processing feed: Feed A
  Processing feed: Feed B
  Processing feed: Feed C
Fetched 10 items, skipped 5, errors 1. Feeds reachable: 2/3.
"""
        stats = parse_ingest_output(output)
        assert stats["feedsChecked"] == 3
        assert stats["feedsReachable"] == 2
        assert stats["feedsUnreachable"] == 1
        assert stats["fetchErrors"] == 1

    def test_stderr_bozo_exceptions(self):
        """Bozo exceptions from stderr should be collected as errors."""
        stdout = """Ingesting 1 feed(s)...
  Processing feed: Anthropic Research Blog (limit 15)
    Feed UNREACHABLE: Anthropic Research Blog
Fetched 0 items, skipped 0, errors 0. Feeds reachable: 0/1.
"""
        stderr = """    [diag] url=https://www.anthropic.com/feed.xml status=None bozo=True entries=0
    [diag] bozo_exception=SAXParseException: not well-formed (invalid token)
    Feed unreachable: SAXParseException: not well-formed (invalid token)
"""
        stats = parse_ingest_output(stdout, stderr)
        assert stats["feedsChecked"] == 1
        assert stats["feedsReachable"] == 0
        assert stats["feedsUnreachable"] == 1
        errored = stats["erroredFeeds"]
        assert any("unreachable" in e.lower() for e in errored)
        assert any("SAXParseException" in e for e in errored)


class TestParseDocpackOutput:
    def test_empty_output(self):
        stats = parse_docpack_output("")
        assert stats["docsBundled"] == 0

    def test_typical_output(self):
        output = "Bundled 12 documents -> data/docpacks/daily_bundle_2026-02-14.jsonl\n"
        stats = parse_docpack_output(output)
        assert stats["docsBundled"] == 12


class TestParseExtractOutput:
    def test_empty_output(self):
        stats = parse_extract_output("")
        assert stats["docsExtracted"] == 0
        assert stats["entitiesFound"] == 0

    def test_typical_output(self):
        output = """Extraction runner v1.0.0
Model: claude-sonnet-4-20250514
Shadow mode: ON (parallel, understudy: gpt-5-nano)
Docpack: data/docpacks/daily_bundle_2026-02-14.jsonl
Output: data/extractions

  [1/3] doc_abc: extracting... OK (5 entities, 8 relations, 1200ms)
  [2/3] doc_def: extracting... OK (3 entities, 4 relations, 980ms)
  [3/3] doc_ghi: extracting... OK (4 entities, 6 relations, 1100ms)

Done. Processed: 3, Succeeded: 3, Failed: 0
"""
        stats = parse_extract_output(output)
        assert stats["docsExtracted"] == 3
        assert stats["entitiesFound"] == 12  # 5+3+4
        assert stats["relationsFound"] == 18  # 8+4+6
        assert stats["validationErrors"] == 0

    def test_with_failures(self):
        output = """Done. Processed: 5, Succeeded: 3, Failed: 2"""
        stats = parse_extract_output(output)
        assert stats["docsExtracted"] == 3
        assert stats["validationErrors"] == 2

    def test_with_escalation(self):
        output = """Done. Processed: 5, Succeeded: 4, Failed: 1, Escalated: 2/5 (40%)"""
        stats = parse_extract_output(output)
        assert stats["docsExtracted"] == 4
        assert stats["escalated"] == 2


class TestParseImportOutput:
    def test_empty_output(self):
        stats = parse_import_output("")
        assert stats["filesImported"] == 0

    def test_typical_output(self):
        output = """Processing doc_abc.json...
  Imported: 5 entities, 8 relations
Processing doc_def.json...
  Imported: 3 entities, 4 relations

Imported 2 extraction files:
  - 8 entities (4 new, 4 resolved to existing)
  - 12 relations
  - 24 evidence records
"""
        stats = parse_import_output(output)
        assert stats["filesImported"] == 2
        assert stats["entitiesNew"] == 4
        assert stats["relations"] == 12
        assert stats["evidenceRecords"] == 24


class TestParseExportOutput:
    def test_empty_output(self):
        stats = parse_export_output("")
        assert stats["totalNodes"] == 0
        assert stats["totalEdges"] == 0


class TestParseTrendingOutput:
    def test_empty_output(self):
        stats = parse_trending_output("")
        assert stats["trendingNodes"] == 0
        assert stats["trendingEdges"] == 0


class TestCopyGraphsToLive:
    def test_copies_json_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graphs_dir = Path(tmpdir) / "graphs"
            source_dir = graphs_dir / "2026-02-14"
            source_dir.mkdir(parents=True)

            # Create sample graph files
            for name in ["mentions.json", "claims.json", "trending.json"]:
                (source_dir / name).write_text(json.dumps({"test": True}))

            live_dir = Path(tmpdir) / "live"
            result = copy_graphs_to_live(graphs_dir, "2026-02-14", live_dir)

            assert result is True
            assert (live_dir / "mentions.json").exists()
            assert (live_dir / "claims.json").exists()
            assert (live_dir / "trending.json").exists()

    def test_returns_false_when_source_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graphs_dir = Path(tmpdir) / "graphs"
            live_dir = Path(tmpdir) / "live"
            result = copy_graphs_to_live(graphs_dir, "2026-02-14", live_dir)
            assert result is False


class TestRunStage:
    def test_successful_command(self):
        result = run_stage("test", [sys.executable, "-c", "print('hello')"])
        assert result["status"] == "ok"
        assert result["returncode"] == 0
        assert "hello" in result["stdout"]
        assert result["duration_sec"] >= 0

    def test_failing_command(self):
        result = run_stage("test", [sys.executable, "-c", "import sys; sys.exit(1)"])
        assert result["status"] == "error"
        assert result["returncode"] == 1

    def test_timeout(self):
        result = run_stage(
            "test",
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=1,
        )
        assert result["status"] == "timeout"

    def test_nonexistent_command(self):
        result = run_stage("test", ["/nonexistent/command"])
        assert result["status"] == "error"


class TestDryRun:
    def test_dry_run_prints_stages(self):
        """Test that --dry-run prints stage commands without executing."""
        import subprocess

        project_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "scripts/run_pipeline.py", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        assert result.returncode == 0
        assert "DRY RUN" in result.stdout
        assert "ingest" in result.stdout
        assert "extract" in result.stdout
        assert "trending" in result.stdout

    def test_dry_run_skip_extract(self):
        """Test that --dry-run --skip-extract shows extract as skipped."""
        import subprocess

        project_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "scripts/run_pipeline.py", "--dry-run", "--skip-extract"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        assert result.returncode == 0
        assert "SKIP" in result.stdout
