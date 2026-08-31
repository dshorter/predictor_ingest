"""Tests for token-usage cost accounting (src/db).

This is the money path, and until 2026-08-31 it had no tests at all — which is
part of why two defects lived in it for weeks: `claude-sonnet-5` was missing
from the rate table so cost logged NULL, and extraction was priced at sync rates
despite running through the Batch API at half.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db import (  # noqa: E402
    _compute_cost,
    ensure_token_usage_table,
    log_token_usage,
    spend_for_run,
    spend_since,
)


@pytest.fixture
def conn(monkeypatch):
    # The ceiling is enforced inside log_token_usage; these tests are about
    # accounting, not halting, so disable it explicitly.
    monkeypatch.setenv("PREDICTOR_MAX_COST_USD", "0")
    c = sqlite3.connect(":memory:")
    ensure_token_usage_table(c)
    yield c
    c.close()


class TestBatchPricing:
    def test_batch_is_half_of_sync(self):
        args = ("claude-sonnet-5", 1_000_000, 1_000_000)
        assert _compute_cost(*args, "sync") == pytest.approx(12.00)   # $2 + $10
        assert _compute_cost(*args, "batch") == pytest.approx(6.00)

    def test_sync_is_the_default(self):
        a = _compute_cost("claude-sonnet-5", 1000, 1000)
        b = _compute_cost("claude-sonnet-5", 1000, 1000, "sync")
        assert a == b

    def test_unknown_billing_mode_raises(self):
        # Loudly, rather than silently falling back to a rate — a wrong
        # multiplier is invisible in the output but doubles the books.
        with pytest.raises(ValueError, match="unknown billing_mode"):
            _compute_cost("claude-sonnet-5", 10, 10, "batched")

    def test_unpriced_model_returns_none_not_zero(self):
        # Zero would be indistinguishable from a free call and would sum
        # silently into a total; None is what makes it countable as unknown.
        assert _compute_cost("some-model-nobody-priced", 10_000, 10_000) is None

    @pytest.mark.parametrize("model,expected_in,expected_out", [
        ("claude-sonnet-5", 2.00, 10.00),
        ("claude-sonnet-4-6", 3.00, 15.00),
        ("claude-haiku-4-5", 1.00, 5.00),
        # The dated alias must resolve to the same rate as the bare id; it is
        # what NARRATIVE_MODEL actually passes.
        ("claude-haiku-4-5-20251001", 1.00, 5.00),
    ])
    def test_rates_match_the_published_table(self, model, expected_in, expected_out):
        got = _compute_cost(model, 1_000_000, 0)
        assert got == pytest.approx(expected_in)
        got = _compute_cost(model, 0, 1_000_000)
        assert got == pytest.approx(expected_out)

    def test_haiku_45_is_not_priced_as_haiku_35(self):
        # Regression: Haiku 4.5 carried Haiku 3.5's (0.25, 1.25) until
        # 2026-08-29, understating every narrative call by 4x.
        assert _compute_cost("claude-haiku-4-5", 1_000_000, 0) == pytest.approx(1.00)


class TestLogging:
    def test_billing_mode_is_persisted(self, conn):
        log_token_usage(conn, "2026-08-31", "extraction", "claude-sonnet-5",
                        1000, 500, doc_id="d1", billing_mode="batch")
        row = conn.execute(
            "SELECT billing_mode, cost_usd FROM token_usage").fetchone()
        assert row[0] == "batch"
        assert row[1] == pytest.approx((1000 * 2.0 + 500 * 10.0) * 0.5 / 1e6)

    def test_migration_is_idempotent(self, conn):
        ensure_token_usage_table(conn)
        ensure_token_usage_table(conn)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(token_usage)")]
        assert cols.count("billing_mode") == 1


class TestSpendViews:
    """The two views answer different questions and must not be conflated.

    ADR-008's staggered handoff means a run submits today's batch and collects
    yesterday's, so extraction cost lands on a run_date whose run has already
    finished. Reporting only per-run_date would omit extraction — ~90% of the
    bill — from every notice on the day it is submitted.
    """

    def _seed(self, conn):
        # Extraction booked to the 30th but billed (created_at) on the 31st,
        # exactly as a next-day collect records it.
        conn.execute(
            """INSERT INTO token_usage
                 (run_date, stage, model, input_tokens, output_tokens, cost_usd,
                  billing_mode, created_at)
               VALUES ('2026-08-30','extraction','claude-sonnet-5',0,0,4.00,
                       'batch','2026-08-31 06:10:00')""")
        # Synthesis both booked and billed on the 31st.
        conn.execute(
            """INSERT INTO token_usage
                 (run_date, stage, model, input_tokens, output_tokens, cost_usd,
                  billing_mode, created_at)
               VALUES ('2026-08-31','synthesis','claude-sonnet-5',0,0,0.25,
                       'sync','2026-08-31 06:20:00')""")
        conn.commit()

    def test_run_date_view_misses_the_collected_batch(self, conn):
        self._seed(conn)
        assert spend_for_run(conn, "2026-08-31")["total_usd"] == pytest.approx(0.25)
        assert spend_for_run(conn, "2026-08-30")["total_usd"] == pytest.approx(4.00)

    def test_billed_view_captures_what_the_run_actually_spent(self, conn):
        self._seed(conn)
        billed = spend_since(conn, "2026-08-31 06:00:00")
        assert billed["total_usd"] == pytest.approx(4.25)
        assert billed["by_stage"]["extraction"] == pytest.approx(4.00)

    def test_unpriced_calls_are_counted_not_dropped(self, conn):
        log_token_usage(conn, "2026-08-31", "extraction", "unpriced-model-x",
                        1000, 1000, billing_mode="batch")
        out = spend_for_run(conn, "2026-08-31")
        assert out["calls"] == 1
        assert out["unpriced_calls"] == 1
        assert out["total_usd"] == 0.0  # NULL sums to zero — hence the counter
