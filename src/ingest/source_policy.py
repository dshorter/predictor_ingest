"""Source-type extraction policy — which document sources are worth extracting.

Some source types (Bluesky posts, Reddit comments) have document units that
are too short / low-density for LLM extraction to yield useful relations.
SRC-5 in `docs/backlog.md` documents the canonical case: Bluesky SE Film
produces 0.7 relations/doc vs the source average of ~14.

This module defines a registry mapping `source_type` → whether docs of that
type should enter the extraction budget. Sources marked `extract: false`
are still ingested (so they contribute to mention counts and the Movers
velocity signal) but skip extraction entirely, saving LLM tokens.

The policy is tied to `source_type`, not individual feeds — adding a new
Bluesky or Reddit feed inherits the right behaviour automatically.

See `docs/plans/movers-and-focus-mode.md` §"Chatter source types" for the
design rationale.
"""

from __future__ import annotations


# Registry: source_type → policy.
#
# `extract: True`  — docs go through doc_select scoring and may be queued
#                    for LLM extraction.
# `extract: False` — docs are ingested for mention counting but never queued
#                    for extraction. Token cost is zero for these sources.
#
# Unknown source_types default to extract=True (conservative — assume new
# integrations want extraction unless explicitly opted out).
_POLICY: dict[str, dict[str, bool]] = {
    "rss":      {"extract": True},
    "atom":     {"extract": True},
    "substack": {"extract": True},   # substack feeds are long-form articles
    "edgar":    {"extract": True},   # SEC filings — long, structured
    "patents":  {"extract": True},   # USPTO patent abstracts — content-dense
    "bluesky":  {"extract": False},  # short posts, low extraction yield (SRC-5)
    "reddit":   {"extract": False},  # mostly short comments, low extraction yield
}


def should_extract(source_type: str | None) -> bool:
    """Return True if docs of this source_type should be queued for extraction.

    Unknown / missing source_types default to True (extracting). Callers
    should pass the raw `documents.source_type` column value; case is
    normalised internally.
    """
    if not source_type:
        return True
    return _POLICY.get(source_type.lower(), {"extract": True})["extract"]


def extracting_source_types() -> list[str]:
    """Return the source_type values that DO go through extraction.

    Useful for building SQL `IN (...)` clauses that filter the candidate
    set to extraction-eligible documents only.
    """
    return sorted(st for st, p in _POLICY.items() if p["extract"])


def non_extracting_source_types() -> list[str]:
    """Return the source_type values that DO NOT go through extraction."""
    return sorted(st for st, p in _POLICY.items() if not p["extract"])


def registered_source_types() -> list[str]:
    """Return all source_types with an explicit policy entry."""
    return sorted(_POLICY.keys())
