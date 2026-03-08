from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the SQLite database.")
    parser.add_argument(
        "--domain", default=None,
        help="Domain slug (default: ai or PREDICTOR_DOMAIN env var)",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite database (default: data/db/{domain}.db)",
    )
    parser.add_argument(
        "--schema",
        default="schemas/sqlite.sql",
        help="Path to schema SQL.",
    )
    args = parser.parse_args()

    from util.paths import get_db_path
    if args.db is None:
        args.db = str(get_db_path(args.domain))

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_path = Path(args.schema)
    schema_sql = schema_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

    print(f"Initialized {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
