"""Quality-based document selection for extraction budget control.

When daily ingestion produces more documents than the extraction budget
allows, this module selects which documents to extract based on:

1. Pre-extraction quality signals (word count, metadata completeness,
   source tier, recency) — all CPU-based, zero LLM cost.
2. Fair representation across feeds — every feed gets at least one slot
   (if it has a qualifying document).
3. A configurable budget with stretch — base budget (e.g. 20) can expand
   to a stretch max (e.g. 25) if remaining candidates score well.
4. A "bench" for qualified-but-budget-blocked articles that can backfill
   on light days.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_BUDGET: int = 20
DEFAULT_STRETCH_MAX: int = 25
STRETCH_QUALITY_THRESHOLD: float = 0.55
MIN_QUALITY_THRESHOLD: float = 0.20

# Bench: qualified-but-budget-blocked articles can backfill on light days.
# Articles expire from the bench after this many days.
BENCH_EXPIRY_DAYS: int = 5

# Word count sweet spot for quality scoring.
# Articles below WORDS_LOW are penalised; above WORDS_HIGH get diminishing
# returns (very long articles aren't necessarily better for extraction).
WORDS_LOW: int = 200
WORDS_IDEAL: int = 800
WORDS_HIGH: int = 3000

# Signal-type weights (higher = more valuable for extraction)
SIGNAL_WEIGHTS: dict[str, float] = {
    "primary": 1.0,
    "commentary": 0.8,
    "community": 0.6,
    "echo": 0.4,
}


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------

@dataclass
class ScoredDoc:
    """A document candidate with its computed quality score."""

    doc_id: str
    source: str
    title: Optional[str]
    published_at: Optional[str]
    text: str
    word_count: int
    quality_score: float
    score_breakdown: dict[str, float] = field(default_factory=dict)
    # Original row data for passthrough to docpack
    row: dict[str, Any] = field(default_factory=dict)


def _word_count(text: str) -> int:
    """Count words in cleaned text."""
    return len(text.split())


def _word_count_score(wc: int) -> float:
    """Score based on word count.

    - < WORDS_LOW: linear ramp from 0 to 0.5
    - WORDS_LOW .. WORDS_IDEAL: linear ramp from 0.5 to 1.0
    - WORDS_IDEAL .. WORDS_HIGH: stays at 1.0
    - > WORDS_HIGH: gentle log decay (never below 0.7)
    """
    if wc <= 0:
        return 0.0
    if wc < WORDS_LOW:
        return 0.5 * (wc / WORDS_LOW)
    if wc <= WORDS_IDEAL:
        return 0.5 + 0.5 * ((wc - WORDS_LOW) / (WORDS_IDEAL - WORDS_LOW))
    if wc <= WORDS_HIGH:
        return 1.0
    # Gentle decay for very long articles
    overshoot = (wc - WORDS_HIGH) / WORDS_HIGH
    return max(0.7, 1.0 - 0.1 * math.log1p(overshoot))


def _metadata_score(title: Optional[str], published_at: Optional[str]) -> float:
    """Score based on metadata completeness.

    - Has non-empty title: +0.5
    - Has published date:  +0.5
    """
    score = 0.0
    if title and title.strip():
        score += 0.5
    if published_at and published_at.strip():
        score += 0.5
    return score


def _source_tier_score(tier: int) -> float:
    """Score based on source tier (1=primary, 2=secondary, 3=echo)."""
    if tier <= 1:
        return 1.0
    if tier == 2:
        return 0.6
    return 0.3


def _signal_type_score(signal: str) -> float:
    """Score based on signal type from feed config."""
    return SIGNAL_WEIGHTS.get(signal, 0.5)


def _recency_score(published_at: Optional[str], reference_date: Optional[date] = None) -> float:
    """Score based on article age relative to reference date.

    - 0-3 days old: 1.0 (full credit)
    - 3-7 days old: linear decay from 1.0 to 0.5
    - 7-14 days old: linear decay from 0.5 to 0.3
    - 14+ days old: 0.3 (floor)
    - No published_at: 0.4 (modest penalty — we can't tell)
    """
    if not published_at or not published_at.strip():
        return 0.4

    ref = reference_date or date.today()

    try:
        # Handle both "YYYY-MM-DD" and "YYYY-MM-DDTHH:MM:SS..." formats
        pub_str = published_at.strip()[:10]
        pub_date = date.fromisoformat(pub_str)
    except (ValueError, IndexError):
        return 0.4

    age_days = (ref - pub_date).days

    if age_days < 0:
        # Future date (clock skew or pre-publication) — treat as fresh
        return 1.0
    if age_days <= 3:
        return 1.0
    if age_days <= 7:
        # Linear decay from 1.0 to 0.5 over days 3-7
        return 1.0 - 0.5 * ((age_days - 3) / 4)
    if age_days <= 14:
        # Linear decay from 0.5 to 0.3 over days 7-14
        return 0.5 - 0.2 * ((age_days - 7) / 7)
    return 0.3


def score_document(
    text: str,
    title: Optional[str] = None,
    published_at: Optional[str] = None,
    tier: int = 1,
    signal: str = "primary",
    reference_date: Optional[date] = None,
) -> tuple[float, dict[str, float]]:
    """Compute pre-extraction quality score for a document.

    All signals are CPU-based (zero LLM cost). The score is a weighted
    combination of:

    - word_count  (30%): article length in the extractable sweet spot
    - metadata    (20%): title + published date presence
    - source_tier (20%): tier 1 sources are higher priority
    - signal_type (15%): primary > commentary > echo
    - recency     (15%): newer articles are more valuable for trend detection

    Args:
        text: Cleaned article text
        title: Article title (may be None)
        published_at: Publication date string (may be None)
        tier: Feed tier (1, 2, or 3)
        signal: Feed signal type
        reference_date: Date to compute recency against (default: today)

    Returns:
        Tuple of (combined_score, breakdown_dict) where combined_score
        is 0.0-1.0 and breakdown contains individual component scores.
    """
    wc = _word_count(text)
    wc_score = _word_count_score(wc)
    meta_score = _metadata_score(title, published_at)
    tier_score = _source_tier_score(tier)
    sig_score = _signal_type_score(signal)
    rec_score = _recency_score(published_at, reference_date)

    combined = (
        0.30 * wc_score
        + 0.20 * meta_score
        + 0.20 * tier_score
        + 0.15 * sig_score
        + 0.15 * rec_score
    )

    breakdown = {
        "word_count": wc_score,
        "metadata": meta_score,
        "source_tier": tier_score,
        "signal_type": sig_score,
        "recency": rec_score,
        "word_count_raw": wc,
    }

    return combined, breakdown


# ---------------------------------------------------------------------------
# Selection algorithm
# ---------------------------------------------------------------------------

def select_for_extraction(
    candidates: list[dict[str, Any]],
    feed_tiers: dict[str, int],
    feed_signals: dict[str, str],
    budget: int = DEFAULT_BUDGET,
    stretch_max: int = DEFAULT_STRETCH_MAX,
    min_per_feed: int = 1,
    stretch_threshold: float = STRETCH_QUALITY_THRESHOLD,
    min_quality: float = MIN_QUALITY_THRESHOLD,
    reference_date: Optional[date] = None,
) -> list[ScoredDoc]:
    """Select documents for extraction with feed representation and quality.

    Algorithm:
    1. Score every candidate.
    2. Drop candidates below min_quality.
    3. Guarantee min_per_feed from each feed (highest-scoring doc per feed).
    4. Fill remaining budget slots from the global quality ranking.
    5. If docs ranked budget+1..stretch_max score above stretch_threshold,
       include them (stretch behaviour).

    Args:
        candidates: List of doc dicts with keys: doc_id, source, title,
                    published_at, text. Extra keys preserved in row.
        feed_tiers: Mapping of source name -> tier (default 1 if missing)
        feed_signals: Mapping of source name -> signal type (default "primary")
        budget: Base number of documents to select
        stretch_max: Maximum docs if stretch quality is met
        min_per_feed: Minimum docs per feed (if available above min_quality)
        stretch_threshold: Quality score above which stretch docs are included
        min_quality: Minimum quality score to be considered at all
        reference_date: Date to compute recency against (default: today)

    Returns:
        List of ScoredDoc objects, sorted by quality_score descending.
        Length will be between 0 and stretch_max.
    """
    if not candidates:
        return [], []

    # Step 1: Score all candidates
    scored: list[ScoredDoc] = []
    for doc in candidates:
        text = doc.get("text", "")
        source = doc.get("source", "")
        tier = feed_tiers.get(source, 1)
        signal = feed_signals.get(source, "primary")

        quality, breakdown = score_document(
            text=text,
            title=doc.get("title"),
            published_at=doc.get("published_at"),
            tier=tier,
            signal=signal,
            reference_date=reference_date,
        )

        scored.append(ScoredDoc(
            doc_id=doc.get("doc_id", ""),
            source=source,
            title=doc.get("title"),
            published_at=doc.get("published_at"),
            text=text,
            word_count=breakdown["word_count_raw"],
            quality_score=quality,
            score_breakdown=breakdown,
            row=doc,
        ))

    # Step 2: Drop below min_quality
    scored = [s for s in scored if s.quality_score >= min_quality]

    if not scored:
        return [], []

    # If total candidates fit within budget, return all
    if len(scored) <= budget:
        scored.sort(key=lambda s: s.quality_score, reverse=True)
        return scored, []

    # Step 3: Guarantee representation — best doc per feed
    by_feed: dict[str, list[ScoredDoc]] = {}
    for s in scored:
        by_feed.setdefault(s.source, []).append(s)

    # Sort each feed's docs by quality (best first)
    for feed_docs in by_feed.values():
        feed_docs.sort(key=lambda s: s.quality_score, reverse=True)

    selected_ids: set[str] = set()
    selected: list[ScoredDoc] = []

    # Collect the best doc from each feed, then pick the top ones if
    # there are more feeds than budget allows.
    feed_reps: list[ScoredDoc] = []
    for feed, feed_docs in by_feed.items():
        for doc in feed_docs[:min_per_feed]:
            feed_reps.append(doc)

    # If feed representation alone exceeds stretch_max, take only the
    # best-scoring representatives up to stretch_max.
    if len(feed_reps) > stretch_max:
        feed_reps.sort(key=lambda s: s.quality_score, reverse=True)
        feed_reps = feed_reps[:stretch_max]

    for doc in feed_reps:
        if doc.doc_id not in selected_ids:
            selected.append(doc)
            selected_ids.add(doc.doc_id)

    # Step 4: Fill remaining budget from global ranking
    remaining_budget = budget - len(selected)
    if remaining_budget > 0:
        # Global ranking excluding already-selected
        pool = sorted(
            [s for s in scored if s.doc_id not in selected_ids],
            key=lambda s: s.quality_score,
            reverse=True,
        )
        for doc in pool[:remaining_budget]:
            selected.append(doc)
            selected_ids.add(doc.doc_id)

    # Step 5: Stretch — include additional high-quality docs up to stretch_max
    if len(selected) >= budget and stretch_max > budget:
        stretch_slots = stretch_max - len(selected)
        if stretch_slots > 0:
            stretch_pool = sorted(
                [s for s in scored if s.doc_id not in selected_ids],
                key=lambda s: s.quality_score,
                reverse=True,
            )
            for doc in stretch_pool[:stretch_slots]:
                if doc.quality_score >= stretch_threshold:
                    selected.append(doc)
                    selected_ids.add(doc.doc_id)
                else:
                    break  # Pool is sorted; once below threshold, stop

    # Sort final selection by quality descending
    selected.sort(key=lambda s: s.quality_score, reverse=True)

    # Identify bench-worthy overflow: qualified docs that didn't make the cut
    overflow = [
        s for s in scored
        if s.doc_id not in selected_ids and s.quality_score >= min_quality
    ]
    overflow.sort(key=lambda s: s.quality_score, reverse=True)

    return selected, overflow


# ---------------------------------------------------------------------------
# Bench management
# ---------------------------------------------------------------------------

def save_bench(
    conn: Any,
    overflow: list[ScoredDoc],
    reference_date: Optional[date] = None,
    expiry_days: int = BENCH_EXPIRY_DAYS,
) -> int:
    """Save qualified-but-budget-blocked docs to the bench table.

    Args:
        conn: SQLite connection
        overflow: ScoredDoc objects that qualified but were not selected
        reference_date: Date these docs were scored (default: today)
        expiry_days: Days until bench entries expire

    Returns:
        Number of docs added to bench
    """
    if not overflow:
        return 0

    ref = reference_date or date.today()
    expires = (ref + timedelta(days=expiry_days)).isoformat()
    scored_at = ref.isoformat()

    added = 0
    for doc in overflow:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO bench
                   (doc_id, quality_score, scored_at, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (doc.doc_id, doc.quality_score, scored_at, expires),
            )
            added += 1
        except Exception:
            pass  # duplicate or constraint error — skip silently

    conn.commit()
    return added


def load_bench(
    conn: Any,
    reference_date: Optional[date] = None,
    limit: int = DEFAULT_BUDGET,
) -> list[dict[str, Any]]:
    """Load unexpired, unextracted bench docs for backfill.

    Returns docs ordered by quality_score descending, excluding any that
    have already been extracted (status != 'cleaned').

    Args:
        conn: SQLite connection
        reference_date: Current date for expiry check (default: today)
        limit: Maximum bench docs to return

    Returns:
        List of document dicts ready for docpack building.
    """
    ref = (reference_date or date.today()).isoformat()

    rows = conn.execute(
        """SELECT d.doc_id, d.url, d.source, d.title, d.published_at,
                  d.fetched_at, d.text_path, b.quality_score
           FROM bench b
           JOIN documents d ON b.doc_id = d.doc_id
           WHERE b.expires_at > ?
             AND d.status = 'cleaned'
             AND d.text_path IS NOT NULL
           ORDER BY b.quality_score DESC
           LIMIT ?""",
        (ref, limit),
    ).fetchall()

    return [dict(r) for r in rows]


def expire_bench(conn: Any, reference_date: Optional[date] = None) -> int:
    """Remove expired entries from the bench.

    Args:
        conn: SQLite connection
        reference_date: Current date for expiry check (default: today)

    Returns:
        Number of rows removed.
    """
    ref = (reference_date or date.today()).isoformat()
    cursor = conn.execute("DELETE FROM bench WHERE expires_at <= ?", (ref,))
    conn.commit()
    return cursor.rowcount


def clear_bench_doc(conn: Any, doc_id: str) -> None:
    """Remove a specific doc from the bench (e.g. after it's been extracted).

    Args:
        conn: SQLite connection
        doc_id: Document to remove from bench
    """
    conn.execute("DELETE FROM bench WHERE doc_id = ?", (doc_id,))
    conn.commit()
