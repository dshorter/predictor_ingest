#!/usr/bin/env python3
"""
Entity Resolution Runner

Runs entity resolution to find and merge duplicate entities based on
similarity matching. Updates canonical IDs and adds aliases.
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from db import init_db
from resolve import EntityResolver


def main():
    parser = argparse.ArgumentParser(
        description="Run entity resolution to merge duplicate entities"
    )
    parser.add_argument(
        '--db',
        default='data/db/predictor.db',
        help='Database path (default: data/db/predictor.db)'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.85,
        help='Similarity threshold for merging (default: 0.85)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Report potential merges without applying them'
    )

    args = parser.parse_args()

    # Resolve paths
    repo_root = Path(__file__).parent.parent
    db_path = repo_root / args.db

    # Validate database
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        print("Run 'make init-db' and 'make ingest' first.", file=sys.stderr)
        sys.exit(1)

    # Connect to database
    conn = init_db(str(db_path))

    try:
        # Create resolver
        resolver = EntityResolver(conn, threshold=args.threshold)

        # Run resolution
        if args.dry_run:
            print("[DRY RUN] Simulating entity resolution...", file=sys.stderr)
            # Note: EntityResolver doesn't have a native dry-run mode
            # In dry-run, we just report what would be done without committing
            print("[DRY RUN] Mode not fully implemented - would check for duplicates")
            print(f"[DRY RUN] Using threshold: {args.threshold}")
            stats = {"entities_checked": 0, "merges": 0, "aliases_added": 0}
        else:
            stats = resolver.run_resolution_pass()

        # Print results
        if args.dry_run:
            print("\n[DRY RUN] No changes made to database")
        else:
            print("\nResolution pass complete:")
            print(f"  - {stats.get('entities_checked', 0)} entities checked")
            print(f"  - {stats.get('merges', 0)} merges performed")
            print(f"  - {stats.get('aliases_added', 0)} aliases added")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
