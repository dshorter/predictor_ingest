"""Run cross-document synthesis on today's extracted documents.

Groups documents by shared entities and uses a specialist LLM to find
cross-document connections, corroboration, and implicit relations.
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
        description="Run cross-document synthesis on the knowledge graph."
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
        "--model", default="claude-sonnet-4-5-20250514",
        help="Specialist model for synthesis (default: claude-sonnet-4-5-20250514)",
    )
    parser.add_argument(
        "--run-date", default=None,
        help="Date to cluster documents from (default: today)",
    )
    args = parser.parse_args()

    if args.domain:
        set_active_domain(args.domain)

    from util.paths import get_db_path
    if args.db is None:
        args.db = str(get_db_path(args.domain))

    conn = init_db(Path(args.db))

    from synthesize import run_synthesis
    result = run_synthesis(conn, model=args.model, run_date=args.run_date)

    print("Synthesis complete:")
    print(f"  - {result.batches_processed} document clusters processed")
    print(f"  - {result.entities_corroborated} entities corroborated")
    print(f"  - {result.relations_inferred} relations inferred")
    print(f"  - {result.llm_calls} LLM calls")
    print(f"  - {result.duration_ms}ms")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
