"""Collect results from pending Anthropic Batch API jobs.

Queries batch_jobs for all pending jobs (ordered by submitted_at), checks
their status, and processes any that are complete. Implements the staggered
daily handoff described in ADR-008:

  Exit code 0 — all pending jobs collected (or no jobs pending); caller
                proceeds with import → resolve → … → trending
  Exit code 2 — one or more jobs still in flight; caller should skip
                graph stages for today (they will run tomorrow when the
                batch completes)
  Exit code 1 — unexpected error

Edge cases (from ADR-008):
  - Still pending:  log warning, exit 2 → caller skips graph stages
  - Two days piled: collect both, caller runs one combined graph pass
  - Failed batch:   fall back to sync extraction for affected docs

Usage:
    python scripts/collect_batch.py --db data/db/film.db --domain film
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

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_PENDING = 2  # signal to caller: skip graph stages today


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


def _sync_fallback(
    doc_ids: list[str],
    db_path: Path,
    domain: str,
    extractions_dir: Path,
) -> int:
    """Synchronous fallback extraction for docs from a failed batch job.

    Calls the Anthropic API directly for each doc. Used when a batch job
    has status errored/canceled/expired.

    Returns number of docs successfully extracted.
    """
    try:
        import anthropic
    except ImportError:
        print("  ERROR: anthropic package not installed")
        return 0

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ERROR: ANTHROPIC_API_KEY not set — cannot fallback")
        return 0

    from db import init_db
    from extract import (
        build_extraction_prompt,
        parse_extraction_response,
        save_extraction,
        ExtractionError,
        ANTHROPIC_EXTRACTION_SCHEMA,
        EXTRACTOR_VERSION,
    )

    conn = init_db(db_path)
    client = anthropic.Anthropic(api_key=api_key)
    model = get_model()

    # Load doc text from DB
    succeeded = 0
    for doc_id in doc_ids:
        row = conn.execute(
            "SELECT doc_id, title, url, source, published_at, text_path FROM documents WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()
        if not row:
            print(f"  [{doc_id}] not found in DB — skipping")
            continue

        text_path = row["text_path"]
        if not text_path or not Path(text_path).exists():
            print(f"  [{doc_id}] text file missing — skipping")
            continue

        text = Path(text_path).read_text(encoding="utf-8")
        doc = {
            "docId": doc_id,
            "title": row["title"] or "",
            "url": row["url"] or "",
            "source": row["source"] or "",
            "publishedAt": row["published_at"] or "",
            "text": text,
        }

        print(f"  [{doc_id}] fallback sync extraction...", end=" ", flush=True)
        try:
            response = client.messages.create(
                model=model,
                max_tokens=8192,
                messages=[{"role": "user", "content": build_extraction_prompt(doc, EXTRACTOR_VERSION)}],
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": ANTHROPIC_EXTRACTION_SCHEMA,
                    }
                },
            )
            extraction = parse_extraction_response(response.content[0].text, doc_id)
            save_extraction(extraction, extractions_dir)
            n_e = len(extraction.get("entities", []))
            n_r = len(extraction.get("relations", []))
            print(f"OK ({n_e}e, {n_r}r)")
            succeeded += 1
        except ExtractionError as e:
            print(f"FAILED: {e}")
        except Exception as e:
            print(f"ERROR: {e}")

    return succeeded


def collect(
    db_path: Path,
    domain: str,
    extractions_dir: Path,
) -> int:
    """Collect all pending batch jobs for a domain.

    Returns an exit code: EXIT_OK, EXIT_PENDING, or EXIT_ERROR.
    """
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package not installed. Run: pip install anthropic")
        return EXIT_ERROR

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return EXIT_ERROR

    from db import init_db
    from extract import (
        parse_extraction_response,
        save_extraction,
        ExtractionError,
    )

    conn = init_db(db_path)
    client = anthropic.Anthropic(api_key=api_key)

    pending_jobs = conn.execute(
        "SELECT * FROM batch_jobs WHERE domain = ? AND status = 'pending' ORDER BY submitted_at",
        (domain,),
    ).fetchall()

    if not pending_jobs:
        print("No pending batch jobs — nothing to collect")
        return EXIT_OK

    print(f"Found {len(pending_jobs)} pending batch job(s)")

    any_still_pending = False
    total_collected = 0
    total_failed = 0

    for job in pending_jobs:
        job_id = job["job_id"]
        run_date = job["run_date"]
        doc_ids = json.loads(job["doc_ids"])
        print(f"\n[{job_id}] run_date={run_date}, {len(doc_ids)} docs")

        batch = client.beta.messages.batches.retrieve(job_id)
        status = batch.processing_status  # in_progress | ended

        if status == "in_progress":
            print(f"  Still in progress — graph stages will be skipped today")
            print(f"  (will be collected tomorrow along with today's batch)")
            any_still_pending = True
            continue

        # Batch has ended — process results
        completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        collected = 0
        errors = 0
        fallback_needed = []

        for result in client.beta.messages.batches.results(job_id):
            doc_id = result.custom_id
            result_type = result.result.type  # succeeded | errored | canceled | expired

            if result_type == "succeeded":
                response_text = result.result.message.content[0].text
                try:
                    extraction = parse_extraction_response(response_text, doc_id)
                    save_extraction(extraction, extractions_dir)
                    n_e = len(extraction.get("entities", []))
                    n_r = len(extraction.get("relations", []))
                    print(f"  [{doc_id}] OK ({n_e}e, {n_r}r)")
                    collected += 1
                except ExtractionError as e:
                    print(f"  [{doc_id}] parse error: {e} — queuing fallback")
                    fallback_needed.append(doc_id)
                    errors += 1
            else:
                print(f"  [{doc_id}] {result_type} — queuing fallback")
                fallback_needed.append(doc_id)
                errors += 1

        # Sync fallback for any per-doc failures within the batch
        if fallback_needed:
            print(f"\n  Running sync fallback for {len(fallback_needed)} failed docs...")
            fb_ok = _sync_fallback(fallback_needed, db_path, domain, extractions_dir)
            collected += fb_ok

        # Download result JSONL to disk for audit trail
        result_dir = Path("data/batch_results") / domain
        result_dir.mkdir(parents=True, exist_ok=True)
        result_file = str(result_dir / f"{job_id}.jsonl")
        try:
            with open(result_file, "w", encoding="utf-8") as f:
                for result in client.beta.messages.batches.results(job_id):
                    f.write(json.dumps({
                        "custom_id": result.custom_id,
                        "type": result.result.type,
                    }) + "\n")
        except Exception as e:
            print(f"  Warning: could not save result file: {e}")
            result_file = None

        conn.execute(
            """UPDATE batch_jobs
               SET status = 'complete', completed_at = ?, result_file = ?
               WHERE job_id = ?""",
            (completed_at, result_file, job_id),
        )
        conn.commit()

        total_collected += collected
        total_failed += errors - len(fallback_needed)  # net unrecovered failures
        print(f"  Collected: {collected}/{len(doc_ids)} docs")

    if any_still_pending:
        print(f"\nOne or more batches still in flight — skipping graph stages today")
        print(f"Collected {total_collected} docs from completed batches")
        return EXIT_PENDING

    print(f"\nAll batches collected. Total docs: {total_collected}")
    return EXIT_OK


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect results from pending Anthropic Batch API jobs")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--domain", default=None, help="Domain slug")
    parser.add_argument("--output-dir", default=None, help="Extractions output directory")
    args = parser.parse_args()

    if args.domain:
        os.environ["PREDICTOR_DOMAIN"] = args.domain
        from domain import set_active_domain
        set_active_domain(args.domain)

    domain = args.domain or os.environ.get("PREDICTOR_DOMAIN", "ai")

    from util.paths import get_extractions_dir
    extractions_dir = Path(args.output_dir) if args.output_dir else get_extractions_dir(domain)
    extractions_dir.mkdir(parents=True, exist_ok=True)

    return collect(Path(args.db), domain, extractions_dir)


if __name__ == "__main__":
    raise SystemExit(main())
