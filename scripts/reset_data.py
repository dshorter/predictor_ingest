"""Reset all collected data for a clean re-ingest.

Removes:
- SQLite database (will be recreated by init_db on next run)
- data/raw/        (raw HTML files)
- data/text/       (cleaned text files)
- data/docpacks/   (JSONL + MD bundles)
- data/extractions/ (per-doc extraction JSON — PRESERVES these by default)
- data/graphs/     (Cytoscape exports)
- data/logs/       (pipeline run logs)

Does NOT touch:
- config/          (feed definitions)
- schemas/         (SQL + JSON schemas)
- web/data/        (use --include-web to clear)
- src/, scripts/, tests/  (code)
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


DATA_DIRS = [
    "data/raw",
    "data/text",
    "data/docpacks",
    "data/graphs",
    "data/logs",
]

DB_PATH = "data/db/predictor.db"


def count_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for f in directory.rglob("*") if f.is_file())


def dir_size_mb(directory: Path) -> float:
    if not directory.exists():
        return 0.0
    return sum(f.stat().st_size for f in directory.rglob("*") if f.is_file()) / (1024 * 1024)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset all collected data for a clean re-ingest.")
    parser.add_argument(
        "--include-extractions", action="store_true",
        help="Also delete data/extractions/ (manual extraction JSON files)",
    )
    parser.add_argument(
        "--include-web", action="store_true",
        help="Also delete web/data/graphs/live/",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]

    dirs_to_clear = list(DATA_DIRS)
    if args.include_extractions:
        dirs_to_clear.append("data/extractions")

    web_live = "web/data/graphs/live"
    if args.include_web:
        dirs_to_clear.append(web_live)

    db_full = project_root / DB_PATH

    # Show what will be deleted
    print("=== Data Reset Plan ===\n")

    total_files = 0
    total_mb = 0.0

    if db_full.exists():
        size = db_full.stat().st_size / (1024 * 1024)
        print(f"  DELETE  {DB_PATH}  ({size:.1f} MB)")
        total_mb += size
    else:
        print(f"  SKIP    {DB_PATH}  (not found)")

    for rel_dir in dirs_to_clear:
        d = project_root / rel_dir
        n = count_files(d)
        mb = dir_size_mb(d)
        total_files += n
        total_mb += mb
        if n > 0:
            print(f"  CLEAR   {rel_dir}/  ({n} files, {mb:.1f} MB)")
        else:
            print(f"  SKIP    {rel_dir}/  (empty or not found)")

    if not args.include_extractions:
        ext_dir = project_root / "data/extractions"
        ext_n = count_files(ext_dir)
        if ext_n > 0:
            print(f"\n  KEEP    data/extractions/  ({ext_n} files — use --include-extractions to delete)")

    print(f"\nTotal: {total_files} files + DB, ~{total_mb:.1f} MB")

    if total_files == 0 and not db_full.exists():
        print("\nNothing to delete.")
        return 0

    if not args.yes:
        confirm = input("\nProceed? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return 1

    # Delete DB
    if db_full.exists():
        db_full.unlink()
        # Also remove WAL and journal files
        for suffix in ["-wal", "-shm", "-journal"]:
            sidecar = db_full.parent / (db_full.name + suffix)
            if sidecar.exists():
                sidecar.unlink()
        print(f"  Deleted {DB_PATH}")

    # Clear data directories (remove contents, keep the directory)
    for rel_dir in dirs_to_clear:
        d = project_root / rel_dir
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)
        print(f"  Cleared {rel_dir}/")

    # Remove pipeline lock if present
    lock = project_root / "data" / "pipeline.lock"
    if lock.exists():
        lock.unlink()
        print("  Removed pipeline.lock")

    print("\nDone. Run the pipeline to re-ingest from scratch:")
    print("  python scripts/run_pipeline.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
