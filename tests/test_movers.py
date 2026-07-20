"""Tests for scripts/run_movers.py — backend Movers exporter.

Covers the row builder (rank delta, is_new, velocity_raw, distinct sources)
and the empty-DB corner case. The actual SQL plumbing is exercised against
a real in-memory SQLite DB seeded with fixture rows.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# Add scripts/ to import path so tests can import run_movers directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from run_movers import (
    _compute_velocity_raw,
    _most_recent_run_date,
    _prior_run_date,
    _ranks_for_run,
    _velocity_ci_lower,
    build_movers_rows,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db() -> sqlite3.Connection:
    """Bare in-memory DB with the tables Movers reads from."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE documents (
            doc_id TEXT PRIMARY KEY,
            url TEXT,
            source TEXT,
            source_type TEXT NOT NULL DEFAULT 'rss',
            title TEXT,
            published_at TEXT,
            fetched_at TEXT,
            text_path TEXT,
            status TEXT
        );
        CREATE TABLE entities (
            entity_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            aliases TEXT,
            external_ids TEXT,
            first_seen TEXT,
            last_seen TEXT
        );
        CREATE TABLE relations (
            relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            rel TEXT NOT NULL,
            kind TEXT,
            verb_raw TEXT,
            confidence REAL,
            doc_id TEXT,
            extractor_version TEXT
        );
        CREATE TABLE trend_history (
            entity_id TEXT NOT NULL,
            run_date TEXT NOT NULL,
            mention_count_7d INTEGER,
            mention_count_30d INTEGER,
            velocity REAL,
            novelty REAL,
            bridge_score REAL,
            trend_score REAL,
            in_trending_view INTEGER DEFAULT 0,
            epoch INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (entity_id, run_date)
        );
    """)
    return conn


def _add_entity(conn, eid, name, type_, first_seen="2026-01-01"):
    conn.execute(
        "INSERT INTO entities (entity_id, name, type, first_seen) VALUES (?, ?, ?, ?)",
        (eid, name, type_, first_seen),
    )


def _add_th(conn, eid, run_date, trend_score, *, mc7=0, mc30=0, in_trending=0,
            velocity=None, bridge=None, epoch=1):
    conn.execute(
        """INSERT INTO trend_history
           (entity_id, run_date, mention_count_7d, mention_count_30d,
            trend_score, in_trending_view, velocity, bridge_score, epoch)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (eid, run_date, mc7, mc30, trend_score, in_trending, velocity,
         bridge, epoch),
    )


def _add_doc(conn, doc_id, source, published_at):
    conn.execute(
        """INSERT INTO documents (doc_id, source, source_type, published_at, status)
           VALUES (?, ?, 'rss', ?, 'extracted')""",
        (doc_id, source, published_at),
    )


def _add_mention(conn, entity_id, doc_id):
    """Add a MENTIONS relation pointing at the entity from a document."""
    conn.execute(
        """INSERT INTO relations (source_id, target_id, rel, doc_id)
           VALUES (?, ?, 'MENTIONS', ?)""",
        (f"doc:{doc_id}", entity_id, doc_id),
    )


# ---------------------------------------------------------------------------
# _compute_velocity_raw
# ---------------------------------------------------------------------------

class TestVelocityRaw:

    def test_simple_ratio(self):
        assert _compute_velocity_raw(10, 5) == 2.0

    def test_no_prior_returns_null(self):
        """Just-appeared (no prior-window mentions) yields null, not infinity."""
        assert _compute_velocity_raw(5, 0) is None

    def test_zero_recent_with_prior(self):
        """A dormant entity has velocity 0, not null."""
        assert _compute_velocity_raw(0, 10) == 0.0

    def test_zero_both_returns_null(self):
        assert _compute_velocity_raw(0, 0) is None

    def test_uncapped(self):
        """The point of velocity_raw is that it is NOT capped at velocity_cap (5.0)."""
        assert _compute_velocity_raw(50, 1) == 50.0


# ---------------------------------------------------------------------------
# _most_recent_run_date / _prior_run_date
# ---------------------------------------------------------------------------

