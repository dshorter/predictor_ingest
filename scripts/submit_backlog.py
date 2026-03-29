"""Submit backlog of un-extracted documents to the Anthropic Batch API.

Queries the DB for documents with status='cleaned' (i.e., ingested but never
extracted), builds docpack-style records for up to --chunk-size of them, and
submits a batch job. Run once per day until the backlog is cleared; the
staggered handoff (ADR-008) means each chunk is collected on the following run.

Usage:
    python scripts/submit_backlog.py --db data/db/film.db --domain film
    python scripts/submit_backlog.py --db data/db/film.db --domain film --chunk-size 50
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def load_dotenv() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.replace("\r", "").strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("\"'").strip()
                    if key and key not in os.environ:
                        os.environ[key] = value


load_dotenv()


def get_model() -> str:
    return os.environ.get("PRIMARY_MODEL", "").strip() or "claude-sonnet-4-6"


def fetch_backlog_docs(conn: sqlite3.Connection, chunk_size: int) -> list[dict]:
    """Return up to chunk_size cleaned docs that have no extraction on disk."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT doc_id, url, title, text, source, published_at, fetched_at
           FROM documents
           WHERE status = 'cleaned'
           ORDER BY published_at DESC
           LIMIT ?""",
        (chunk_size,),
    ).fetchall()
    docs = []
    for row in rows:
        docs.append({
            "docId": row["doc_id"],
            "url": row["url"] or "",
            "title": row["title"] or "",
            "text": row["text"] or "",
            "source": row["source"] or "",
            "publishedAt": row["published_at"] or "",
            "fetchedAt": row["fetched_at"] or "",
        })
    return docs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Submit backlog of un-extracted docs to Anthropic Batch API"
    )
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--domain", default=None, help="Domain slug")
    parser.add_argument("--chunk-size", type=int, default=100,
                        help="Max docs per batch submission (default: 100)")
    parser.add_argument("--model", default=None, help="Model ID (default: PRIMARY_MODEL env)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be submitted without calling the API")
    args = parser.parse_args()

    if args.domain:
        os.environ["PREDICTOR_DOMAIN"] = args.domain
        from domain import set_active_domain
        set_active_domain(args.domain)

    domain = args.domain or os.environ.get("PREDICTOR_DOMAIN", "ai")
    model = args.model or get_model()
    run_date = date.today().isoformat()
    db_path = Path(args.db)

    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 1

    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package not installed. Run: pip install anthropic")
        return 1

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return 1

    from extract import (
        build_extraction_prompt,
        ANTHROPIC_EXTRACTION_SCHEMA,
        EXTRACTOR_VERSION,
    )
    from db import init_db
    from util.paths import get_extractions_dir

    conn = init_db(db_path)
    all_docs = fetch_backlog_docs(conn, args.chunk_size * 3)  # fetch extra to filter

    # Filter docs that already have extractions on disk
    extractions_dir = get_extractions_dir(domain)
    pending_docs = []
    for doc in all_docs:
        if (extractions_dir / f"{doc['docId']}.json").exists():
            continue
        pending_docs.append(doc)
        if len(pending_docs) >= args.chunk_size:
            break

    total_backlog = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE status = 'cleaned'"
    ).fetchone()[0]

    print(f"Backlog: {total_backlog} docs with status=cleaned")
    print(f"Chunk:   {len(pending_docs)} docs selected (chunk-size={args.chunk_size})")
    print(f"Model:   {model}")
    print(f"Domain:  {domain}")

    if not pending_docs:
        print("No backlog docs to submit — all cleaned docs already extracted")
        return 0

    if args.dry_run:
        print("\nDRY RUN — would submit:")
        for doc in pending_docs[:5]:
            print(f"  {doc['docId']} — {doc.get('title', '')[:60]}")
        if len(pending_docs) > 5:
            print(f"  ... and {len(pending_docs) - 5} more")
        return 0

    client = anthropic.Anthropic(api_key=api_key)

    requests = [
        {
            "custom_id": doc["docId"],
            "params": {
                "model": model,
                "max_tokens": 8192,
                "messages": [{"role": "user", "content": build_extraction_prompt(doc, EXTRACTOR_VERSION)}],
                "output_config": {
                    "format": {
                        "type": "json_schema",
                        "schema": ANTHROPIC_EXTRACTION_SCHEMA,
                    }
                },
            },
        }
        for doc in pending_docs
    ]

    batch = client.beta.messages.batches.create(requests=requests)
    job_id = batch.id
    submitted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn.execute(
        """INSERT INTO batch_jobs (job_id, domain, run_date, submitted_at, status, doc_ids)
           VALUES (?, ?, ?, ?, 'pending', ?)""",
        (job_id, domain, run_date, submitted_at,
         json.dumps([d["docId"] for d in pending_docs])),
    )
    conn.commit()

    remaining = total_backlog - len(pending_docs)
    print(f"\nSubmitted: job_id={job_id}")
    print(f"  Docs in batch: {len(pending_docs)}")
    print(f"  Remaining backlog after this batch: ~{remaining}")
    if remaining > 0:
        print(f"  Run again tomorrow after collect drains this batch")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
