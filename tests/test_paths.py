"""Tests for util.paths domain-aware path helpers."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from util.paths import (
    get_db_path,
    get_docpacks_dir,
    get_extractions_dir,
    get_graphs_dir,
    get_logs_dir,
    get_raw_dir,
    get_text_dir,
)


class TestPathHelpers:
    """Verify domain-scoped paths."""

    def test_db_path_contains_domain(self):
        assert get_db_path("ai") == Path("data/db/ai.db")
        assert get_db_path("biosafety") == Path("data/db/biosafety.db")

    def test_raw_dir_scoped(self):
        assert get_raw_dir("ai") == Path("data/raw/ai")

    def test_text_dir_scoped(self):
        assert get_text_dir("biosafety") == Path("data/text/biosafety")

    def test_docpacks_dir_scoped(self):
        assert get_docpacks_dir("ai") == Path("data/docpacks/ai")

    def test_extractions_dir_scoped(self):
        assert get_extractions_dir("ai") == Path("data/extractions/ai")

    def test_graphs_dir_scoped(self):
        assert get_graphs_dir("ai") == Path("data/graphs/ai")

    def test_logs_dir_scoped(self):
        assert get_logs_dir("ai") == Path("data/logs/ai")

    def test_different_domains_never_collide(self):
        dirs = [get_raw_dir, get_text_dir, get_docpacks_dir,
                get_extractions_dir, get_graphs_dir, get_logs_dir]
        for fn in dirs:
            assert fn("ai") != fn("biosafety"), (
                f"{fn.__name__}('ai') must differ from {fn.__name__}('biosafety')"
            )

    def test_default_domain_is_ai(self, monkeypatch):
        monkeypatch.delenv("PREDICTOR_DOMAIN", raising=False)
        assert get_db_path() == Path("data/db/ai.db")
        assert get_raw_dir() == Path("data/raw/ai")

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("PREDICTOR_DOMAIN", "biosafety")
        assert get_db_path() == Path("data/db/biosafety.db")
        assert get_raw_dir() == Path("data/raw/biosafety")

    def test_explicit_domain_overrides_env(self, monkeypatch):
        monkeypatch.setenv("PREDICTOR_DOMAIN", "biosafety")
        assert get_db_path("ai") == Path("data/db/ai.db")
