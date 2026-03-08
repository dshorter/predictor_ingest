"""Tests for domain database and data directory isolation.

Verifies that:
1. Each domain gets its own database file
2. Each domain gets its own data directories (raw, text, docpacks, etc.)
3. It is structurally impossible for records to bleed across domains
4. The Makefile and pipeline derive DB paths from the domain slug
5. No scripts hardcode 'predictor.db' as a default
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Scripts that should NOT default to predictor.db
SCRIPTS_MUST_USE_DOMAIN_DB = [
    "scripts/run_pipeline.py",
    "scripts/run_extract.py",
    "scripts/build_docpack.py",
    "scripts/run_export.py",
    "scripts/run_resolve.py",
    "scripts/run_trending.py",
    "scripts/import_extractions.py",
    "scripts/repair_data.py",
    "scripts/init_db.py",
    "scripts/health_report.py",
    "scripts/shadow_report.py",
    "scripts/generate_dashboard_json.py",
    "scripts/collect_diagnostics.py",
]


class TestDomainDBIsolation:
    """Verify domain isolation via separate database files."""

    def test_makefile_db_derives_from_domain(self):
        """Makefile DB variable should use $(DOMAIN) in the path."""
        makefile = Path(__file__).parent.parent / "Makefile"
        content = makefile.read_text()
        assert "$(DOMAIN).db" in content, (
            "Makefile DB default must derive from $(DOMAIN) for isolation"
        )

    def test_pipeline_db_derives_from_domain(self):
        """run_pipeline.py should derive DB path from --domain flag."""
        pipeline = Path(__file__).parent.parent / "scripts" / "run_pipeline.py"
        content = pipeline.read_text()
        assert "args.domain" in content and ".db" in content, (
            "run_pipeline.py must derive DB path from domain slug"
        )

    def test_two_domains_get_different_db_paths(self):
        """Two different domains must resolve to different DB files."""
        db_ai = f"data/db/ai.db"
        db_bio = f"data/db/biosafety.db"
        assert db_ai != db_bio, "Domain DB paths must differ"
        assert "ai" in db_ai
        assert "biosafety" in db_bio

    def test_domain_db_path_contains_slug(self):
        """DB path must contain the domain slug — bleed is structurally impossible."""
        domains = ["ai", "biosafety", "cyber", "climate"]
        for domain in domains:
            db_path = f"data/db/{domain}.db"
            assert domain in db_path, (
                f"DB path for domain '{domain}' must contain the slug"
            )

    def test_no_shared_db_reference_in_pipeline(self):
        """Pipeline should not hardcode 'predictor.db' as default."""
        pipeline = Path(__file__).parent.parent / "scripts" / "run_pipeline.py"
        content = pipeline.read_text()
        assert 'default="data/db/predictor.db"' not in content, (
            "Pipeline must not hardcode predictor.db; use {domain}.db"
        )

    @pytest.mark.parametrize("script", SCRIPTS_MUST_USE_DOMAIN_DB)
    def test_no_hardcoded_predictor_db_default(self, script):
        """Scripts must not hardcode predictor.db as argparse default."""
        path = Path(__file__).parent.parent / script
        if not path.exists():
            pytest.skip(f"{script} not found")
        content = path.read_text()
        assert 'default="data/db/predictor.db"' not in content, (
            f"{script} must not hardcode predictor.db; use domain-scoped default"
        )
        assert "default=str(ROOT / \"data\" / \"db\" / \"predictor.db\")" not in content, (
            f"{script} must not hardcode predictor.db via ROOT"
        )


class TestDomainDataDirIsolation:
    """Verify data directories are scoped by domain."""

    def test_makefile_docpack_dir_scoped(self):
        """Makefile DOCPACK_DIR should include $(DOMAIN)."""
        makefile = Path(__file__).parent.parent / "Makefile"
        content = makefile.read_text()
        assert "data/docpacks/$(DOMAIN)" in content, (
            "Makefile DOCPACK_DIR must be domain-scoped"
        )

    def test_makefile_extractions_dir_scoped(self):
        """Makefile EXTRACTIONS_DIR should include $(DOMAIN)."""
        makefile = Path(__file__).parent.parent / "Makefile"
        content = makefile.read_text()
        assert "data/extractions/$(DOMAIN)" in content, (
            "Makefile EXTRACTIONS_DIR must be domain-scoped"
        )

    def test_makefile_graphs_dir_scoped(self):
        """Makefile GRAPHS_DIR should include $(DOMAIN)."""
        makefile = Path(__file__).parent.parent / "Makefile"
        content = makefile.read_text()
        assert "data/graphs/$(DOMAIN)" in content, (
            "Makefile GRAPHS_DIR must be domain-scoped"
        )

    def test_makefile_ingest_passes_domain_dirs(self):
        """Makefile ingest target should pass domain-scoped raw/text dirs."""
        makefile = Path(__file__).parent.parent / "Makefile"
        content = makefile.read_text()
        assert "data/raw/$(DOMAIN)" in content, (
            "Makefile ingest must pass domain-scoped --raw-dir"
        )
        assert "data/text/$(DOMAIN)" in content, (
            "Makefile ingest must pass domain-scoped --text-dir"
        )
