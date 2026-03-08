"""Reset all collected data for a clean re-ingest.

Removes (for the selected domain):
- SQLite database: data/db/{domain}.db
- data/raw/{domain}/        (raw HTML files)
- data/text/{domain}/       (cleaned text files)
- data/docpacks/{domain}/   (JSONL + MD bundles)
- data/extractions/{domain}/ (per-doc extraction JSON — PRESERVES these by default)
- data/graphs/{domain}/     (Cytoscape exports)
- data/logs/{domain}/       (pipeline run logs)

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

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from util.paths import (
    get_db_path,
    get_docpacks_dir,
    get_extractions_dir,
    get_graphs_dir,
    get_logs_dir,
    get_raw_dir,
    get_text_dir,
)


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
        "--domain", default=None,
        help="Domain slug to reset (default: ai or PREDICTOR_DOMAIN env var)",
    )
    parser.add_argument(
        "--include-extractions", action="store_true",
        help="Also delete extractions (manual extraction JSON files)",
    )
    parser.add_argument(
        "--include-web", action="store_true",
        help="Also delete web/data/graphs/live/{domain}/",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    from util.paths import _resolve_domain
    domain = _resolve_domain(args.domain)

    project_root = Path(__file__).resolve().parents[1]
    db_path = get_db_path(domain)

    dirs_to_clear: list[Path] = [
        get_raw_dir(domain),
        get_text_dir(domain),
        get_docpacks_dir(domain),
        get_graphs_dir(domain),
        get_logs_dir(domain),
    ]

    if args.include_extractions:
        dirs_to_clear.append(get_extractions_dir(domain))

    if args.include_web:
        dirs_to_clear.append(Path("web/data/graphs/live") / domain)

    db_full = project_root / db_path

    # Show what will be deleted
    print(f"=== Data Reset Plan (domain: {domain}) ===\n")

    total_files = 0
    total_mb = 0.0

    if db_full.exists():
        size = db_full.stat().st_size / (1024 * 1024)
        print(f"  DELETE  {db_path}  ({size:.1f} MB)")
        total_mb += size
    else:
        print(f"  SKIP    {db_path}  (not found)")

    for d_rel in dirs_to_clear:
        d = project_root / d_rel
        n = count_files(d)
        mb = dir_size_mb(d)
        total_files += n
        total_mb += mb
        if n > 0:
            print(f"  CLEAR   {d_rel}/  ({n} files, {mb:.1f} MB)")
        else:
            print(f"  SKIP    {d_rel}/  (empty or not found)")

    if not args.include_extractions:
        ext_dir = project_root / get_extractions_dir(domain)
        ext_n = count_files(ext_dir)
        if ext_n > 0:
            print(f"\n  KEEP    {get_extractions_dir(domain)}/  ({ext_n} files — use --include-extractions to delete)")

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
        print(f"  Deleted {db_path}")

    # Clear data directories (remove contents, keep the directory)
    for d_rel in dirs_to_clear:
        d = project_root / d_rel
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)
        print(f"  Cleared {d_rel}/")

    # Remove pipeline lock if present
    lock = project_root / "data" / "pipeline.lock"
    if lock.exists():
        lock.unlink()
        print("  Removed pipeline.lock")

    print(f"\nDone. Run the pipeline to re-ingest from scratch:")
    print(f"  python scripts/run_pipeline.py --domain {domain}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
