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
Feed OK: 20 items
Processing feed: Hugging Face Blog
Feed OK: 3 items
Processing feed: OpenAI Blog
Feed OK: 1 items
Saved 12 new documents
Skipping 4 existing duplicates
"""
        stats = parse_ingest_output(output)
        assert stats["feedsChecked"] == 3
        assert stats["feedsReachable"] == 3
        assert stats["newDocsFound"] == 12
        assert stats["duplicatesSkipped"] == 4

    def test_fetch_errors(self):
        output = """Processing feed: arXiv CS.AI
Feed OK: 20 items
Processing feed: Broken Feed
Error fetching feed: Connection refused
"""
        stats = parse_ingest_output(output)
        assert stats["feedsChecked"] == 2
        assert stats["fetchErrors"] == 1


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
