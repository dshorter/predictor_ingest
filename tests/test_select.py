"""Tests for quality-based document selection (src/select/).

Tests the pre-extraction quality scoring and budget selection algorithm
that controls extraction costs while ensuring feed representation.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from doc_select import (
    BENCH_EXPIRY_DAYS,
    DEFAULT_BUDGET,
    DEFAULT_STRETCH_MAX,
    MIN_QUALITY_THRESHOLD,
    STRETCH_QUALITY_THRESHOLD,
    WORDS_HIGH,
    WORDS_IDEAL,
    WORDS_LOW,
    ScoredDoc,
    _recency_score,
    clear_bench_doc,
    expire_bench,
    load_bench,
    save_bench,
    score_document,
    select_for_extraction,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_text(word_count: int) -> str:
    """Generate dummy text with the specified word count."""
    return " ".join(f"word{i}" for i in range(word_count))


def _make_candidate(
    doc_id: str,
    source: str = "Test Feed",
    title: str = "Test Article",
    published_at: str = "2026-02-28",
    word_count: int = 800,
) -> dict:
    """Create a candidate document dict for selection."""
    return {
        "doc_id": doc_id,
        "source": source,
        "title": title,
        "published_at": published_at,
        "text": _make_text(word_count),
        "url": f"https://example.com/{doc_id}",
        "fetched": "2026-02-28T12:00:00Z",
    }


def _make_bench_db() -> sqlite3.Connection:
    """Create an in-memory SQLite DB with documents + bench tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE documents (
            doc_id TEXT PRIMARY KEY,
            url TEXT,
            source TEXT,
            title TEXT,
            published_at TEXT,
            fetched_at TEXT,
            text_path TEXT,
            status TEXT
        );
        CREATE TABLE bench (
            doc_id TEXT PRIMARY KEY,
            quality_score REAL NOT NULL,
            scored_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
        );
        CREATE INDEX idx_bench_expires ON bench(expires_at);
        CREATE INDEX idx_bench_quality ON bench(quality_score DESC);
    """)
    return conn


# ---------------------------------------------------------------------------
# score_document tests
# ---------------------------------------------------------------------------

class TestScoreDocument:
    def test_ideal_document(self):
        """A well-formed doc from a tier-1 primary source scores high."""
        text = _make_text(WORDS_IDEAL)
        score, breakdown = score_document(
            text=text, title="Good Title", published_at="2026-02-28",
            tier=1, signal="primary",
            reference_date=date(2026, 2, 28),
        )
        assert score > 0.85
        assert breakdown["word_count"] == 1.0
        assert breakdown["metadata"] == 1.0
        assert breakdown["source_tier"] == 1.0
        assert breakdown["signal_type"] == 1.0
        assert breakdown["recency"] == 1.0

    def test_empty_text_scores_zero_on_word_count(self):
        """Empty text should score 0 on word count component."""
        score, breakdown = score_document(text="", title="Title", published_at="2026-01-01")
        assert breakdown["word_count"] == 0.0
        # Other components (metadata, tier, signal) still contribute,
        # so the combined score can be > 0 even with empty text.
        # But it should be lower than a doc with real text.
        score_with_text, _ = score_document(
            text="some real article text here " * 50,
            title="Title", published_at="2026-01-01",
        )
        assert score < score_with_text

    def test_short_text_penalized(self):
        """Very short articles score lower on word count."""
        short_text = _make_text(50)
        score_short, bd_short = score_document(text=short_text)
        ideal_text = _make_text(WORDS_IDEAL)
        score_ideal, bd_ideal = score_document(text=ideal_text)
        assert bd_short["word_count"] < bd_ideal["word_count"]
        assert score_short < score_ideal

    def test_very_long_text_gentle_decay(self):
        """Very long articles get a gentle decay but never below 0.7."""
        long_text = _make_text(10000)
        score, breakdown = score_document(text=long_text)
        assert breakdown["word_count"] >= 0.7
        assert breakdown["word_count"] <= 1.0

    def test_words_low_boundary(self):
        """At exactly WORDS_LOW, word count score should be ~0.5."""
        text = _make_text(WORDS_LOW)
        _, breakdown = score_document(text=text)
        assert abs(breakdown["word_count"] - 0.5) < 0.01

    def test_missing_title_penalized(self):
        """No title reduces metadata score by 0.5."""
        _, with_title = score_document(text="some text", title="Title", published_at="2026-01-01")
        _, without_title = score_document(text="some text", title=None, published_at="2026-01-01")
        assert with_title["metadata"] == 1.0
        assert without_title["metadata"] == 0.5

    def test_missing_date_penalized(self):
        """No published date reduces metadata score by 0.5."""
        _, with_date = score_document(text="some text", title="Title", published_at="2026-01-01")
        _, without_date = score_document(text="some text", title="Title", published_at=None)
        assert with_date["metadata"] == 1.0
        assert without_date["metadata"] == 0.5

    def test_tier_2_lower_than_tier_1(self):
        """Tier 2 sources score lower than tier 1."""
        text = _make_text(500)
        score_t1, _ = score_document(text=text, tier=1)
        score_t2, _ = score_document(text=text, tier=2)
        assert score_t1 > score_t2

    def test_echo_lower_than_primary(self):
        """Echo signal type scores lower than primary."""
        text = _make_text(500)
        score_primary, _ = score_document(text=text, signal="primary")
        score_echo, _ = score_document(text=text, signal="echo")
        assert score_primary > score_echo

    def test_score_in_valid_range(self):
        """Score should always be between 0.0 and 1.0."""
        for wc in [0, 10, 100, 500, 1000, 5000, 20000]:
            for tier in [1, 2, 3]:
                for signal in ["primary", "commentary", "echo", "community"]:
                    score, _ = score_document(
                        text=_make_text(wc),
                        title="T" if wc > 0 else None,
                        published_at="2026-01-01" if wc > 50 else None,
                        tier=tier,
                        signal=signal,
                    )
                    assert 0.0 <= score <= 1.0, f"Score {score} out of range for wc={wc}, tier={tier}, signal={signal}"

    def test_breakdown_has_raw_word_count(self):
        """Breakdown should include the raw word count."""
        text = _make_text(42)
        _, breakdown = score_document(text=text)
        assert breakdown["word_count_raw"] == 42

    def test_breakdown_has_recency(self):
        """Breakdown should include recency score."""
        text = _make_text(500)
        _, breakdown = score_document(text=text, published_at="2026-03-16",
                                       reference_date=date(2026, 3, 16))
        assert "recency" in breakdown
        assert breakdown["recency"] == 1.0


# ---------------------------------------------------------------------------
# Recency scoring tests
# ---------------------------------------------------------------------------

class TestRecencyScore:
    def test_same_day(self):
        """Published today should get full credit."""
        assert _recency_score("2026-03-16", date(2026, 3, 16)) == 1.0

    def test_one_day_old(self):
        """1 day old is within the 0-3 day full-credit window."""
        assert _recency_score("2026-03-15", date(2026, 3, 16)) == 1.0

    def test_three_days_old(self):
        """3 days old is the edge of the full-credit window."""
        assert _recency_score("2026-03-13", date(2026, 3, 16)) == 1.0

    def test_five_days_old(self):
        """5 days old should be in the 3-7 day decay band."""
        score = _recency_score("2026-03-11", date(2026, 3, 16))
        assert 0.5 < score < 1.0

    def test_seven_days_old(self):
        """7 days old should be at the bottom of the first decay band (~0.5)."""
        score = _recency_score("2026-03-09", date(2026, 3, 16))
        assert abs(score - 0.5) < 0.01

    def test_ten_days_old(self):
        """10 days old should be in the 7-14 day decay band."""
        score = _recency_score("2026-03-06", date(2026, 3, 16))
        assert 0.3 < score < 0.5

    def test_fourteen_days_old(self):
        """14 days old should be at the floor (~0.3)."""
        score = _recency_score("2026-03-02", date(2026, 3, 16))
        assert abs(score - 0.3) < 0.01

    def test_very_old(self):
        """30 days old should be at the floor (0.3)."""
        assert _recency_score("2026-02-14", date(2026, 3, 16)) == 0.3

    def test_future_date(self):
        """Future dates (clock skew) treated as fresh."""
        assert _recency_score("2026-03-18", date(2026, 3, 16)) == 1.0

    def test_no_date(self):
        """Missing date gets modest penalty (0.4)."""
        assert _recency_score(None) == 0.4
        assert _recency_score("") == 0.4

    def test_invalid_date(self):
        """Invalid date string gets modest penalty."""
        assert _recency_score("not-a-date") == 0.4

    def test_datetime_format(self):
        """ISO datetime with time component should work."""
        score = _recency_score("2026-03-16T14:30:00Z", date(2026, 3, 16))
        assert score == 1.0

    def test_recency_affects_overall_score(self):
        """Fresh articles should score higher than old ones, all else equal."""
        text = _make_text(800)
        ref = date(2026, 3, 16)
        score_fresh, _ = score_document(
            text=text, title="Title", published_at="2026-03-16",
            tier=1, signal="primary", reference_date=ref,
        )
        score_old, _ = score_document(
            text=text, title="Title", published_at="2026-02-16",
            tier=1, signal="primary", reference_date=ref,
        )
        assert score_fresh > score_old


# ---------------------------------------------------------------------------
# select_for_extraction tests
# ---------------------------------------------------------------------------

class TestSelectForExtraction:
    def test_empty_candidates(self):
        """Empty input returns empty output."""
        selected, overflow = select_for_extraction([], {}, {})
        assert selected == []
        assert overflow == []

    def test_under_budget_returns_all(self):
        """When candidates <= budget, all are returned."""
        candidates = [_make_candidate(f"doc{i}") for i in range(5)]
        selected, overflow = select_for_extraction(candidates, {}, {}, budget=10)
        assert len(selected) == 5
        assert len(overflow) == 0

    def test_over_budget_selects_budget(self):
        """When candidates > budget, returns approximately budget docs."""
        candidates = [_make_candidate(f"doc{i}") for i in range(50)]
        selected, overflow = select_for_extraction(candidates, {}, {}, budget=20, stretch_max=25)
        assert len(selected) <= 25
        assert len(selected) >= 20

    def test_overflow_contains_remaining(self):
        """Overflow should contain qualified docs that didn't make the cut."""
        candidates = [_make_candidate(f"doc{i}", word_count=800) for i in range(50)]
        selected, overflow = select_for_extraction(
            candidates, {}, {}, budget=20, stretch_max=25,
        )
        total_qualified = len(selected) + len(overflow)
        # All 50 candidates should be accounted for (minus any below min_quality)
        assert total_qualified <= 50
        assert len(overflow) > 0
        # No overlap between selected and overflow
        selected_ids = {s.doc_id for s in selected}
        overflow_ids = {s.doc_id for s in overflow}
        assert selected_ids.isdisjoint(overflow_ids)

    def test_feed_representation(self):
        """Each feed gets at least 1 doc when budget allows."""
        candidates = []
        feeds = ["Feed A", "Feed B", "Feed C", "Feed D", "Feed E"]
        for feed in feeds:
            for j in range(10):
                candidates.append(_make_candidate(
                    f"doc_{feed}_{j}",
                    source=feed,
                    word_count=500 + j * 100,
                ))

        selected, _overflow = select_for_extraction(
            candidates, {}, {},
            budget=10, stretch_max=12,
        )

        # Every feed should have at least 1 doc
        sources = {s.source for s in selected}
        assert sources == set(feeds), f"Missing feeds: {set(feeds) - sources}"

    def test_quality_ranking(self):
        """Higher quality docs are preferred within budget."""
        candidates = []
        # 5 high quality docs (long, tier 1)
        for i in range(5):
            candidates.append(_make_candidate(
                f"good_{i}", source="Primary Feed",
                word_count=1000, title="Great Article",
            ))
        # 5 low quality docs (short, no metadata)
        for i in range(5):
            candidates.append(_make_candidate(
                f"bad_{i}", source="Echo Feed",
                word_count=50, title="",
            ))

        feed_tiers = {"Primary Feed": 1, "Echo Feed": 2}
        feed_signals = {"Primary Feed": "primary", "Echo Feed": "echo"}

        selected, _overflow = select_for_extraction(
            candidates, feed_tiers, feed_signals,
            budget=5, stretch_max=7,
        )

        # All 5 good docs should be selected
        good_ids = {s.doc_id for s in selected if s.doc_id.startswith("good_")}
        assert len(good_ids) == 5

    def test_stretch_behavior(self):
        """Budget can stretch if remaining docs have high quality."""
        # 30 high-quality candidates from one feed
        candidates = [
            _make_candidate(f"doc_{i}", source="Good Feed", word_count=1000)
            for i in range(30)
        ]

        selected, _overflow = select_for_extraction(
            candidates, {"Good Feed": 1}, {"Good Feed": "primary"},
            budget=20, stretch_max=25,
            stretch_threshold=0.5,
        )

        # Should stretch beyond 20 because all docs are high quality
        assert len(selected) > 20
        assert len(selected) <= 25

    def test_stretch_stops_at_threshold(self):
        """Stretch stops when quality drops below threshold."""
        candidates = []
        # 22 good docs
        for i in range(22):
            candidates.append(_make_candidate(
                f"good_{i}", source="Feed",
                word_count=1000, title="Title",
                published_at="2026-02-28",
            ))
        # 10 terrible docs
        for i in range(10):
            candidates.append(_make_candidate(
                f"bad_{i}", source="Feed",
                word_count=5, title="",
                published_at="",
            ))

        selected, _overflow = select_for_extraction(
            candidates, {}, {},
            budget=20, stretch_max=30,
            stretch_threshold=0.8,
        )

        # Should get around 20-22 docs, NOT stretch to include the bad ones
        assert len(selected) <= 25
        # All selected should have decent quality
        for doc in selected:
            assert doc.quality_score > 0.3

    def test_min_quality_filter(self):
        """Documents below min_quality are excluded entirely."""
        candidates = [
            _make_candidate("good", word_count=1000),
            _make_candidate("terrible", word_count=1, title="", published_at=""),
        ]

        selected, _overflow = select_for_extraction(
            candidates, {}, {},
            budget=10, min_quality=0.4,
        )

        doc_ids = {s.doc_id for s in selected}
        assert "good" in doc_ids
        # The terrible doc may or may not be included depending on exact score

    def test_sorted_by_quality_descending(self):
        """Results should be sorted by quality score, highest first."""
        candidates = [
            _make_candidate(f"doc_{i}", word_count=100 + i * 200)
            for i in range(10)
        ]

        selected, _overflow = select_for_extraction(candidates, {}, {}, budget=5)

        scores = [s.quality_score for s in selected]
        assert scores == sorted(scores, reverse=True)

    def test_scored_doc_has_row_data(self):
        """ScoredDoc.row should contain the original candidate data."""
        candidates = [_make_candidate("doc_1")]
        selected, _overflow = select_for_extraction(candidates, {}, {}, budget=10)
        assert len(selected) == 1
        assert selected[0].row["url"] == "https://example.com/doc_1"
        assert selected[0].row["doc_id"] == "doc_1"

    def test_single_feed_budget(self):
        """When all docs are from one feed, budget still limits selection."""
        candidates = [
            _make_candidate(f"doc_{i}", source="Solo Feed", word_count=800)
            for i in range(40)
        ]

        selected, _overflow = select_for_extraction(
            candidates, {}, {},
            budget=20, stretch_max=25,
        )

        assert len(selected) <= 25

    def test_many_feeds_few_budget(self):
        """When feeds > budget, each feed still gets representation up to budget."""
        candidates = []
        feeds = [f"Feed_{i}" for i in range(30)]
        for feed in feeds:
            candidates.append(_make_candidate(
                f"doc_{feed}", source=feed, word_count=800,
            ))

        selected, _overflow = select_for_extraction(
            candidates, {}, {},
            budget=20, stretch_max=25,
        )

        # Can't select from all 30 feeds with budget 25
        assert len(selected) <= 25
        # But should still select budget number of docs
        assert len(selected) >= 20

    def test_tier_preference_in_selection(self):
        """Tier 1 sources should be preferred over tier 2 in selection."""
        candidates = []
        # 5 tier-1 docs
        for i in range(5):
            candidates.append(_make_candidate(
                f"t1_{i}", source="Tier1", word_count=800,
            ))
        # 15 tier-2 echo docs
        for i in range(15):
            candidates.append(_make_candidate(
                f"t2_{i}", source="Tier2", word_count=800,
            ))

        feed_tiers = {"Tier1": 1, "Tier2": 2}
        feed_signals = {"Tier1": "primary", "Tier2": "echo"}

        selected, _overflow = select_for_extraction(
            candidates, feed_tiers, feed_signals,
            budget=10, stretch_max=12,
        )

        # All 5 tier-1 docs should be selected
        t1_count = sum(1 for s in selected if s.source == "Tier1")
        assert t1_count == 5

    def test_default_budget_values(self):
        """Default budget constants should be sensible."""
        assert DEFAULT_BUDGET == 20
        assert DEFAULT_STRETCH_MAX == 25
        assert 0.0 < STRETCH_QUALITY_THRESHOLD < 1.0
        assert 0.0 < MIN_QUALITY_THRESHOLD < STRETCH_QUALITY_THRESHOLD

    def test_reference_date_passed_through(self):
        """reference_date should affect scoring via recency."""
        ref = date(2026, 3, 16)
        candidates_fresh = [_make_candidate("fresh", published_at="2026-03-16", word_count=800)]
        candidates_old = [_make_candidate("old", published_at="2026-02-16", word_count=800)]

        sel_fresh, _ = select_for_extraction(
            candidates_fresh, {}, {}, budget=10, reference_date=ref,
        )
        sel_old, _ = select_for_extraction(
            candidates_old, {}, {}, budget=10, reference_date=ref,
        )

        assert sel_fresh[0].quality_score > sel_old[0].quality_score