class TestRunDateHelpers:

    def test_most_recent_empty_db(self):
        conn = _make_db()
        assert _most_recent_run_date(conn) is None

    def test_most_recent_picks_max(self):
        conn = _make_db()
        _add_th(conn, "a", "2026-05-01", 0.5)
        _add_th(conn, "a", "2026-05-10", 0.7)
        _add_th(conn, "a", "2026-05-05", 0.6)
        assert _most_recent_run_date(conn) == "2026-05-10"

    def test_prior_run_date_exact_match(self):
        conn = _make_db()
        _add_th(conn, "a", "2026-05-03", 0.5)
        _add_th(conn, "a", "2026-05-10", 0.7)
        assert _prior_run_date(conn, "2026-05-10", 7) == "2026-05-03"

    def test_prior_run_date_falls_back_to_closest(self):
        """If no row exists for exactly today-N, use the most recent <= that."""
        conn = _make_db()
        _add_th(conn, "a", "2026-05-01", 0.5)
        _add_th(conn, "a", "2026-05-10", 0.7)
        # Today=05-10, window=7 → target=05-03; closest <= is 05-01
        assert _prior_run_date(conn, "2026-05-10", 7) == "2026-05-01"

    def test_prior_run_date_none_when_no_prior(self):
        conn = _make_db()
        _add_th(conn, "a", "2026-05-10", 0.7)
        assert _prior_run_date(conn, "2026-05-10", 7) is None


# ---------------------------------------------------------------------------
# _ranks_for_run — ROW_NUMBER ordering
# ---------------------------------------------------------------------------

class TestRanks:

    def test_ranks_by_trend_score_desc(self):
        conn = _make_db()
        _add_th(conn, "a", "2026-05-10", 0.5)
        _add_th(conn, "b", "2026-05-10", 0.9)
        _add_th(conn, "c", "2026-05-10", 0.7)
        ranks = _ranks_for_run(conn, "2026-05-10")
        assert ranks["b"]["rank"] == 1
        assert ranks["c"]["rank"] == 2
        assert ranks["a"]["rank"] == 3

    def test_in_trending_view_round_trips(self):
        conn = _make_db()
        _add_th(conn, "a", "2026-05-10", 0.5, in_trending=1)
        _add_th(conn, "b", "2026-05-10", 0.9, in_trending=0)
        ranks = _ranks_for_run(conn, "2026-05-10")
        assert ranks["a"]["in_trending_view"] is True
        assert ranks["b"]["in_trending_view"] is False


# ---------------------------------------------------------------------------
# build_movers_rows — end-to-end
# ---------------------------------------------------------------------------

