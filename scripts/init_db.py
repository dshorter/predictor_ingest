from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the SQLite database.")
    parser.add_argument(
        "--db",
        default="data/db/ingest.sqlite",
        help="Path to sqlite db.",
    )
    parser.add_argument(
        "--schema",
        default="schemas/sqlite.sql",
        help="Path to schema SQL.",
    )
    args = parser.parse_args()

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
