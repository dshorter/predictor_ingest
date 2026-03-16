#!/usr/bin/env python3
"""Compare quality gate results before and after normalization fixes.

Re-runs quality gates on existing extraction JSON files using the current
normalization map, showing which previously-failing docs now pass.

No API calls needed — works entirely on existing extraction data + source text.

Usage:
    PREDICTOR_DOMAIN=biosafety python scripts/compare_normalization.py \
        --extractions data/extractions/biosafety \
        --db data/db/biosafety.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from extract import normalize_extraction, evaluate_extraction


def load_source_text(db_path: Path, doc_id: str) -> str | None:
    """Load cleaned text for a document from DB."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT text_path FROM documents WHERE doc_id = ?", (doc_id,)
    ).fetchone()
    conn.close()
    if row and row["text_path"]:
        text_path = Path(row["text_path"])
        if text_path.exists():
            return text_path.read_text()
    return None


def main():
    parser = argparse.ArgumentParser(description="Compare normalization before/after")
    parser.add_argument("--extractions", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0, help="Max docs to check")
    args = parser.parse_args()

    if not args.extractions.exists():
        print(f"Not found: {args.extractions}")
        sys.exit(1)
    if not args.db.exists():
        print(f"Not found: {args.db}")
        sys.exit(1)

    files = sorted(args.extractions.glob("*.json"))
    if args.limit:
        files = files[: args.limit]

    print(f"Re-evaluating {len(files)} extractions with current normalization...\n")

    results = {"pass": 0, "escalate": 0, "error": 0}
    improved = []
    still_failing = []

    for f in files:
        try:
            raw = json.loads(f.read_text())
        except Exception:
            results["error"] += 1
            continue

        doc_id = raw.get("docId", f.stem)
        source_text = load_source_text(args.db, doc_id)

        # Apply current normalization
        normalized = normalize_extraction(raw)

        # Run quality gates
        try:
            evaluation = evaluate_extraction(normalized, source_text or "")
        except Exception as e:
            results["error"] += 1
            still_failing.append((doc_id, str(e)))
            continue

        if evaluation.get("escalate"):
            results["escalate"] += 1
            still_failing.append((doc_id, evaluation.get("decision_reason", "unknown")))
        else:
            results["pass"] += 1
            improved.append(doc_id)

    print("=" * 70)
    print("RESULTS (with current normalization + gates)")
    print("=" * 70)
    print(f"  Pass:     {results['pass']:>4}")
    print(f"  Escalate: {results['escalate']:>4}")
    print(f"  Error:    {results['error']:>4}")
    total = sum(results.values())
    if total:
        pass_rate = results["pass"] / total * 100
        print(f"\n  Pass rate: {pass_rate:.1f}% (was ~32% before fixes)")

    if still_failing:
        print(f"\nStill failing ({len(still_failing)}):")
        for doc_id, reason in still_failing[:20]:
            print(f"  {doc_id}: {reason}")

    print(
        "\nNote: Compare these numbers against the health report's 32% accept rate."
    )
    print("Improvement = new pass rate - 32%.")


if __name__ == "__main__":
    main()