class TestBuildMoversRows:

    def test_empty_trend_history(self):
        """Fresh DB returns no rows and a null dateRange.start."""
        conn = _make_db()
        rows, date_range = build_movers_rows(conn, 7, "MENTIONS")
        assert rows == []
        assert date_range["start"] is None

    def test_returning_entity_has_rank_delta(self):
        conn = _make_db()
        _add_entity(conn, "org:a", "Alpha", "Org", first_seen="2026-01-01")
        # 7 days ago entity ranked 3, today ranked 1 → climbed 2
        _add_th(conn, "org:a", "2026-05-03", trend_score=0.1)
        _add_th(conn, "org:b", "2026-05-03", trend_score=0.5)
        _add_th(conn, "org:c", "2026-05-03", trend_score=0.9)
        _add_th(conn, "org:a", "2026-05-10", trend_score=0.9)
        rows, _ = build_movers_rows(conn, 7, "MENTIONS")
        row_a = next(r for r in rows if r["entity_id"] == "org:a")
        assert row_a["current_rank"] == 1
        assert row_a["rank_prior"] == 3
        assert row_a["rank_delta"] == 2
        assert row_a["is_new"] is False

    def test_just_appeared_entity_is_new(self):
        """Entity with no prior trend_history row has is_new=True."""
        conn = _make_db()
        _add_entity(conn, "tech:novel", "Novel Thing", "Tech",
                    first_seen="2026-05-08")
        _add_th(conn, "tech:novel", "2026-05-10", trend_score=0.4)
        # Need a prior run date for the function to look up — populate
        # someone else's row 7 days back so prior_run_date exists.
        _add_entity(conn, "org:other", "Other", "Org", first_seen="2026-01-01")
        _add_th(conn, "org:other", "2026-05-03", trend_score=0.5)
        _add_th(conn, "org:other", "2026-05-10", trend_score=0.5)
        rows, _ = build_movers_rows(conn, 7, "MENTIONS")
        row = next(r for r in rows if r["entity_id"] == "tech:novel")
        assert row["is_new"] is True
        assert row["rank_prior"] is None
        assert row["rank_delta"] is None

    def test_velocity_raw_from_mentions(self):
        """Velocity is computed from the relations table, uncapped."""
        conn = _make_db()
        _add_entity(conn, "org:fast", "Fast Co", "Org", first_seen="2026-04-01")
        _add_th(conn, "org:fast", "2026-05-10", trend_score=0.5, mc7=20)
        _add_th(conn, "org:fast", "2026-05-03", trend_score=0.5, mc7=2)

        # 6 recent (in 2026-05-03..2026-05-10), 2 earlier (in 2026-04-26..2026-05-03)
        for i in range(6):
            _add_doc(conn, f"d{i}", "feedA", "2026-05-07")
            _add_mention(conn, "org:fast", f"d{i}")
        for i in range(2):
            _add_doc(conn, f"e{i}", "feedA", "2026-05-01")
            _add_mention(conn, "org:fast", f"e{i}")

        rows, _ = build_movers_rows(conn, 7, "MENTIONS")
        row = next(r for r in rows if r["entity_id"] == "org:fast")
        assert row["velocity_raw"] == pytest.approx(3.0)

    def test_velocity_raw_null_when_no_prior_mentions(self):
        """Brand-new entity with no prior-window mentions → velocity null."""
        conn = _make_db()
        _add_entity(conn, "org:new", "New", "Org", first_seen="2026-05-08")
        _add_th(conn, "org:new", "2026-05-10", trend_score=0.3, mc7=4)
        for i in range(4):
            _add_doc(conn, f"d{i}", "feedA", "2026-05-08")
            _add_mention(conn, "org:new", f"d{i}")
        rows, _ = build_movers_rows(conn, 7, "MENTIONS")
        row = next(r for r in rows if r["entity_id"] == "org:new")
        assert row["velocity_raw"] is None

    def test_distinct_sources_counts_unique_feeds(self):
        conn = _make_db()
        _add_entity(conn, "org:s", "S", "Org", first_seen="2026-04-01")
        _add_th(conn, "org:s", "2026-05-10", trend_score=0.5, mc7=4)
        _add_doc(conn, "d1", "feedA", "2026-05-08")
        _add_doc(conn, "d2", "feedA", "2026-05-09")
        _add_doc(conn, "d3", "feedB", "2026-05-08")
        _add_doc(conn, "d4", "feedC", "2026-05-09")
        for d in ("d1", "d2", "d3", "d4"):
            _add_mention(conn, "org:s", d)
        rows, _ = build_movers_rows(conn, 7, "MENTIONS")
        row = next(r for r in rows if r["entity_id"] == "org:s")
        # 3 unique sources (feedA, feedB, feedC) even though 4 mentions
        assert row["distinct_sources_7d"] == 3

    def test_rows_sorted_by_current_rank(self):
        conn = _make_db()
        _add_entity(conn, "a", "A", "Org", first_seen="2026-01-01")
        _add_entity(conn, "b", "B", "Org", first_seen="2026-01-01")
        _add_entity(conn, "c", "C", "Org", first_seen="2026-01-01")
        _add_th(conn, "a", "2026-05-10", trend_score=0.5)
        _add_th(conn, "b", "2026-05-10", trend_score=0.9)
        _add_th(conn, "c", "2026-05-10", trend_score=0.7)
        rows, _ = build_movers_rows(conn, 7, "MENTIONS")
        assert [r["entity_id"] for r in rows] == ["b", "c", "a"]

    def test_row_has_all_required_fields(self):
        """Every row should have the 18 fields from schemas/movers.json."""
        conn = _make_db()
        _add_entity(conn, "a", "A", "Org", first_seen="2026-04-01")
        _add_th(conn, "a", "2026-05-10", trend_score=0.5, mc7=3, mc30=8,
                in_trending=1)
        rows, _ = build_movers_rows(conn, 7, "MENTIONS")
        assert len(rows) == 1
        required = {
            "entity_id", "label", "type",
            "current_rank", "rank_prior", "rank_delta", "is_new",
            "velocity_raw", "velocity_ci_lower", "sustained", "bridge_delta",
            "mention_count_7d", "mention_count_30d",
            "first_seen", "days_since_first_seen",
            "distinct_sources_7d", "in_trending_view", "trend_score",
        }
        assert set(rows[0].keys()) == required


# ---------------------------------------------------------------------------
# _velocity_ci_lower (Sprint 20.7)
# ---------------------------------------------------------------------------

class TestVelocityCiLower:

    def test_null_only_when_both_windows_empty(self):
        assert _velocity_ci_lower(0, 0) is None
        assert _velocity_ci_lower(4, 0) is not None
        assert _velocity_ci_lower(0, 4) is not None

    def test_lower_than_point_ratio(self):
        """The bound is conservative: always below the observed ratio."""
        for recent, previous in [(3, 1), (6, 2), (30, 10), (100, 50)]:
            assert _velocity_ci_lower(recent, previous) < recent / previous

    def test_more_evidence_tightens_the_bound(self):
        """Same 3:1 ratio, more data → higher lower bound.

        This is the whole point of 20.7: a 3/1 'tripled!' riser must rank
        below a 30/10 riser even though the point ratios are identical.
        """
        small = _velocity_ci_lower(3, 1)
        large = _velocity_ci_lower(30, 10)
        assert small < large < 3.0

    def test_zero_prior_surge_is_defined_and_humble(self):
        """0→N surges get a finite, deflated bound instead of null/infinity."""
        bound = _velocity_ci_lower(12, 0)
        assert bound is not None
        assert 1.0 < bound < 12.0

    def test_single_mention_self_suppresses(self):
        """1 mention from nothing is noise; the bound says so."""
        assert _velocity_ci_lower(1, 0) < 1.0

    def test_decline_stays_below_one(self):
        assert _velocity_ci_lower(2, 10) < 1.0


