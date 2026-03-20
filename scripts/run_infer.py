"""Run relation inference pass on the knowledge graph.

Evaluates domain-defined inference rules to create new relations
from implicit patterns in the entity graph.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db import init_db
from domain import set_active_domain


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run relation inference pass on the knowledge graph."
    )
    parser.add_argument(
        "--domain", default=None,
        help="Domain slug (default: ai or PREDICTOR_DOMAIN env var)",
    )
    parser.add_argument(
        "--db", default=None,
        help="Path to SQLite database (default: data/db/{domain}.db)",
    )
    parser.add_argument(
        "--run-date", default=None,
        help="Run date for logging (default: today)",
    )
    args = parser.parse_args()

    if args.domain:
        set_active_domain(args.domain)

    from util.paths import get_db_path
    if args.db is None:
        args.db = str(get_db_path(args.domain))

    conn = init_db(Path(args.db))

    from infer import run_inference_pass
    result = run_inference_pass(conn, run_date=args.run_date)

    print("Inference pass complete:")
    print(f"  - {result.rules_evaluated} rules evaluated")
    print(f"  - {result.relations_inferred} relations inferred")
    print(f"  - {result.relations_skipped} skipped (already existed)")
    print(f"  - {result.duration_ms}ms")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
