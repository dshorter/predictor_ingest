"""Run LLM extraction on documents from a docpack.

Calls Claude Sonnet to extract entities and relations from each document,
validates output against schema, and saves to data/extractions/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def load_dotenv() -> None:
    """Load .env file from project root if it exists."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                # Strip whitespace and handle Windows CRLF
                line = line.replace("\r", "").strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    # Strip quotes and whitespace from value
                    value = value.strip().strip("\"'").strip()
                    if key and key not in os.environ:
                        os.environ[key] = value


# Load environment variables from .env file
load_dotenv()

from extract import (
    build_extraction_prompt,
    parse_extraction_response,
    save_extraction,
    compare_extractions,
    ExtractionError,
    EXTRACTOR_VERSION,
)
from db import init_db, insert_extraction_comparison


def load_docpack(docpack_path: Path) -> list[dict[str, Any]]:
    """Load documents from JSONL docpack file.

    Args:
        docpack_path: Path to JSONL file

    Returns:
        List of document dicts
    """
    docs = []
    with open(docpack_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line))
    return docs


def get_default_model() -> str:
    """Get default model from environment or use fallback."""
    model = os.environ.get("PRIMARY_MODEL", "").strip()
    return model if model else "claude-sonnet-4-20250514"


def get_understudy_model() -> str | None:
    """Get understudy model from environment."""
    model = os.environ.get("UNDERSTUDY_MODEL", "").strip()
    return model if model else None


def extract_with_anthropic(
    doc: dict[str, Any],
    model: str | None = None,
    max_tokens: int = 8192,
) -> tuple[str, int]:
    """Call Anthropic API to extract from a document.

    Args:
        doc: Document dict with docId, title, text, etc.
        model: Model ID to use
        max_tokens: Max tokens for response

    Returns:
        Tuple of (response text, duration in ms)
    """
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    if model is None:
        model = get_default_model()

    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_extraction_prompt(doc)

    start_time = time.time()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    duration_ms = int((time.time() - start_time) * 1000)

    return response.content[0].text, duration_ms