# ---------------------------------------------------------------------------
# sustained (20.8), bridge_delta (20.9), epoch guard (20.1b)
# ---------------------------------------------------------------------------

class TestSustainedFlag:

    def _two_run_db(self, prior_velocity, today_velocity):
        conn = _make_db()
        _add_entity(conn, "org:r", "Riser", "Org", first_seen="2026-01-01")
        _add_th(conn, "org:r", "2026-05-03", trend_score=0.5,
                velocity=prior_velocity)
        _add_th(conn, "org:r", "2026-05-10", trend_score=0.5,
                velocity=today_velocity)
        return conn

    def test_rising_in_both_windows(self):
        rows, _ = build_movers_rows(self._two_run_db(1.5, 2.0), 7, "MENTIONS")
        assert rows[0]["sustained"] is True

    def test_prior_window_flat_or_falling(self):
        rows, _ = build_movers_rows(self._two_run_db(0.8, 2.0), 7, "MENTIONS")
        assert rows[0]["sustained"] is False

    def test_gated_velocity_never_qualifies(self):
        """Small-N runs store gated velocity 1.0 — not > 1, not sustained."""
        rows, _ = build_movers_rows(self._two_run_db(1.0, 2.0), 7, "MENTIONS")
        assert rows[0]["sustained"] is False

    def test_no_prior_run(self):
        conn = _make_db()
        _add_entity(conn, "org:r", "Riser", "Org", first_seen="2026-05-01")
        _add_th(conn, "org:r", "2026-05-10", trend_score=0.5, velocity=3.0)
        rows, _ = build_movers_rows(conn, 7, "MENTIONS")
        assert rows[0]["sustained"] is False


class TestBridgeDelta:

    def test_delta_vs_prior_run(self):
        conn = _make_db()
        _add_entity(conn, "org:b", "Bridge Co", "Org", first_seen="2026-01-01")
        _add_th(conn, "org:b", "2026-05-03", trend_score=0.5, bridge=3.0)
        _add_th(conn, "org:b", "2026-05-10", trend_score=0.5, bridge=5.5)
        rows, _ = build_movers_rows(conn, 7, "MENTIONS")
        assert rows[0]["bridge_delta"] == pytest.approx(2.5)

    def test_null_without_prior_row(self):
        conn = _make_db()
        _add_entity(conn, "org:b", "Bridge Co", "Org", first_seen="2026-05-01")
        _add_th(conn, "org:b", "2026-05-10", trend_score=0.5, bridge=5.5)
        rows, _ = build_movers_rows(conn, 7, "MENTIONS")
        assert rows[0]["bridge_delta"] is None


class TestEpochGuard:

    def test_prior_run_in_older_epoch_is_ignored(self):
        """Windows never span epochs: an epoch-1 run 7d back must not be
        the comparison baseline for an epoch-2 export (ADR-010 / 20.1b)."""
        conn = _make_db()
        _add_entity(conn, "org:x", "X", "Org", first_seen="2026-01-01")
        _add_th(conn, "org:x", "2026-05-03", trend_score=0.9, velocity=2.0,
                bridge=4.0, epoch=1)
        _add_th(conn, "org:x", "2026-05-10", trend_score=0.5, velocity=2.0,
                bridge=6.0, epoch=2)
        rows, _ = build_movers_rows(conn, 7, "MENTIONS")
        row = rows[0]
        assert row["is_new"] is True
        assert row["rank_prior"] is None
        assert row["sustained"] is False
        assert row["bridge_delta"] is None

    def test_same_epoch_prior_run_is_used(self):
        conn = _make_db()
        _add_entity(conn, "org:x", "X", "Org", first_seen="2026-01-01")
        _add_th(conn, "org:x", "2026-05-03", trend_score=0.9, velocity=2.0,
                bridge=4.0, epoch=2)
        _add_th(conn, "org:x", "2026-05-10", trend_score=0.5, velocity=2.0,
                bridge=6.0, epoch=2)
        rows, _ = build_movers_rows(conn, 7, "MENTIONS")
        row = rows[0]
        assert row["is_new"] is False
        assert row["sustained"] is True
        assert row["bridge_delta"] == pytest.approx(2.0)
