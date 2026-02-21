"""Collect pipeline diagnostics into a snapshot for sharing.

Gathers logs, graph JSON, database summary, and extractions into
a tar.gz that can be shared via gist for analysis.

Usage:
    python scripts/collect_diagnostics.py                # tar.gz to diagnostics/
    python scripts/collect_diagnostics.py --gist         # tar + upload as GitHub gist
    python scripts/collect_diagnostics.py --date 2026-02-19  # specific date only
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def collect_file(src: Path, dest_dir: Path, label: str) -> bool:
    """Copy a file into the snapshot directory. Returns True if copied."""
    if not src.exists():
        print(f"  [{label}] not found: {src}")
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_dir / src.name)
    size_kb = src.stat().st_size / 1024
    print(f"  [{label}] {src.name} ({size_kb:.1f} KB)")
    return True


def collect_glob(src_dir: Path, pattern: str, dest_dir: Path, label: str) -> int:
    """Copy all files matching pattern. Returns count."""
    if not src_dir.exists():
        print(f"  [{label}] directory not found: {src_dir}")
        return 0
    files = sorted(src_dir.glob(pattern))
    if not files:
        print(f"  [{label}] no files matching {pattern}")
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(f, dest_dir / f.name)
    total_kb = sum(f.stat().st_size for f in files) / 1024
    print(f"  [{label}] {len(files)} files ({total_kb:.1f} KB)")
    return len(files)


def dump_db_summary(db_path: Path, dest_dir: Path) -> bool:
    """Extract key stats and full entity/relation dump from the database."""
    if not db_path.exists():
        print(f"  [db] not found: {db_path}")
        return False

    dest_dir.mkdir(parents=True, exist_ok=True)
    summary: dict = {"db_path": str(db_path), "collected_at": utc_now_compact()}

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Document counts by status
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM documents GROUP BY status"
        ).fetchall()
        summary["documents_by_status"] = {r["status"]: r["cnt"] for r in rows}
        summary["documents_total"] = sum(r["cnt"] for r in rows)

        # Entity counts by type
        rows = conn.execute(
            "SELECT entity_type, COUNT(*) as cnt FROM entities GROUP BY entity_type"
        ).fetchall()
        summary["entities_by_type"] = {r["entity_type"]: r["cnt"] for r in rows}
        summary["entities_total"] = sum(r["cnt"] for r in rows)

        # Relation counts by rel type
        rows = conn.execute(
            "SELECT rel, COUNT(*) as cnt FROM relations GROUP BY rel ORDER BY cnt DESC"
        ).fetchall()
        summary["relations_by_type"] = {r["rel"]: r["cnt"] for r in rows}
        summary["relations_total"] = sum(r["cnt"] for r in rows)

        # Evidence count
        row = conn.execute("SELECT COUNT(*) as cnt FROM evidence").fetchone()
        summary["evidence_total"] = row["cnt"] if row else 0

        # Alias count
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM entity_aliases").fetchone()
            summary["aliases_total"] = row["cnt"] if row else 0
        except sqlite3.OperationalError:
            summary["aliases_total"] = 0

        # Recent documents (last 20)
        rows = conn.execute(
            "SELECT doc_id, url, source, title, published_at, status "
            "FROM documents ORDER BY fetched_at DESC LIMIT 20"
        ).fetchall()
        summary["recent_documents"] = [dict(r) for r in rows]

        # All entities with their types
        rows = conn.execute(
            "SELECT entity_id, name, entity_type, first_seen, last_seen "
            "FROM entities ORDER BY last_seen DESC"
        ).fetchall()
        summary["all_entities"] = [dict(r) for r in rows]

        # All relations with evidence counts
        rows = conn.execute(
            "SELECT r.id, r.source_id, r.rel, r.target_id, r.kind, "
            "r.confidence, r.doc_id, "
            "(SELECT COUNT(*) FROM evidence e WHERE e.relation_id = r.id) as evidence_count "
            "FROM relations r ORDER BY r.id"
        ).fetchall()
        summary["all_relations"] = [dict(r) for r in rows]

        # Full evidence dump (snippets are the key debugging info)
        rows = conn.execute(
            "SELECT e.id, e.relation_id, e.doc_id, e.url, e.published, "
            "e.snippet, e.char_span "
            "FROM evidence e ORDER BY e.relation_id"
        ).fetchall()
        summary["all_evidence"] = [dict(r) for r in rows]

        conn.close()

    except Exception as e:
        summary["error"] = str(e)
        print(f"  [db] error reading database: {e}")

    out_path = dest_dir / "db_summary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  [db] summary: {summary.get('documents_total', '?')} docs, "
          f"{summary.get('entities_total', '?')} entities, "
          f"{summary.get('relations_total', '?')} relations, "
          f"{summary.get('evidence_total', '?')} evidence")
    return True


def create_gist(tar_path: Path) -> str | None:
    """Upload tar.gz as a GitHub gist. Returns gist URL or None."""
    # Check gh is available and authenticated
    try:
        subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, check=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("  [gist] 'gh' CLI not found or not authenticated.")
        print("         Install: https://cli.github.com/")
        print("         Auth:    gh auth login")
        return None

    print(f"  [gist] uploading {tar_path.name}...")
    try:
        result = subprocess.run(
            [
                "gh", "gist", "create",
                str(tar_path),
                "--desc", f"predictor_ingest diagnostics {tar_path.stem}",
            ],
            capture_output=True, text=True, check=True, timeout=60,
        )
        url = result.stdout.strip()
        print(f"  [gist] uploaded: {url}")
        return url
    except subprocess.CalledProcessError as e:
        print(f"  [gist] upload failed: {e.stderr.strip()}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect pipeline diagnostics.")
    parser.add_argument(
        "--date",
        help="Collect for specific date (YYYY-MM-DD). Default: all available.",
    )
    parser.add_argument(
        "--gist", action="store_true",
        help="Upload snapshot as a GitHub gist (requires 'gh' CLI).",
    )
    parser.add_argument(
        "--db", default="data/db/predictor.db",
        help="Path to SQLite database (default: data/db/predictor.db)",
    )
    args = parser.parse_args()

    timestamp = utc_now_compact()
    snapshot_name = f"snapshot_{timestamp}"
    diag_dir = PROJECT_ROOT / "diagnostics"
    snapshot_dir = diag_dir / snapshot_name

    print(f"Collecting diagnostics → diagnostics/{snapshot_name}/")
    print()

    # 1. Pipeline logs
    log_dir = PROJECT_ROOT / "data" / "logs"
    if args.date:
        collect_file(log_dir / f"pipeline_{args.date}.json", snapshot_dir / "logs", "logs")
    else:
        collect_glob(log_dir, "pipeline_*.json", snapshot_dir / "logs", "logs")

    # 2. Live graph JSON (what the client is actually rendering)
    live_dir = PROJECT_ROOT / "web" / "data" / "graphs" / "live"
    collect_glob(live_dir, "*.json", snapshot_dir / "graphs_live", "live graphs")

    # 3. Dated graph output (pipeline export)
    graphs_dir = PROJECT_ROOT / "data" / "graphs"
    if args.date:
        collect_glob(
            graphs_dir / args.date, "*.json",
            snapshot_dir / f"graphs_{args.date}", "dated graphs",
        )
    elif graphs_dir.exists():
        dated_dirs = sorted([d for d in graphs_dir.iterdir() if d.is_dir()])
        for d in dated_dirs[-3:]:  # last 3 dates
            collect_glob(d, "*.json", snapshot_dir / f"graphs_{d.name}", f"graphs/{d.name}")

    # 4. Database summary (full entity/relation/evidence dump as JSON)
    db_path = PROJECT_ROOT / args.db
    dump_db_summary(db_path, snapshot_dir)

    # 5. Extractions (per-doc JSON)
    ext_dir = PROJECT_ROOT / "data" / "extractions"
    collect_glob(ext_dir, "*.json", snapshot_dir / "extractions", "extractions")

    # 6. Docpacks (bundled docs)
    docpack_dir = PROJECT_ROOT / "data" / "docpacks"
    if args.date:
        collect_file(
            docpack_dir / f"daily_bundle_{args.date}.jsonl",
            snapshot_dir / "docpacks", "docpacks",
        )
        collect_file(
            docpack_dir / f"daily_bundle_{args.date}.md",
            snapshot_dir / "docpacks", "docpacks",
        )
    else:
        collect_glob(docpack_dir, "*.jsonl", snapshot_dir / "docpacks", "docpacks")

    # 7. Feed config (for context)
    collect_file(PROJECT_ROOT / "config" / "feeds.yaml", snapshot_dir, "config")

    # Write manifest
    manifest = {
        "snapshot": snapshot_name,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "date_filter": args.date,
    }
    with open(snapshot_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print()

    # Always create tar.gz
    tar_path = diag_dir / f"{snapshot_name}.tar.gz"
    shutil.make_archive(
        str(diag_dir / snapshot_name), "gztar",
        root_dir=str(diag_dir),
        base_dir=snapshot_name,
    )
    tar_size = tar_path.stat().st_size / 1024
    print(f"Archive: diagnostics/{snapshot_name}.tar.gz ({tar_size:.1f} KB)")

    # Clean up the uncompressed directory
    shutil.rmtree(snapshot_dir)

    # Upload gist if requested
    gist_url = None
    if args.gist:
        print()
        gist_url = create_gist(tar_path)

    print()
    if gist_url:
        print(f"Share this URL with Claude: {gist_url}")
    else:
        print(f"Snapshot: diagnostics/{snapshot_name}.tar.gz")
        if not args.gist:
            print("Upload with:  gh gist create diagnostics/" + snapshot_name + ".tar.gz")
        print("Or share the file directly.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
