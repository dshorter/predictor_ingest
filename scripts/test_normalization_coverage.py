#!/usr/bin/env python3
"""Test normalization coverage against existing extraction data.

Reads all extraction JSON files and checks:
1. Which relation types would have been caught by the normalization map
2. Which date resolutions would have been caught
3. What remains uncovered (still fails validation)

Usage:
    PREDICTOR_DOMAIN=biosafety python scripts/test_normalization_coverage.py
    PREDICTOR_DOMAIN=biosafety python scripts/test_normalization_coverage.py --dir data/extractions/biosafety
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Add src/ to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import get_active_profile
from extract import (
    RELATION_NORMALIZATION,
    RELATION_TYPES,
    normalize_extraction,
)

# Load schema enum for date resolution
VALID_DATE_RESOLUTIONS = {"exact", "range", "anchored_to_published", "unknown", None}

# Date resolution map from extract module
_DATE_RESOLUTION_MAP = {
    "day": "exact",
    "daily": "exact",
    "month": "exact",
    "year": "exact",
    "weekly": "range",
    "week": "range",
    "season": "range",
    "decade": "range",
    "duration": "range",
    "period": "range",
    "quarterly": "range",
    "annual": "range",
    "approximate": "unknown",
}


def analyze_extractions(extraction_dir: Path) -> None:
    """Analyze all extraction JSON files for normalization coverage."""
    files = sorted(extraction_dir.glob("*.json"))
    if not files:
        print(f"No extraction JSON files found in {extraction_dir}")
        return

    print(f"Analyzing {len(files)} extraction files in {extraction_dir}\n")

    # Counters
    rel_canonical = Counter()      # Already canonical
    rel_normalized = Counter()     # Would be normalized by map
    rel_unknown = Counter()        # Not in canonical or normalization map
    date_canonical = Counter()     # Already valid
    date_normalized = Counter()    # Would be normalized
    date_unknown = Counter()       # Not handled
    orphan_docs = 0
    total_relations = 0
    total_dates = 0
    files_with_issues = []

    for f in files:
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, Exception) as e:
            print(f"  SKIP {f.name}: {e}")
            continue

        doc_issues = []
        entities_names = {e.get("name") for e in data.get("entities", [])}

        # Check relations
        for rel_obj in data.get("relations", []):
            total_relations += 1
            rel = rel_obj.get("rel", "").upper()

            if rel in [r.upper() for r in RELATION_TYPES]:
                rel_canonical[rel] += 1
            elif rel in RELATION_NORMALIZATION:
                rel_normalized[rel] += 1
            elif rel.replace("-", "_").replace(" ", "_") in RELATION_NORMALIZATION:
                rel_normalized[rel] += 1
            else:
                rel_unknown[rel] += 1
                doc_issues.append(f"unknown rel: {rel}")

            # Check orphan endpoints
            src = rel_obj.get("source", "")
            tgt = rel_obj.get("target", "")
            if src not in entities_names or tgt not in entities_names:
                orphan_docs += 1

        # Check dates
        for date_obj in data.get("dates", []):
            total_dates += 1
            res = date_obj.get("resolution")

            if res in VALID_DATE_RESOLUTIONS:
                date_canonical[res or "null"] += 1
            elif res in _DATE_RESOLUTION_MAP:
                date_normalized[res] += 1
            else:
                date_unknown[res] += 1
                doc_issues.append(f"unknown date resolution: {res}")

        if doc_issues:
            files_with_issues.append((f.name, doc_issues))

    # Report
    print("=" * 70)
    print("RELATION TYPE COVERAGE")
    print("=" * 70)
    print(f"Total relations: {total_relations}")
    print(f"  Already canonical:  {sum(rel_canonical.values()):>5}")
    print(f"  Normalized by map:  {sum(rel_normalized.values()):>5}")
    print(f"  UNCOVERED:          {sum(rel_unknown.values()):>5}")
    print()

    if rel_normalized:
        print("Normalized (would be fixed by normalization map):")
        for rel, count in rel_normalized.most_common():
            target = RELATION_NORMALIZATION.get(rel, RELATION_NORMALIZATION.get(rel.replace("-", "_").replace(" ", "_"), "?"))
            print(f"  {rel} -> {target}  ({count}x)")
        print()

    if rel_unknown:
        print("UNCOVERED (still fail validation — need new mappings or canonical types):")
        for rel, count in rel_unknown.most_common():
            print(f"  {rel}  ({count}x)")
        print()

    print(f"Orphan endpoints (src/tgt not in entities): {orphan_docs}")
    print()

    print("=" * 70)
    print("DATE RESOLUTION COVERAGE")
    print("=" * 70)
    print(f"Total dates: {total_dates}")
    print(f"  Already valid:      {sum(date_canonical.values()):>5}")
    print(f"  Normalized by map:  {sum(date_normalized.values()):>5}")
    print(f"  UNCOVERED:          {sum(date_unknown.values()):>5}")
    print()

    if date_normalized:
        print("Normalized (would be fixed):")
        for res, count in date_normalized.most_common():
            print(f"  {res} -> {_DATE_RESOLUTION_MAP[res]}  ({count}x)")
        print()

    if date_unknown:
        print("UNCOVERED (still fail validation):")
        for res, count in date_unknown.most_common():
            print(f"  {res}  ({count}x)")
        print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    total_issues = sum(rel_unknown.values()) + sum(date_unknown.values())
    total_fixed = sum(rel_normalized.values()) + sum(date_normalized.values())
    print(f"Issues fixed by normalization:   {total_fixed}")
    print(f"Issues remaining (uncovered):    {total_issues}")
    print(f"Files with remaining issues:     {len(files_with_issues)}")

    if files_with_issues:
        print("\nFiles with uncovered issues:")
        for fname, issues in files_with_issues[:20]:
            print(f"  {fname}:")
            for issue in issues[:5]:
                print(f"    - {issue}")


def main():
    parser = argparse.ArgumentParser(description="Test normalization coverage")
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("data/extractions/biosafety"),
        help="Directory containing extraction JSON files",
    )
    args = parser.parse_args()

    if not args.dir.exists():
        print(f"Directory not found: {args.dir}")
        print("Run this on a machine with extraction data.")
        sys.exit(1)

    analyze_extractions(args.dir)


if __name__ == "__main__":
    main()
