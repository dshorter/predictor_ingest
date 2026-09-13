"""score_all (set-based) must agree with score_entity (per-entity) exactly.

TREND-0. `score_all` used to loop `score_entity`, costing nine queries per
entity; at 34,043 film entities that is ~300,000 round trips, and film crossed
the 600s `trending` stage timeout on 2026-08-06. Movers output was frozen for 38
days while `run_movers.py` re-served the last good snapshot and exited 0.
Semiconductors hit the same wall 2026-09-06.

`score_entity` was left untouched precisely so it can serve as the oracle here.
These tests are the entire safety argument for the rewrite: if the two
implementations ever disagree, the fast one is wrong.

Coverage is deliberately edge-first, because the risky part of a GROUP BY
rewrite is the rows GROUP BY does not return.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from trend import TrendScorer, _BASE_RELATION, _TREND_WEIGHTS

AS_OF = date(2026, 9, 13)


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE entities (
            entity_id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT,
            first_seen TEXT
        );
        CREATE TABLE documents (
            doc_id TEXT PRIMARY KEY,
            published_at TEXT
        );
        CREATE TABLE relations (
            relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT,
            rel TEXT,
            target_id TEXT,
            doc_id TEXT
        );
        """
    )


def _doc(conn: sqlite3.Connection, doc_id: str, days_ago: int | None) -> None:
    """A document published days_ago before AS_OF; None means NULL published_at."""
    published = None if days_ago is None else (AS_OF - timedelta(days=days_ago)).isoformat()
    conn.execute("INSERT INTO documents (doc_id, published_at) VALUES (?, ?)", (doc_id, published))


def _mention(conn: sqlite3.Connection, entity_id: str, doc_id: str) -> None:
    conn.execute(
        "INSERT INTO relations (source_id, rel, target_id, doc_id) VALUES (?, ?, ?, ?)",
        (f"doc:{doc_id}", _BASE_RELATION, entity_id, doc_id),
    )


def _edge(conn: sqlite3.Connection, src: str, dst: str, rel: str = "PARTNERS_WITH") -> None:
    conn.execute(
        "INSERT INTO relations (source_id, rel, target_id, doc_id) VALUES (?, ?, ?, NULL)",
        (src, rel, dst),
    )


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """A fixture built to hit every branch the rewrite could get wrong."""
    c = sqlite3.connect(":memory:")
    _schema(c)

    gate = int(_TREND_WEIGHTS.get("min_mentions_for_velocity", 3))

    entities = [
        ("e:silent", "Silent", "ORG", "2026-01-01"),      # no mentions, no edges at all
        ("e:gated", "Gated", "ORG", "2026-08-01"),        # mentions below the velocity gate
        ("e:new", "New", "ORG", AS_OF.isoformat()),       # previous window empty -> cap path
        ("e:steady", "Steady", "ORG", "2026-02-01"),      # mentions in both windows -> ratio
        ("e:declining", "Declining", "ORG", "2026-03-01"),# previous > recent
        ("e:nofirstseen", "NoFirstSeen", "ORG", None),    # NULL first_seen -> novelty 0.5
        ("e:badfirstseen", "BadDate", "ORG", "not-a-date"),  # unparseable -> novelty 0.5
        ("e:boundary", "Boundary", "ORG", "2026-04-01"),  # published exactly on as_of-7
        ("e:nulldoc", "NullDoc", "ORG", "2026-05-01"),    # mentioned only by a NULL-dated doc
        ("e:bridge", "Bridge", "ORG", "2026-06-01"),      # edges but no mentions
        ("e:old", "Old", "ORG", "2024-01-01"),            # outside max_age_days
    ]
    for eid, name, typ, first_seen in entities:
        c.execute(
            "INSERT INTO entities (entity_id, name, type, first_seen) VALUES (?, ?, ?, ?)",
            (eid, name, typ, first_seen),
        )

    # documents across the window boundaries that matter
    _doc(c, "d:today", 0)
    _doc(c, "d:recent", 3)
    _doc(c, "d:boundary", 7)     # in BOTH the recent and previous 7d windows
    _doc(c, "d:prev", 10)
    _doc(c, "d:month", 20)
    _doc(c, "d:ancient", 400)    # outside max_age_days (365)
    _doc(c, "d:null", None)      # NULL published_at -> matches no window

    # gated: enough to be nonzero, fewer than the gate
    for i in range(max(1, gate - 1)):
        _mention(c, "e:gated", "d:recent")

    # new: recent only, nothing in the previous window
    for _ in range(4):
        _mention(c, "e:new", "d:today")

    # steady: both windows populated
    for _ in range(6):
        _mention(c, "e:steady", "d:recent")
    for _ in range(3):
        _mention(c, "e:steady", "d:prev")
    _mention(c, "e:steady", "d:month")

    # declining: previous heavier than recent
    for _ in range(2):
        _mention(c, "e:declining", "d:recent")
    for _ in range(8):
        _mention(c, "e:declining", "d:prev")

    # boundary: only the as_of-7 document
    for _ in range(3):
        _mention(c, "e:boundary", "d:boundary")

    # nulldoc: only a NULL-dated document
    for _ in range(5):
        _mention(c, "e:nulldoc", "d:null")

    # old: only outside the age window
    for _ in range(3):
        _mention(c, "e:old", "d:ancient")

    # bridge degrees, including a self-referencing pair and an isolated target
    _edge(c, "e:bridge", "e:steady")
    _edge(c, "e:bridge", "e:new")
    _edge(c, "e:bridge", "e:gated")
    _edge(c, "e:steady", "e:bridge")
    _edge(c, "e:declining", "e:bridge")
    # a duplicate edge: COUNT(DISTINCT) must not double-count it
    _edge(c, "e:bridge", "e:steady")
    # a NULL rel — excluded by `rel != ?` in both implementations
    c.execute(
        "INSERT INTO relations (source_id, rel, target_id, doc_id) VALUES (?, NULL, ?, NULL)",
        ("e:bridge", "e:old"),
    )

    c.commit()
    return c


