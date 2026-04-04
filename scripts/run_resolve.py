"""Run entity resolution pass on all entities in the database.

Finds and merges duplicate entities using similarity matching.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _bootstrap_domain() -> None:
    """Set PREDICTOR_DOMAIN from --domain arg before any domain-aware imports."""
    for i, arg in enumerate(sys.argv):
        if arg == "--domain" and i + 1 < len(sys.argv):
            os.environ["PREDICTOR_DOMAIN"] = sys.argv[i + 1]
            return
        if arg.startswith("--domain="):
            os.environ["PREDICTOR_DOMAIN"] = arg.split("=", 1)[1]
            return


def _load_dotenv() -> None:
    """Load .env from project root so standalone invocations pick up API keys."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


_load_dotenv()
_bootstrap_domain()

from db import init_db
from resolve import EntityResolver


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run entity resolution pass on the database."
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
        "--threshold", type=float, default=0.85,
        help="Similarity threshold for matching (default: 0.85)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report potential merges without applying",
    )
    parser.add_argument(
        "--llm-disambiguate", action="store_true",
        help="Enable LLM-powered disambiguation for gray-zone pairs",
    )
    parser.add_argument(
        "--disambiguate-model", default="gpt-5-nano",
        help="Model for LLM disambiguation (default: gpt-5-nano)",
    )
    args = parser.parse_args()

    from util.paths import get_db_path
    if args.db is None:
        args.db = str(get_db_path(args.domain))

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

    stats = resolver.run_resolution_pass(
        llm_disambiguate=args.llm_disambiguate,
        disambiguate_model=args.disambiguate_model,
        dry_run=args.dry_run,
    )

    print("Resolution pass complete:")
    print(f"  - {stats['entities_checked']} entities checked")
    print(f"  - {stats['merges_performed']} merges performed")

    if args.llm_disambiguate:
        print(f"  - {stats.get('disambig_pairs_evaluated', 0)} gray-zone pairs evaluated by LLM")
        print(f"  - {stats.get('disambig_merges', 0)} LLM-confirmed merges")
        print(f"  - {stats.get('disambig_kept_separate', 0)} kept separate")
        print(f"  - {stats.get('disambig_uncertain', 0)} uncertain")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