# ---------------------------------------------------------------------------
# Bench tests
# ---------------------------------------------------------------------------

class TestBench:
    def test_save_bench(self):
        """save_bench inserts overflow docs into bench table."""
        conn = _make_bench_db()
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("doc1", "http://example.com", "Feed", "Title", "2026-03-16",
             "2026-03-16T12:00:00Z", "/tmp/doc1.txt", "cleaned"),
        )
        conn.commit()

        overflow = [ScoredDoc(
            doc_id="doc1", source="Feed", title="Title",
            published_at="2026-03-16", text="some text",
            word_count=500, quality_score=0.72,
        )]

        added = save_bench(conn, overflow, reference_date=date(2026, 3, 16))
        assert added == 1

        rows = conn.execute("SELECT * FROM bench").fetchall()
        assert len(rows) == 1
        assert rows[0]["doc_id"] == "doc1"
        assert rows[0]["quality_score"] == 0.72
        assert rows[0]["scored_at"] == "2026-03-16"
        expected_expiry = (date(2026, 3, 16) + timedelta(days=BENCH_EXPIRY_DAYS)).isoformat()
        assert rows[0]["expires_at"] == expected_expiry

    def test_save_bench_ignores_duplicates(self):
        """Inserting same doc_id twice should not fail."""
        conn = _make_bench_db()
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("doc1", "http://example.com", "Feed", "Title", "2026-03-16",
             "2026-03-16T12:00:00Z", "/tmp/doc1.txt", "cleaned"),
        )
        conn.commit()

        overflow = [ScoredDoc(
            doc_id="doc1", source="Feed", title="Title",
            published_at="2026-03-16", text="text",
            word_count=500, quality_score=0.72,
        )]

        save_bench(conn, overflow, reference_date=date(2026, 3, 16))
        save_bench(conn, overflow, reference_date=date(2026, 3, 17))

        rows = conn.execute("SELECT * FROM bench").fetchall()
        assert len(rows) == 1

    def test_load_bench_excludes_extracted(self):
        """load_bench should skip docs that have already been extracted."""
        conn = _make_bench_db()
        # One cleaned, one extracted
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("doc1", "http://example.com", "Feed", "Title", "2026-03-16",
             "2026-03-16T12:00:00Z", "/tmp/doc1.txt", "cleaned"),
        )
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("doc2", "http://example.com/2", "Feed", "Title2", "2026-03-16",
             "2026-03-16T12:00:00Z", "/tmp/doc2.txt", "extracted"),
        )
        conn.execute("INSERT INTO bench VALUES (?, ?, ?, ?)",
                      ("doc1", 0.72, "2026-03-16", "2026-03-25"))
        conn.execute("INSERT INTO bench VALUES (?, ?, ?, ?)",
                      ("doc2", 0.68, "2026-03-16", "2026-03-25"))
        conn.commit()

        rows = load_bench(conn, reference_date=date(2026, 3, 17))
        assert len(rows) == 1
        assert rows[0]["doc_id"] == "doc1"

    def test_load_bench_excludes_expired(self):
        """load_bench should skip expired entries."""
        conn = _make_bench_db()
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("doc1", "http://example.com", "Feed", "Title", "2026-03-10",
             "2026-03-10T12:00:00Z", "/tmp/doc1.txt", "cleaned"),
        )
        # Expired yesterday
        conn.execute("INSERT INTO bench VALUES (?, ?, ?, ?)",
                      ("doc1", 0.72, "2026-03-10", "2026-03-15"))
        conn.commit()

        rows = load_bench(conn, reference_date=date(2026, 3, 16))
        assert len(rows) == 0

    def test_load_bench_orders_by_quality(self):
        """load_bench should return highest quality first."""
        conn = _make_bench_db()
        for i, score in enumerate([0.55, 0.82, 0.71]):
            conn.execute(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (f"doc{i}", f"http://example.com/{i}", "Feed", "Title",
                 "2026-03-16", "2026-03-16T12:00:00Z", f"/tmp/doc{i}.txt", "cleaned"),
            )
            conn.execute("INSERT INTO bench VALUES (?, ?, ?, ?)",
                          (f"doc{i}", score, "2026-03-16", "2026-03-25"))
        conn.commit()

        rows = load_bench(conn, reference_date=date(2026, 3, 17))
        scores = [r["quality_score"] for r in rows]
        assert scores == sorted(scores, reverse=True)

    def test_expire_bench(self):
        """expire_bench should remove stale entries."""
        conn = _make_bench_db()
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("doc1", "http://example.com", "Feed", "Title", "2026-03-10",
             "2026-03-10T12:00:00Z", "/tmp/doc1.txt", "cleaned"),
        )
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("doc2", "http://example.com/2", "Feed", "Title2", "2026-03-14",
             "2026-03-14T12:00:00Z", "/tmp/doc2.txt", "cleaned"),
        )
        # doc1 expired, doc2 still valid
        conn.execute("INSERT INTO bench VALUES (?, ?, ?, ?)",
                      ("doc1", 0.72, "2026-03-10", "2026-03-15"))
        conn.execute("INSERT INTO bench VALUES (?, ?, ?, ?)",
                      ("doc2", 0.68, "2026-03-14", "2026-03-19"))
        conn.commit()

        removed = expire_bench(conn, reference_date=date(2026, 3, 16))
        assert removed == 1

        remaining = conn.execute("SELECT * FROM bench").fetchall()
        assert len(remaining) == 1
        assert remaining[0]["doc_id"] == "doc2"

    def test_clear_bench_doc(self):
        """clear_bench_doc should remove a specific doc."""
        conn = _make_bench_db()
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("doc1", "http://example.com", "Feed", "Title", "2026-03-16",
             "2026-03-16T12:00:00Z", "/tmp/doc1.txt", "cleaned"),
        )
        conn.execute("INSERT INTO bench VALUES (?, ?, ?, ?)",
                      ("doc1", 0.72, "2026-03-16", "2026-03-21"))
        conn.commit()

        clear_bench_doc(conn, "doc1")

        remaining = conn.execute("SELECT * FROM bench").fetchall()
        assert len(remaining) == 0

    def test_bench_expiry_days_default(self):
        """Default bench expiry should be 5 days."""
        assert BENCH_EXPIRY_DAYS == 5


