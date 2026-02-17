"""Repair data integrity issues in the pipeline.

Diagnoses and fixes:
1. Missing text files: re-cleans from raw HTML if available
2. Orphaned DB records: marks docs with missing files as 'error'
3. Re-ingests docs stuck in 'error' status from retryable errors (429/5xx)

Usage:
    python scripts/repair_data.py --db data/db/predictor.db --check
    python scripts/repair_data.py --db data/db/predictor.db --fix
    python scripts/repair_data.py --db data/db/predictor.db --fix --retry-errors
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db import init_db
from util import clean_html, sha256_text


def check_integrity(conn: sqlite3.Connection) -> dict:
    """Check for data integrity issues.

    Returns dict with counts of each issue type.
    """
    issues = {
        "missing_text_files": 0,
        "missing_raw_files": 0,
        "cleaned_but_no_text_path": 0,
        "retryable_errors": 0,
        "permanent_errors": 0,
        "total_docs": 0,
        "cleaned_docs": 0,
        "error_docs": 0,
    }

    # Count docs by status
    for row in conn.execute(
        "SELECT status, COUNT(*) as cnt FROM documents GROUP BY status"
    ).fetchall():
        issues["total_docs"] += row["cnt"]
        if row["status"] == "cleaned":
            issues["cleaned_docs"] = row["cnt"]
        elif row["status"] == "error":
            issues["error_docs"] = row["cnt"]

    # Check cleaned docs with missing text files
    rows = conn.execute(
        "SELECT doc_id, text_path, raw_path FROM documents WHERE status = 'cleaned'"
    ).fetchall()
    for row in rows:
        if not row["text_path"]:
            issues["cleaned_but_no_text_path"] += 1
        elif not Path(row["text_path"]).exists():
            issues["missing_text_files"] += 1
        if row["raw_path"] and not Path(row["raw_path"]).exists():
            issues["missing_raw_files"] += 1

    # Count retryable vs permanent errors
    error_rows = conn.execute(
        "SELECT error FROM documents WHERE status = 'error' AND error IS NOT NULL"
    ).fetchall()
    for row in error_rows:
        err = row["error"] or ""
        if "429" in err or "500" in err or "502" in err or "503" in err or "504" in err:
            issues["retryable_errors"] += 1
        elif "403" in err:
            issues["permanent_errors"] += 1

    return issues


def fix_missing_text(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """Re-generate text files from raw HTML where text is missing.

    Returns count of files recovered.
    """
    recovered = 0
    rows = conn.execute(
        """
        SELECT doc_id, raw_path, text_path
        FROM documents
        WHERE status = 'cleaned'
          AND text_path IS NOT NULL
        """
    ).fetchall()

    for row in rows:
        text_path = Path(row["text_path"])
        raw_path = Path(row["raw_path"]) if row["raw_path"] else None

        if text_path.exists():
            continue  # text file is fine

        if raw_path and raw_path.exists():
            if dry_run:
                print(f"  WOULD recover: {row['doc_id']} from {raw_path}")
                recovered += 1
                continue

            # Re-clean from raw HTML
            html = raw_path.read_text(encoding="utf-8", errors="replace")
            text = clean_html(html)
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(text + "\n", encoding="utf-8")
            content_hash = sha256_text(text)

            conn.execute(
                "UPDATE documents SET content_hash = ? WHERE doc_id = ?",
                (content_hash, row["doc_id"]),
            )
            print(f"  Recovered: {row['doc_id']}")
            recovered += 1
        else:
            # Both raw and text missing — mark as error
            if not dry_run:
                conn.execute(
                    """
                    UPDATE documents
                    SET status = 'error',
                        error = 'data_loss: both raw and text files missing'
                    WHERE doc_id = ?
                    """,
                    (row["doc_id"],),
                )
            print(f"  ORPHANED (no raw): {row['doc_id']}")

    if not dry_run:
        conn.commit()
    return recovered


def reset_retryable_errors(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """Reset docs with retryable errors (429/5xx) so they get re-ingested.

    Returns count of docs reset.
    """
    reset = 0
    rows = conn.execute(
        """
        SELECT doc_id, error
        FROM documents
        WHERE status = 'error'
          AND error IS NOT NULL
          AND (error LIKE '%429%' OR error LIKE '%500%'
               OR error LIKE '%502%' OR error LIKE '%503%'
               OR error LIKE '%504%')
        """
    ).fetchall()

    for row in rows:
        if dry_run:
            print(f"  WOULD reset: {row['doc_id']} ({row['error'][:60]})")
        else:
            # Delete the error record so ingest will retry it
            conn.execute("DELETE FROM documents WHERE doc_id = ?", (row["doc_id"],))
        reset += 1

    if not dry_run:
        conn.commit()
    return reset


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair pipeline data integrity.")
    parser.add_argument(
        "--db", default="data/db/predictor.db",
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Check for issues without fixing (default if no action specified)",
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="Fix missing text files and orphaned records",
    )
    parser.add_argument(
        "--retry-errors", action="store_true",
        help="Reset retryable errors (429/5xx) so ingest will re-fetch them",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    if not args.fix and not args.retry_errors:
        args.check = True

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 1

    conn = init_db(db_path)

    # Always show current state
    issues = check_integrity(conn)
    print("=== Data Integrity Report ===")
    print(f"  Total documents:       {issues['total_docs']}")
    print(f"  Cleaned (OK):          {issues['cleaned_docs']}")
    print(f"  Errors:                {issues['error_docs']}")
    print(f"    Retryable (429/5xx): {issues['retryable_errors']}")
    print(f"    Permanent (403):     {issues['permanent_errors']}")
    print(f"  Missing text files:    {issues['missing_text_files']}")
    print(f"  Missing raw files:     {issues['missing_raw_files']}")
    print(f"  No text_path in DB:    {issues['cleaned_but_no_text_path']}")
    print()

    if args.check and not args.fix and not args.retry_errors:
        if issues["missing_text_files"] or issues["retryable_errors"]:
            print("Run with --fix to repair missing text files")
            print("Run with --retry-errors to reset retryable errors for re-ingestion")
        else:
            print("No issues found.")
        conn.close()
        return 0

    if args.fix:
        label = "DRY RUN: " if args.dry_run else ""
        print(f"{label}Fixing missing text files...")
        recovered = fix_missing_text(conn, dry_run=args.dry_run)
        print(f"  {label}Recovered {recovered} text files")
        print()

    if args.retry_errors:
        label = "DRY RUN: " if args.dry_run else ""
        print(f"{label}Resetting retryable errors...")
        reset = reset_retryable_errors(conn, dry_run=args.dry_run)
        print(f"  {label}Reset {reset} documents for retry")
        print()

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
