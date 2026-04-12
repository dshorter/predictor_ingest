"""Submit today's docpack to the Anthropic Messages Batch API.

Builds one batch request per document, posts to /v1/messages/batches,
and stores the job_id in the batch_jobs table. Exits immediately after
submission — results are collected by collect_batch.py on the next run.

Usage (called by run_pipeline.py or directly):
    python scripts/submit_batch.py --db data/db/film.db --domain film
    python scripts/submit_batch.py --db data/db/film.db --domain film --docpack data/docpacks/film/daily_bundle_2026-03-25.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
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


def load_docpack(path: Path) -> list[dict]:
    docs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line))
    return docs


def already_submitted(conn: sqlite3.Connection, domain: str, run_date: str) -> bool:
    """Return True if a batch job was already submitted for this domain+date."""
    row = conn.execute(
        "SELECT job_id FROM batch_jobs WHERE domain = ? AND run_date = ? AND status = 'pending'",
        (domain, run_date),
    ).fetchone()
    return row is not None


def submit(
    docpack_path: Path,
    db_path: Path,
    domain: str,
    run_date: str,
    model: str | None = None,
    skip_existing: bool = True,
) -> str:
    """Submit docpack to Anthropic Batch API and record the job in the DB.

    Returns the batch job_id.
    """
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    if model is None:
        model = get_model()

    from extract import (
        build_extraction_prompt,
        ANTHROPIC_EXTRACTION_SCHEMA,
        EXTRACTOR_VERSION,
    )
    from db import init_db

    conn = init_db(db_path)

    if skip_existing and already_submitted(conn, domain, run_date):
        print(f"Batch job for {domain}/{run_date} already pending — skipping submission")
        row = conn.execute(
            "SELECT job_id FROM batch_jobs WHERE domain = ? AND run_date = ? AND status = 'pending'",
            (domain, run_date),
        ).fetchone()
        return row[0]

    docs = load_docpack(docpack_path)
    if not docs:
        print("No documents in docpack — nothing to submit")
        sys.exit(0)

    # Filter docs that already have extractions on disk
    from util.paths import get_extractions_dir
    extractions_dir = get_extractions_dir(domain)
    pending_docs = []
    skipped = 0
    for doc in docs:
        doc_id = doc.get("docId", "")
        if skip_existing and (extractions_dir / f"{doc_id}.json").exists():
            skipped += 1
            continue
        pending_docs.append(doc)

    if skipped:
        print(f"Skipped {skipped} docs with existing extractions")

    if not pending_docs:
        print("All docs already extracted — nothing to submit")
        sys.exit(0)

    print(f"Submitting {len(pending_docs)} docs to Anthropic Batch API")
    print(f"  Model: {model}")
    print(f"  Domain: {domain}")
    print(f"  Run date: {run_date}")

    client = anthropic.Anthropic(api_key=api_key)

    requests = [
        {
            "custom_id": doc["docId"],
            "params": {
                "model": model,
                "max_tokens": 16384,
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
        (job_id, domain, run_date, submitted_at, json.dumps([d["docId"] for d in pending_docs])),
    )
    conn.commit()

    print(f"  Submitted: job_id={job_id}")
    print(f"  Docs: {len(pending_docs)}")
    print(f"  Status: pending (collect with collect_batch.py on next run)")
    return job_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit docpack to Anthropic Batch API")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--domain", default=None, help="Domain slug")
    parser.add_argument("--docpack", default=None, help="Path to JSONL docpack file")
    parser.add_argument("--model", default=None, help="Model ID (default: PRIMARY_MODEL env)")
    parser.add_argument("--no-skip", action="store_true", help="Re-submit even if already submitted today")
    parser.add_argument("--date", default=None, help="Run date ISO (default: today)")
    args = parser.parse_args()

    from datetime import date as _date
    run_date = args.date or _date.today().isoformat()

    if args.domain:
        os.environ["PREDICTOR_DOMAIN"] = args.domain
        from domain import set_active_domain
        set_active_domain(args.domain)

    domain = args.domain or os.environ.get("PREDICTOR_DOMAIN", "ai")

    from util.paths import get_db_path, get_docpacks_dir
    db_path = Path(args.db) if args.db else get_db_path(domain)

    if args.docpack:
        docpack_path = Path(args.docpack)
    else:
        # Default: latest daily bundle for today's date
        docpacks_dir = get_docpacks_dir(domain)
        candidates = sorted(docpacks_dir.glob(f"daily_bundle_{run_date}*.jsonl"))
        if not candidates:
            # Fall back to most recent bundle
            candidates = sorted(docpacks_dir.glob("daily_bundle_*.jsonl"))
        docpack_path = candidates[-1] if candidates else docpacks_dir / f"daily_bundle_{run_date}_all.jsonl"

    if not docpack_path.exists():
        print(f"No docpack found: {docpack_path}")
        print("Run 'make docpack' first")
        return 0

    submit(
        docpack_path=docpack_path,
        db_path=db_path,
        domain=domain,
        run_date=run_date,
        model=args.model,
        skip_existing=not args.no_skip,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