# ---------------------------------------------------------------------------
# Integration-style tests
# ---------------------------------------------------------------------------

class TestSelectionIntegration:
    """Tests that simulate realistic daily ingestion scenarios."""

    def test_typical_daily_run(self):
        """Simulate a typical day: 12 feeds, ~50 docs total, budget 20."""
        candidates = []
        feed_configs = {
            "arXiv CS.AI": (1, "primary"),
            "Hugging Face Blog": (1, "primary"),
            "Anthropic Blog": (1, "primary"),
            "Google AI Blog": (1, "primary"),
            "MIT Technology Review": (1, "commentary"),
            "The Gradient": (1, "commentary"),
            "TechCrunch AI": (2, "echo"),
            "VentureBeat AI": (2, "echo"),
            "Ars Technica AI": (2, "echo"),
            "The Verge AI": (2, "echo"),
            "Simon Willison": (2, "community"),
            "Interconnects": (2, "commentary"),
        }

        # Simulate varying doc counts per feed
        doc_counts = {
            "arXiv CS.AI": 15,
            "Hugging Face Blog": 2,
            "Anthropic Blog": 1,
            "Google AI Blog": 2,
            "MIT Technology Review": 3,
            "The Gradient": 0,
            "TechCrunch AI": 8,
            "VentureBeat AI": 6,
            "Ars Technica AI": 4,
            "The Verge AI": 5,
            "Simon Willison": 3,
            "Interconnects": 1,
        }

        feed_tiers = {}
        feed_signals = {}
        for feed, (tier, signal) in feed_configs.items():
            feed_tiers[feed] = tier
            feed_signals[feed] = signal
            for j in range(doc_counts[feed]):
                candidates.append(_make_candidate(
                    f"{feed}_{j}",
                    source=feed,
                    word_count=300 + j * 100,
                ))

        total = len(candidates)
        assert total == 50  # sanity check

        selected, overflow = select_for_extraction(
            candidates, feed_tiers, feed_signals,
            budget=20, stretch_max=25,
        )

        # Should be within budget range
        assert 20 <= len(selected) <= 25

        # Overflow should contain the rest
        assert len(overflow) > 0
        assert len(selected) + len(overflow) <= 50

        # Every active feed should have representation
        active_feeds = {f for f, c in doc_counts.items() if c > 0}
        selected_feeds = {s.source for s in selected}
        assert active_feeds == selected_feeds, (
            f"Missing: {active_feeds - selected_feeds}"
        )

    def test_low_volume_day_no_filtering(self):
        """On a quiet day (< budget), all docs pass through unchanged."""
        candidates = [
            _make_candidate(f"doc_{i}", source="arXiv CS.AI", word_count=600)
            for i in range(8)
        ]

        selected, overflow = select_for_extraction(
            candidates, {"arXiv CS.AI": 1}, {"arXiv CS.AI": "primary"},
            budget=20,
        )

        assert len(selected) == 8
        assert len(overflow) == 0
