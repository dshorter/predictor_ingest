#!/usr/bin/env python3
"""
Wipe all pipeline data for a domain.

Removes the SQLite database and all data directories for the given domain:
  data/db/<domain>.db
  data/raw/<domain>/
  data/text/<domain>/
  data/docpacks/<domain>/
  data/extractions/<domain>/
  data/graphs/<domain>/
  web/data/graphs/live/<domain>/

Domain config (domains/<domain>/, web/data/domains/<domain>.json) is NOT touched.

Usage:
    python scripts/wipe_domain_data.py --domain biosafety          # dry run
    python scripts/wipe_domain_data.py --domain biosafety --confirm
"""

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def targets(domain: str) -> list[tuple[str, Path]]:
    return [
        ("database",       REPO_ROOT / "data" / "db" / f"{domain}.db"),
        ("raw content",    REPO_ROOT / "data" / "raw" / domain),
        ("cleaned text",   REPO_ROOT / "data" / "text" / domain),
        ("docpacks",       REPO_ROOT / "data" / "docpacks" / domain),
        ("extractions",    REPO_ROOT / "data" / "extractions" / domain),
        ("graph exports",  REPO_ROOT / "data" / "graphs" / domain),
        ("web live graphs",REPO_ROOT / "web" / "data" / "graphs" / "live" / domain),
    ]


def main():
    parser = argparse.ArgumentParser(description="Wipe all pipeline data for a domain.")
    parser.add_argument("--domain", required=True, help="Domain slug (e.g. biosafety)")
    parser.add_argument("--confirm", action="store_true",
                        help="Actually delete. Without this flag, only a dry run is shown.")
    args = parser.parse_args()

    domain = args.domain

    # Safety: refuse to wipe the default AI domain without an explicit override
    if domain == "ai" and not args.confirm:
        print("ERROR: wiping 'ai' is destructive. Pass --confirm to proceed.")
        sys.exit(1)

    items = targets(domain)
    existing = [(label, path) for label, path in items if path.exists()]

    if not existing:
        print(f"Nothing to wipe — no data found for domain '{domain}'.")
        return

    print(f"{'DRY RUN — ' if not args.confirm else ''}Wipe plan for domain: {domain}\n")
    for label, path in items:
        status = "EXISTS" if path.exists() else "absent"
        action = ("DELETE" if path.exists() else "skip  ") if args.confirm else ("would delete" if path.exists() else "absent      ")
        kind = "file" if path.is_file() else "dir "
        print(f"  [{action}]  {kind}  {path.relative_to(REPO_ROOT)}  ({label})")

    if not args.confirm:
        print(f"\nDry run complete. Re-run with --confirm to actually delete.")
        return

    print()
    deleted = 0
    for label, path in existing:
        try:
            if path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
            print(f"  deleted  {path.relative_to(REPO_ROOT)}")
            deleted += 1
        except Exception as e:
            print(f"  ERROR deleting {path}: {e}", file=sys.stderr)

    print(f"\nDone. {deleted}/{len(existing)} items removed for domain '{domain}'.")
    print("Domain config (domains/{0}/, web/data/domains/{0}.json) was not touched.".format(domain))


if __name__ == "__main__":
    main()
