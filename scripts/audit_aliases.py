"""Diagnostic: flag entity_aliases rows that likely misroute resolution.

The alias table is consulted FIRST during entity resolution, before any
name or fuzzy matching, with no type filter — so a bad row silently
steers every future mention of that alias into the wrong node. This
audit scores each alias against its target entity's name and known
aliases and prints the rows worth a human look, worst first.

Run on VPS:
    python scripts/audit_aliases.py                    # active domain
    python scripts/audit_aliases.py --domain film
    python scripts/audit_aliases.py --domain film --threshold 0.7

A low similarity score is a heuristic, not a verdict: legitimate rows
can score low (acronyms, renames, ticker symbols). Review before
deleting or retargeting, and back up first:
    sqlite3 data/db/<slug>.db ".mode insert entity_aliases" \
        "SELECT * FROM entity_aliases;" > diagnostics/alias-backup.sql
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from resolve import name_similarity
from util.paths import get_db_path


def audit(conn: sqlite3.Connection, threshold: float) -> list[dict]:
    """Return alias rows whose best similarity to their target is below threshold."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT ea.alias,
               ea.canonical_id,
               e.name    AS target_name,
               e.aliases AS target_aliases,
               (SELECT COUNT(*) FROM relations r
                WHERE r.source_id = ea.canonical_id
                   OR r.target_id = ea.canonical_id) AS target_degree
        FROM entity_aliases ea
        LEFT JOIN entities e ON e.entity_id = ea.canonical_id
        """
    ).fetchall()

    suspects = []
    for row in rows:
        if row["target_name"] is None:
            # Dangling: target entity no longer exists
            suspects.append({
                "alias": row["alias"],
                "canonical_id": row["canonical_id"],
                "target_name": None,
                "similarity": 0.0,
                "target_degree": 0,
                "reason": "dangling target",
            })
            continue

        sim = name_similarity(row["alias"], row["target_name"])
        for known in json.loads(row["target_aliases"] or "[]"):
            sim = max(sim, name_similarity(row["alias"], known))

        if sim < threshold:
            suspects.append({
                "alias": row["alias"],
                "canonical_id": row["canonical_id"],
                "target_name": row["target_name"],
                "similarity": sim,
                "target_degree": row["target_degree"],
                "reason": "low similarity",
            })

    suspects.sort(key=lambda s: s["similarity"])
    return suspects


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--domain", default=None, help="Domain slug (default: active domain)")
    parser.add_argument(
        "--threshold", type=float, default=0.6,
        help="Flag rows whose best alias↔target similarity is below this (default 0.6)",
    )
    args = parser.parse_args()

    db_path = get_db_path(args.domain)
    if not Path(db_path).exists():
        print(f"No database at {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    total = conn.execute("SELECT COUNT(*) FROM entity_aliases").fetchone()[0]
    suspects = audit(conn, args.threshold)
    conn.close()

    print(f"{db_path}: {total} alias rows, {len(suspects)} suspect (threshold {args.threshold})\n")
    if suspects:
        width = max(len(s["alias"]) for s in suspects)
        for s in suspects:
            target = s["target_name"] or "<MISSING ENTITY>"
            print(
                f"  {s['similarity']:.2f}  {s['alias']:<{width}}  ->  "
                f"{s['canonical_id']}  ({target}, degree {s['target_degree']})"
            )

    return 0


if __name__ == "__main__":
    main()
