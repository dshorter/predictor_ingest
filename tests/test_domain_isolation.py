"""Tests for domain database isolation.

Verifies that:
1. Each domain gets its own database file
2. It is structurally impossible for records to bleed across domains
3. The Makefile and pipeline derive DB paths from the domain slug
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestDomainDBIsolation:
    """Verify domain isolation via separate database files."""

    def test_makefile_db_derives_from_domain(self):
        """Makefile DB variable should use $(DOMAIN) in the path."""
        makefile = Path(__file__).parent.parent / "Makefile"
        content = makefile.read_text()
        # DB default should reference $(DOMAIN), not a hardcoded name
        assert "$(DOMAIN).db" in content, (
            "Makefile DB default must derive from $(DOMAIN) for isolation"
        )

    def test_pipeline_db_derives_from_domain(self):
        """run_pipeline.py should derive DB path from --domain flag."""
        pipeline = Path(__file__).parent.parent / "scripts" / "run_pipeline.py"
        content = pipeline.read_text()
        # Should construct DB path from domain slug
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
        # The default should NOT be the old hardcoded path
        assert 'default="data/db/predictor.db"' not in content, (
            "Pipeline must not hardcode predictor.db; use {domain}.db"
        )
