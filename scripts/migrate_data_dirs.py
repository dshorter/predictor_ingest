"""Migrate flat data directories to domain-scoped layout.

Before (V1 flat layout):
    data/raw/*.html          → data/raw/ai/*.html
    data/text/*.txt           → data/text/ai/*.txt
    data/docpacks/*.jsonl     → data/docpacks/ai/*.jsonl
    data/extractions/*.json   → data/extractions/ai/*.json
    data/graphs/YYYY-MM-DD/   → data/graphs/ai/YYYY-MM-DD/
    data/logs/*.json          → data/logs/ai/*.json
    data/db/predictor.db      → data/db/ai.db

This is a one-time migration. All existing data is AI-domain since no
other domain has been ingested yet.

Usage:
    python scripts/migrate_data_dirs.py           # dry-run (default)
    python scripts/migrate_data_dirs.py --apply   # actually move files
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "ai"

# Directories where files sit directly (flat → domain subdir)
FLAT_DIRS = ["raw", "text", "docpacks", "extractions", "logs"]

# Directories where date subdirs sit (e.g. data/graphs/2026-03-01/)
SUBDIR_DIRS = ["graphs"]


def looks_like_date_dir(p: Path) -> bool:
    """Check if path name looks like YYYY-MM-DD."""
    name = p.name
    return len(name) == 10 and name[4] == "-" and name[7] == "-"


def migrate_flat(data_root: Path, name: str, domain: str, apply: bool) -> int:
    """Move files from data/{name}/ into data/{name}/{domain}/."""
    src = data_root / name
    if not src.exists():
        return 0

    # Check if already migrated (domain subdir exists with files)
    dst = src / domain
    if dst.exists() and any(dst.iterdir()):
        print(f"  SKIP  data/{name}/ — already has {domain}/ subdir with files")
        return 0

    # Collect files (not directories named after domains)
    files = [f for f in src.iterdir() if f.is_file()]
    if not files:
        print(f"  SKIP  data/{name}/ — no files to move")
        return 0

    print(f"  MOVE  data/{name}/ → data/{name}/{domain}/  ({len(files)} files)")
    if apply:
        dst.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.move(str(f), str(dst / f.name))
    return len(files)


def migrate_subdirs(data_root: Path, name: str, domain: str, apply: bool) -> int:
    """Move date subdirs from data/{name}/ into data/{name}/{domain}/."""
    src = data_root / name
    if not src.exists():
        return 0

    dst = src / domain
    if dst.exists() and any(dst.iterdir()):
        print(f"  SKIP  data/{name}/ — already has {domain}/ subdir with content")
        return 0

    # Collect date subdirectories
    subdirs = [d for d in src.iterdir() if d.is_dir() and looks_like_date_dir(d)]
    if not subdirs:
        print(f"  SKIP  data/{name}/ — no date subdirs to move")
        return 0

    print(f"  MOVE  data/{name}/YYYY-MM-DD/ → data/{name}/{domain}/YYYY-MM-DD/  ({len(subdirs)} dirs)")
    if apply:
        dst.mkdir(parents=True, exist_ok=True)
        for d in subdirs:
            shutil.move(str(d), str(dst / d.name))
    return len(subdirs)


def migrate_db(data_root: Path, domain: str, apply: bool) -> bool:
    """Rename data/db/predictor.db → data/db/{domain}.db."""
    old_db = data_root / "db" / "predictor.db"
    new_db = data_root / "db" / f"{domain}.db"

    if new_db.exists():
        print(f"  SKIP  data/db/{domain}.db — already exists")
        return False

    if not old_db.exists():
        print(f"  SKIP  data/db/predictor.db — not found")
        return False

    print(f"  MOVE  data/db/predictor.db → data/db/{domain}.db")
    if apply:
        old_db.rename(new_db)
        # Move sidecar files (WAL, SHM, journal)
        for suffix in ["-wal", "-shm", "-journal"]:
            sidecar = old_db.parent / (old_db.name + suffix)
            if sidecar.exists():
                sidecar.rename(new_db.parent / (new_db.name + suffix))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate flat data directories to domain-scoped layout."
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually move files (default: dry-run)",
    )
    parser.add_argument(
        "--domain", default=DOMAIN,
        help=f"Target domain slug (default: {DOMAIN})",
    )
    args = parser.parse_args()

    data_root = PROJECT_ROOT / "data"
    if not data_root.exists():
        print("No data/ directory found — nothing to migrate.")
        return 0

    mode = "APPLYING" if args.apply else "DRY RUN"
    print(f"=== Data Migration ({mode}) — all flat data → {args.domain}/ ===\n")

    total = 0
    for name in FLAT_DIRS:
        total += migrate_flat(data_root, name, args.domain, args.apply)

    for name in SUBDIR_DIRS:
        total += migrate_subdirs(data_root, name, args.domain, args.apply)

    db_moved = migrate_db(data_root, args.domain, args.apply)

    print()
    if total == 0 and not db_moved:
        print("Nothing to migrate.")
    elif not args.apply:
        print(f"Would migrate {total} items + {'DB' if db_moved else 'no DB'}.")
        print("Re-run with --apply to execute.")
    else:
        print(f"Migrated {total} items + {'DB' if db_moved else 'no DB change'}.")
        print("Migration complete.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
