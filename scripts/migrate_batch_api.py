"""DB migration: ADR-008 — replace escalation tables with batch_jobs.

Run once per domain DB to migrate from the two-tier escalation schema to
the Anthropic Batch API schema.

Changes:
  - Drops tables: extraction_comparison, quality_runs, quality_metrics
  - Drops columns from documents: extracted_by, quality_score, escalation_failed
  - Creates table: batch_jobs

Usage:
    python scripts/migrate_batch_api.py --db data/db/film.db
    python scripts/migrate_batch_api.py --db data/db/ai.db
    python scripts/migrate_batch_api.py --db data/db/biosafety.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def migrate(db_path: Path, dry_run: bool = False) -> None:
    if not db_path.exists():
        print(f"DB not found: {db_path} — skipping")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    actions: list[tuple[str, str]] = []

    # --- 1. Drop escalation/shadow tables if they exist ---
    for table in ("extraction_comparison", "quality_runs", "quality_metrics"):
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if exists:
            actions.append((f"DROP TABLE {table}", f"drop table {table}"))

    # --- 2. Drop escalation columns from documents (SQLite 3.35.0+) ---
    doc_cols = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
    for col in ("extracted_by", "quality_score", "escalation_failed"):
        if col in doc_cols:
            actions.append(
                (f"ALTER TABLE documents DROP COLUMN {col}", f"drop documents.{col}")
            )

    # --- 3. Create batch_jobs if it doesn't exist ---
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='batch_jobs'"
    ).fetchone()
    if not exists:
        actions.append((
            """CREATE TABLE batch_jobs (
  job_id        TEXT PRIMARY KEY,
  domain        TEXT NOT NULL,
  run_date      TEXT NOT NULL,
  submitted_at  TEXT NOT NULL,
  status        TEXT NOT NULL,
  doc_ids       TEXT NOT NULL,
  result_file   TEXT,
  completed_at  TEXT
)""",
            "create table batch_jobs",
        ))
        for idx_sql, idx_label in [
            ("CREATE INDEX IF NOT EXISTS idx_batch_jobs_domain ON batch_jobs(domain)", "index domain"),
            ("CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs(status)", "index status"),
            ("CREATE INDEX IF NOT EXISTS idx_batch_jobs_submitted ON batch_jobs(submitted_at)", "index submitted"),
        ]:
            actions.append((idx_sql, idx_label))

    if not actions:
        print(f"{db_path}: already up to date")
        conn.close()
        return

    print(f"{db_path}: {len(actions)} changes{'  [DRY RUN]' if dry_run else ''}")
    for sql, label in actions:
        print(f"  {label}")
        if not dry_run:
            conn.execute(sql)

    if not dry_run:
        conn.commit()
        print(f"  migration complete")

    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate DB to ADR-008 batch API schema")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    args = parser.parse_args()

    migrate(Path(args.db), dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