def _reference(conn: sqlite3.Connection) -> dict[str, dict]:
    """The oracle: what the old implementation produced, per entity."""
    scorer = TrendScorer(conn)
    ids = [r[0] for r in conn.execute("SELECT entity_id FROM entities").fetchall()]
    return {eid: scorer.score_entity(eid) for eid in ids}


def test_every_entity_is_present(conn):
    """The rows GROUP BY omits are the rewrite's main hazard."""
    fast = TrendScorer(conn).score_all(as_of=AS_OF)
    expected = {r[0] for r in conn.execute("SELECT entity_id FROM entities")}
    assert set(fast) == expected
    assert "e:silent" in fast, "an entity with no mentions and no edges must still be scored"


def test_matches_reference_exactly(conn, monkeypatch):
    """Field-by-field equality against score_entity for every entity."""
    # score_entity's helpers default as_of to date.today(); pin it so the
    # comparison is against the same reference date, not the wall clock.
    import trend as trend_mod

    class _FixedDate(date):
        @classmethod
        def today(cls):
            return AS_OF

    monkeypatch.setattr(trend_mod, "date", _FixedDate)

    reference = _reference(conn)
    fast = TrendScorer(conn).score_all(as_of=AS_OF)

    assert set(fast) == set(reference)
    for eid in sorted(reference):
        for field in (
            "entity_id",
            "mention_count_7d",
            "mention_count_30d",
            "velocity",
            "velocity_gated",
            "novelty",
            "bridge_score",
        ):
            exp, got = reference[eid][field], fast[eid][field]
            if isinstance(exp, float):
                assert got == pytest.approx(exp, rel=1e-12, abs=1e-12), (
                    f"{eid}.{field}: reference={exp} set-based={got}"
                )
            else:
                assert got == exp, f"{eid}.{field}: reference={exp} set-based={got}"


def test_zero_mention_entities_default_to_zero(conn):
    fast = TrendScorer(conn).score_all(as_of=AS_OF)
    silent = fast["e:silent"]
    assert silent["mention_count_7d"] == 0
    assert silent["mention_count_30d"] == 0
    assert silent["velocity"] == 0.0, "no mentions in either window is 0.0, not 1.0 or a ratio"
    assert silent["velocity_gated"] == 0
    assert silent["bridge_score"] == 0.0


def test_null_published_at_matches_no_window(conn):
    """A NULL-dated document must not count toward any window."""
    fast = TrendScorer(conn).score_all(as_of=AS_OF)
    assert fast["e:nulldoc"]["mention_count_7d"] == 0
    assert fast["e:nulldoc"]["mention_count_30d"] == 0


def test_unparseable_first_seen_is_medium_novelty(conn):
    fast = TrendScorer(conn).score_all(as_of=AS_OF)
    assert fast["e:nofirstseen"]["novelty"] == 0.5
    assert fast["e:badfirstseen"]["novelty"] == 0.5


def test_velocity_gate_is_reported(conn):
    gate = int(_TREND_WEIGHTS.get("min_mentions_for_velocity", 3))
    fast = TrendScorer(conn).score_all(as_of=AS_OF)
    gated = fast["e:gated"]
    if gate > 1:
        assert gated["velocity"] == 1.0
        assert gated["velocity_gated"] == 1
    # and an entity above the gate is never marked gated
    assert fast["e:steady"]["velocity_gated"] == 0


def test_distinct_neighbours_not_double_counted(conn):
    """e:bridge has a duplicate edge to e:steady; DISTINCT must collapse it."""
    fast = TrendScorer(conn).score_all(as_of=AS_OF)
    reference = _reference(conn)
    assert fast["e:bridge"]["bridge_score"] == pytest.approx(
        reference["e:bridge"]["bridge_score"], rel=1e-12
    )


def test_as_of_is_pinned_not_per_call(conn):
    """Two runs with the same explicit as_of must be identical."""
    scorer = TrendScorer(conn)
    assert scorer.score_all(as_of=AS_OF) == scorer.score_all(as_of=AS_OF)


def test_query_count_is_constant_in_entity_count(conn):
    """The point of the rewrite: queries must not scale with entities."""
    # sqlite3.Connection is an immutable C type, so its methods cannot be
    # patched; set_trace_callback fires once per statement actually executed,
    # which is a truer count anyway.
    counted = {"n": 0}

    def trace(_statement: str) -> None:
        counted["n"] += 1

    conn.set_trace_callback(trace)
    try:
        TrendScorer(conn).score_all(as_of=AS_OF)
    finally:
        conn.set_trace_callback(None)

    n_entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    assert n_entities >= 10, "fixture too small for this assertion to mean anything"
    assert counted["n"] <= 10, (
        f"score_all issued {counted['n']} queries for {n_entities} entities — "
        "it must be a constant, not per-entity"
    )
