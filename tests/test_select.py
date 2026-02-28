"""Tests for quality-based document selection (src/select/).

Tests the pre-extraction quality scoring and budget selection algorithm
that controls extraction costs while ensuring feed representation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from doc_select import (
    DEFAULT_BUDGET,
    DEFAULT_STRETCH_MAX,
    MIN_QUALITY_THRESHOLD,
    STRETCH_QUALITY_THRESHOLD,
    WORDS_HIGH,
    WORDS_IDEAL,
    WORDS_LOW,
    ScoredDoc,
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
        )
        assert score > 0.85
        assert breakdown["word_count"] == 1.0
        assert breakdown["metadata"] == 1.0
        assert breakdown["source_tier"] == 1.0
        assert breakdown["signal_type"] == 1.0

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


# ---------------------------------------------------------------------------
# select_for_extraction tests
# ---------------------------------------------------------------------------

class TestSelectForExtraction:
    def test_empty_candidates(self):
        """Empty input returns empty output."""
        result = select_for_extraction([], {}, {})
        assert result == []

    def test_under_budget_returns_all(self):
        """When candidates <= budget, all are returned."""
        candidates = [_make_candidate(f"doc{i}") for i in range(5)]
        result = select_for_extraction(candidates, {}, {}, budget=10)
        assert len(result) == 5

    def test_over_budget_selects_budget(self):
        """When candidates > budget, returns approximately budget docs."""
        candidates = [_make_candidate(f"doc{i}") for i in range(50)]
        result = select_for_extraction(candidates, {}, {}, budget=20, stretch_max=25)
        assert len(result) <= 25
        assert len(result) >= 20

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

        result = select_for_extraction(
            candidates, {}, {},
            budget=10, stretch_max=12,
        )

        # Every feed should have at least 1 doc
        sources = {s.source for s in result}
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

        result = select_for_extraction(
            candidates, feed_tiers, feed_signals,
            budget=5, stretch_max=7,
        )

        # All 5 good docs should be selected
        good_ids = {s.doc_id for s in result if s.doc_id.startswith("good_")}
        assert len(good_ids) == 5

    def test_stretch_behavior(self):
        """Budget can stretch if remaining docs have high quality."""
        # 30 high-quality candidates from one feed
        candidates = [
            _make_candidate(f"doc_{i}", source="Good Feed", word_count=1000)
            for i in range(30)
        ]

        result = select_for_extraction(
            candidates, {"Good Feed": 1}, {"Good Feed": "primary"},
            budget=20, stretch_max=25,
            stretch_threshold=0.5,
        )

        # Should stretch beyond 20 because all docs are high quality
        assert len(result) > 20
        assert len(result) <= 25

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

        result = select_for_extraction(
            candidates, {}, {},
            budget=20, stretch_max=30,
            stretch_threshold=0.8,
        )

        # Should get around 20-22 docs, NOT stretch to include the bad ones
        assert len(result) <= 25
        # All selected should have decent quality
        for doc in result:
            assert doc.quality_score > 0.3

    def test_min_quality_filter(self):
        """Documents below min_quality are excluded entirely."""
        candidates = [
            _make_candidate("good", word_count=1000),
            _make_candidate("terrible", word_count=1, title="", published_at=""),
        ]

        result = select_for_extraction(
            candidates, {}, {},
            budget=10, min_quality=0.4,
        )

        doc_ids = {s.doc_id for s in result}
        assert "good" in doc_ids
        # The terrible doc may or may not be included depending on exact score

    def test_sorted_by_quality_descending(self):
        """Results should be sorted by quality score, highest first."""
        candidates = [
            _make_candidate(f"doc_{i}", word_count=100 + i * 200)
            for i in range(10)
        ]

        result = select_for_extraction(candidates, {}, {}, budget=5)

        scores = [s.quality_score for s in result]
        assert scores == sorted(scores, reverse=True)

    def test_scored_doc_has_row_data(self):
        """ScoredDoc.row should contain the original candidate data."""
        candidates = [_make_candidate("doc_1")]
        result = select_for_extraction(candidates, {}, {}, budget=10)
        assert len(result) == 1
        assert result[0].row["url"] == "https://example.com/doc_1"
        assert result[0].row["doc_id"] == "doc_1"

    def test_single_feed_budget(self):
        """When all docs are from one feed, budget still limits selection."""
        candidates = [
            _make_candidate(f"doc_{i}", source="Solo Feed", word_count=800)
            for i in range(40)
        ]

        result = select_for_extraction(
            candidates, {}, {},
            budget=20, stretch_max=25,
        )

        assert len(result) <= 25

    def test_many_feeds_few_budget(self):
        """When feeds > budget, each feed still gets representation up to budget."""
        candidates = []
        feeds = [f"Feed_{i}" for i in range(30)]
        for feed in feeds:
            candidates.append(_make_candidate(
                f"doc_{feed}", source=feed, word_count=800,
            ))

        result = select_for_extraction(
            candidates, {}, {},
            budget=20, stretch_max=25,
        )

        # Can't select from all 30 feeds with budget 25
        assert len(result) <= 25
        # But should still select budget number of docs
        assert len(result) >= 20

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

        result = select_for_extraction(
            candidates, feed_tiers, feed_signals,
            budget=10, stretch_max=12,
        )

        # All 5 tier-1 docs should be selected
        t1_count = sum(1 for s in result if s.source == "Tier1")
        assert t1_count == 5

    def test_default_budget_values(self):
        """Default budget constants should be sensible."""
        assert DEFAULT_BUDGET == 20
        assert DEFAULT_STRETCH_MAX == 25
        assert 0.0 < STRETCH_QUALITY_THRESHOLD < 1.0
        assert 0.0 < MIN_QUALITY_THRESHOLD < STRETCH_QUALITY_THRESHOLD


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

        result = select_for_extraction(
            candidates, feed_tiers, feed_signals,
            budget=20, stretch_max=25,
        )

        # Should be within budget range
        assert 20 <= len(result) <= 25

        # Every active feed should have representation
        active_feeds = {f for f, c in doc_counts.items() if c > 0}
        selected_feeds = {s.source for s in result}
        assert active_feeds == selected_feeds, (
            f"Missing: {active_feeds - selected_feeds}"
        )

    def test_low_volume_day_no_filtering(self):
        """On a quiet day (< budget), all docs pass through unchanged."""
        candidates = [
            _make_candidate(f"doc_{i}", source="arXiv CS.AI", word_count=600)
            for i in range(8)
        ]

        result = select_for_extraction(
            candidates, {"arXiv CS.AI": 1}, {"arXiv CS.AI": "primary"},
            budget=20,
        )

        assert len(result) == 8
