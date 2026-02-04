"""Run entity resolution pass on all entities in the database.

Finds and merges duplicate entities using similarity matching.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db import init_db
from resolve import EntityResolver


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run entity resolution pass on the database."
    )
    parser.add_argument(
        "--db", default="data/db/predictor.db",
        help="Path to SQLite database (default: data/db/predictor.db)",
    )
    parser.add_argument(
        "--threshold", type=float, default=0.85,
        help="Similarity threshold for matching (default: 0.85)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report potential merges without applying",
    )
    args = parser.parse_args()

    conn = init_db(Path(args.db))
    resolver = EntityResolver(conn, threshold=args.threshold)

    if args.dry_run:
        # Count entities and report what would happen
        cursor = conn.execute("SELECT COUNT(*) FROM entities")
        total = cursor.fetchone()[0]
        print(f"[DRY RUN] {total} entities in database (threshold: {args.threshold})")
        print("[DRY RUN] Run without --dry-run to perform merges")
        conn.close()
        return 0

    stats = resolver.run_resolution_pass()

    print("Resolution pass complete:")
    print(f"  - {stats['entities_checked']} entities checked")
    print(f"  - {stats['merges_performed']} merges performed")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