def run_extraction(
    docpack_path: Path,
    output_dir: Path,
    model: str | None = None,
    max_docs: Optional[int] = None,
    skip_existing: bool = True,
    shadow_mode: bool = False,
    understudy_model: str | None = None,
    db_path: Path | None = None,
) -> tuple[int, int, int]:
    """Run extraction on all documents in a docpack.

    Args:
        docpack_path: Path to JSONL docpack file
        output_dir: Directory to save extractions
        model: Model ID to use
        max_docs: Maximum documents to process (None for all)
        skip_existing: Skip documents that already have extractions
        shadow_mode: If True, run understudy model in parallel and log comparison
        understudy_model: Model ID for understudy (required if shadow_mode=True)
        db_path: Path to SQLite database for comparison logging

    Returns:
        Tuple of (processed, succeeded, failed) counts
    """
    if model is None:
        model = get_default_model()

    # Shadow mode setup
    conn = None
    if shadow_mode:
        if not understudy_model:
            print("ERROR: --shadow requires UNDERSTUDY_MODEL env var or --understudy-model")
            sys.exit(1)
        if db_path:
            conn = init_db(db_path)
            print(f"Shadow mode: comparing {model} vs {understudy_model}")
        else:
            print(f"Shadow mode enabled but no --db specified; comparisons won't be logged")

    output_dir.mkdir(parents=True, exist_ok=True)

    docs = load_docpack(docpack_path)
    print(f"Loaded {len(docs)} documents from {docpack_path}")

    if max_docs:
        docs = docs[:max_docs]
        print(f"Limiting to first {max_docs} documents")

    processed = 0
    succeeded = 0
    failed = 0

    for i, doc in enumerate(docs, 1):
        doc_id = doc.get("docId", f"unknown_{i}")

        # Check if extraction already exists
        if skip_existing:
            existing_path = output_dir / f"{doc_id}.json"
            if existing_path.exists():
                print(f"  [{i}/{len(docs)}] {doc_id}: SKIPPED (exists)")
                continue

        print(f"  [{i}/{len(docs)}] {doc_id}: extracting...", end=" ", flush=True)
        processed += 1

        try:
            # Call primary API
            response_text, duration_ms = extract_with_anthropic(doc, model=model)

            # Parse and validate
            extraction = parse_extraction_response(response_text, doc_id)

            # Save
            save_extraction(extraction, output_dir)

            entity_count = len(extraction.get("entities", []))
            relation_count = len(extraction.get("relations", []))
            print(f"OK ({entity_count} entities, {relation_count} relations, {duration_ms}ms)")
            succeeded += 1

            # Shadow mode: run understudy and log comparison
            if shadow_mode and understudy_model:
                try:
                    us_response, us_duration = extract_with_anthropic(doc, model=understudy_model)
                    us_extraction = parse_extraction_response(us_response, doc_id)
                    us_valid = True
                    us_error = None
                except ExtractionError as ue:
                    us_extraction = {}
                    us_valid = False
                    us_error = str(ue)
                    us_duration = 0
                except Exception as ue:
                    us_extraction = {}
                    us_valid = False
                    us_error = f"{type(ue).__name__}: {ue}"
                    us_duration = 0

                # Compare and log
                comparison = compare_extractions(
                    primary=extraction,
                    understudy=us_extraction,
                    understudy_model=understudy_model,
                    schema_valid=us_valid,
                    parse_error=us_error,
                    primary_duration_ms=duration_ms,
                    understudy_duration_ms=us_duration,
                )

                if conn:
                    from datetime import date
                    insert_extraction_comparison(
                        conn,
                        doc_id=comparison["doc_id"],
                        run_date=date.today().isoformat(),
                        understudy_model=comparison["understudy_model"],
                        schema_valid=comparison["schema_valid"],
                        parse_error=comparison["parse_error"],
                        primary_entities=comparison["primary_entities"],
                        primary_relations=comparison["primary_relations"],
                        primary_tech_terms=comparison["primary_tech_terms"],
                        understudy_entities=comparison["understudy_entities"],
                        understudy_relations=comparison["understudy_relations"],
                        understudy_tech_terms=comparison["understudy_tech_terms"],
                        entity_overlap_pct=comparison["entity_overlap_pct"],
                        relation_overlap_pct=comparison["relation_overlap_pct"],
                        primary_duration_ms=comparison["primary_duration_ms"],
                        understudy_duration_ms=comparison["understudy_duration_ms"],
                    )

                # Log shadow result
                if us_valid:
                    overlap = comparison.get("entity_overlap_pct", 0) or 0
                    print(f"    └─ understudy: OK ({overlap:.0f}% entity overlap)")
                else:
                    print(f"    └─ understudy: FAILED ({us_error[:50]}...)")

        except ExtractionError as e:
            print(f"FAILED: {e}")
            failed += 1
            # Save error log
            error_path = output_dir / f"{doc_id}.error"
            with open(error_path, "w", encoding="utf-8") as f:
                f.write(f"ExtractionError: {e}\n")

        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1
            # Save error log
            error_path = output_dir / f"{doc_id}.error"
            with open(error_path, "w", encoding="utf-8") as f:
                f.write(f"Error: {type(e).__name__}: {e}\n")

        # Rate limiting - small delay between requests
        if i < len(docs):
            time.sleep(0.5)

    return processed, succeeded, failed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run LLM extraction on documents from a docpack."
    )
    parser.add_argument(
        "--docpack",
        default="data/docpacks/daily_bundle_all.jsonl",
        help="Path to JSONL docpack file (default: data/docpacks/daily_bundle_all.jsonl)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/extractions",
        help="Output directory for extractions (default: data/extractions)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model ID to use (default: PRIMARY_MODEL env var or claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Maximum documents to process (default: all)",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Re-process documents that already have extractions",
    )
    parser.add_argument(
        "--shadow",
        action="store_true",
        help="Enable shadow mode: run understudy model and log comparison stats",
    )
    parser.add_argument(
        "--understudy-model",
        default=None,
        help="Understudy model ID (default: UNDERSTUDY_MODEL env var)",
    )
    parser.add_argument(
        "--db",
        default="data/db/predictor.db",
        help="Path to SQLite database for shadow mode logging (default: data/db/predictor.db)",
    )
    args = parser.parse_args()

    docpack_path = Path(args.docpack)
    if not docpack_path.exists():
        print(f"ERROR: Docpack not found: {docpack_path}")
        return 1

    model = args.model or get_default_model()
    understudy = args.understudy_model or get_understudy_model()

    print(f"Extraction runner v{EXTRACTOR_VERSION}")
    print(f"Model: {model}")
    if args.shadow:
        print(f"Shadow mode: ON (understudy: {understudy or 'NOT SET'})")
    print(f"Docpack: {docpack_path}")
    print(f"Output: {args.output_dir}")
    print()

    processed, succeeded, failed = run_extraction(
        docpack_path=docpack_path,
        output_dir=Path(args.output_dir),
        model=model,
        max_docs=args.max_docs,
        skip_existing=not args.no_skip,
        shadow_mode=args.shadow,
        understudy_model=understudy,
        db_path=Path(args.db) if args.shadow else None,
    )

    print()
    print(f"Done. Processed: {processed}, Succeeded: {succeeded}, Failed: {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
