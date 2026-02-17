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
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    build_extraction_system_prompt,
    build_extraction_user_prompt,
    parse_extraction_response,
    save_extraction,
    compare_extractions,
    score_extraction_quality,
    ExtractionError,
    EXTRACTOR_VERSION,
    ESCALATION_THRESHOLD,
    OPENAI_EXTRACTION_TOOL,
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


def is_openai_model(model: str) -> bool:
    """Check if a model ID is an OpenAI model."""
    openai_prefixes = ("gpt-", "o1", "o3", "o4")
    return any(model.startswith(p) for p in openai_prefixes)


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


def extract_with_openai(
    doc: dict[str, Any],
    model: str = "gpt-5-nano",
) -> tuple[str, int]:
    """Call OpenAI API using tool calling with strict schema enforcement.

    Uses a split prompt (system + user) for prompt caching, and the
    emit_extraction tool with strict: true to guarantee schema compliance.

    Args:
        doc: Document dict with docId, title, text, etc.
        model: OpenAI model ID

    Returns:
        Tuple of (JSON response text, duration in ms)
    """
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai package not installed. Run: pip install openai")
        sys.exit(1)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    system_prompt = build_extraction_system_prompt()
    user_prompt = build_extraction_user_prompt(doc)

    start_time = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=[OPENAI_EXTRACTION_TOOL],
        tool_choice={"type": "function", "function": {"name": "emit_extraction"}},
    )
    duration_ms = int((time.time() - start_time) * 1000)

    # Extract the tool call arguments (this IS the JSON extraction)
    choice = response.choices[0]
    if choice.message.tool_calls:
        json_str = choice.message.tool_calls[0].function.arguments
    else:
        # Fallback: model returned content instead of tool call
        json_str = choice.message.content or "{}"

    return json_str, duration_ms


def extract_document(
    doc: dict[str, Any],
    model: str,
) -> tuple[str, int]:
    """Route extraction to the correct provider based on model ID.

    Args:
        doc: Document dict
        model: Model ID (auto-detects provider)

    Returns:
        Tuple of (response text, duration in ms)
    """
    if is_openai_model(model):
        return extract_with_openai(doc, model=model)
    else:
        return extract_with_anthropic(doc, model=model)


def run_shadow_only(
    docpack_path: Path,
    output_dir: Path,
    understudy_model: str,
    db_path: Path | None = None,
    max_docs: Optional[int] = None,
) -> tuple[int, int, int]:
    """Run only the understudy extraction against existing primary results.

    Loads primary extractions from disk, runs the understudy model,
    and logs comparison stats. Does NOT call the primary model.

    Args:
        docpack_path: Path to JSONL docpack file
        output_dir: Directory where primary extractions live
        understudy_model: Model ID for understudy
        db_path: Path to SQLite database for comparison logging
        max_docs: Maximum documents to process (None for all)

    Returns:
        Tuple of (processed, succeeded, failed) counts
    """
    conn = None
    if db_path:
        conn = init_db(db_path)
    print(f"Shadow-only mode: running {understudy_model} against existing extractions")

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

        # Load existing primary extraction
        primary_path = output_dir / f"{doc_id}.json"
        if not primary_path.exists():
            print(f"  [{i}/{len(docs)}] {doc_id}: SKIPPED (no primary extraction)")
            continue

        with open(primary_path, "r", encoding="utf-8") as f:
            extraction = json.load(f)

        print(f"  [{i}/{len(docs)}] {doc_id}: understudy extracting...", end=" ", flush=True)
        processed += 1

        try:
            us_response, us_duration = extract_document(doc, model=understudy_model)
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

        comparison = compare_extractions(
            primary=extraction,
            understudy=us_extraction,
            understudy_model=understudy_model,
            schema_valid=us_valid,
            parse_error=us_error,
            primary_duration_ms=0,
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

        if us_valid:
            overlap = comparison.get("entity_overlap_pct", 0) or 0
            print(f"OK ({overlap:.0f}% entity overlap, {us_duration}ms)")
            succeeded += 1
        else:
            print(f"FAILED ({us_error[:60]}...)")
            failed += 1

        if i < len(docs):
            time.sleep(0.5)

    return processed, succeeded, failed


def run_escalation(
    docpack_path: Path,
    output_dir: Path,
    cheap_model: str,
    specialist_model: str,
    max_docs: Optional[int] = None,
    skip_existing: bool = True,
    db_path: Path | None = None,
) -> tuple[int, int, int, int]:
    """Run extraction with escalation: cheap model first, specialist on demand.

    For each document:
    1. Run cheap model (e.g. gpt-5-nano with strict schema)
    2. Score extraction quality
    3. If quality is below threshold, re-run with specialist model (e.g. Sonnet)
    4. Save the best result; log which model was used

    Args:
        docpack_path: Path to JSONL docpack file
        output_dir: Directory to save extractions
        cheap_model: Budget model ID (tried first)
        specialist_model: Specialist model ID (escalation target)
        max_docs: Maximum documents to process
        skip_existing: Skip documents that already have extractions
        db_path: Path to SQLite database for logging

    Returns:
        Tuple of (processed, succeeded, failed, escalated) counts
    """
    conn = None
    if db_path:
        conn = init_db(db_path)

    output_dir.mkdir(parents=True, exist_ok=True)

    docs = load_docpack(docpack_path)
    print(f"Loaded {len(docs)} documents from {docpack_path}")
    print(f"Escalation mode: {cheap_model} -> {specialist_model} (threshold: {ESCALATION_THRESHOLD})")

    if max_docs:
        docs = docs[:max_docs]
        print(f"Limiting to first {max_docs} documents")

    processed = 0
    succeeded = 0
    failed = 0
    escalated = 0

    for i, doc in enumerate(docs, 1):
        doc_id = doc.get("docId", f"unknown_{i}")
        source_text = doc.get("text", "")

        if skip_existing:
            existing_path = output_dir / f"{doc_id}.json"
            if existing_path.exists():
                print(f"  [{i}/{len(docs)}] {doc_id}: SKIPPED (exists)")
                continue

        print(f"  [{i}/{len(docs)}] {doc_id}: ", end="", flush=True)
        processed += 1

        # Step 1: Try cheap model
        try:
            response_text, duration_ms = extract_document(doc, model=cheap_model)
            extraction = parse_extraction_response(response_text, doc_id)
        except (ExtractionError, Exception) as e:
            # Cheap model failed entirely — escalate immediately
            print(f"cheap FAILED ({e}), escalating... ", end="", flush=True)
            try:
                response_text, duration_ms = extract_document(doc, model=specialist_model)
                extraction = parse_extraction_response(response_text, doc_id)
                extraction["_extractedBy"] = specialist_model
                extraction["_escalationReason"] = f"cheap_failed: {e}"
                save_extraction(extraction, output_dir)

                entity_count = len(extraction.get("entities", []))
                relation_count = len(extraction.get("relations", []))
                print(f"specialist OK ({entity_count}e, {relation_count}r, {duration_ms}ms)")
                succeeded += 1
                escalated += 1
            except (ExtractionError, Exception) as e2:
                print(f"specialist also FAILED: {e2}")
                failed += 1
                error_path = output_dir / f"{doc_id}.error"
                error_path.write_text(f"Both models failed.\nCheap: {e}\nSpecialist: {e2}\n")
            if i < len(docs):
                time.sleep(0.5)
            continue

        # Step 2: Score the cheap extraction
        quality = score_extraction_quality(extraction, len(source_text))
        score = quality["combined_score"]

        if not quality["escalate"]:
            # Good enough — keep the cheap result
            extraction["_extractedBy"] = cheap_model
            extraction["_qualityScore"] = score
            save_extraction(extraction, output_dir)

            entity_count = len(extraction.get("entities", []))
            relation_count = len(extraction.get("relations", []))
            print(f"cheap OK (q={score:.2f}, {entity_count}e, {relation_count}r, {duration_ms}ms)")
            succeeded += 1
        else:
            # Quality too low — escalate to specialist
            print(f"cheap q={score:.2f} < {ESCALATION_THRESHOLD}, escalating... ", end="", flush=True)
            try:
                spec_response, spec_duration = extract_document(doc, model=specialist_model)
                spec_extraction = parse_extraction_response(spec_response, doc_id)
                spec_extraction["_extractedBy"] = specialist_model
                spec_extraction["_escalationReason"] = (
                    f"quality_low: score={score:.2f}, "
                    f"density={quality['entity_density']:.1f}, "
                    f"evidence={quality['evidence_coverage']:.0%}, "
                    f"confidence={quality['avg_confidence']:.2f}"
                )
                spec_extraction["_qualityScore"] = score_extraction_quality(
                    spec_extraction, len(source_text)
                )["combined_score"]
                save_extraction(spec_extraction, output_dir)

                entity_count = len(spec_extraction.get("entities", []))
                relation_count = len(spec_extraction.get("relations", []))
                print(f"specialist OK ({entity_count}e, {relation_count}r, {spec_duration}ms)")
                succeeded += 1
                escalated += 1
            except (ExtractionError, Exception) as e2:
                # Specialist also failed — save the cheap result anyway
                extraction["_extractedBy"] = cheap_model
                extraction["_qualityScore"] = score
                extraction["_escalationFailed"] = str(e2)
                save_extraction(extraction, output_dir)
                print(f"specialist FAILED ({e2}), keeping cheap result")
                succeeded += 1
                escalated += 1

        if i < len(docs):
            time.sleep(0.5)

    return processed, succeeded, failed, escalated


def run_extraction(
    docpack_path: Path,
    output_dir: Path,
    model: str | None = None,
    max_docs: Optional[int] = None,
    skip_existing: bool = True,
    shadow_mode: bool = False,
    understudy_model: str | None = None,
    db_path: Path | None = None,
    parallel: bool = False,
) -> tuple[int, int, int]:
    """Run extraction on all documents in a docpack.

    Args:
        docpack_path: Path to JSONL docpack file
        output_dir: Directory to save extractions
        model: Model ID to use
        max_docs: Maximum documents to process (None for all)
        skip_existing: Skip documents that already have extractions
        shadow_mode: If True, run understudy model and log comparison
        understudy_model: Model ID for understudy (required if shadow_mode=True)
        db_path: Path to SQLite database for comparison logging
        parallel: If True, run primary and understudy extractions in parallel

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
            # Shadow mode with parallel execution
            if shadow_mode and understudy_model and parallel:
                # Run both extractions in parallel
                with ThreadPoolExecutor(max_workers=2) as executor:
                    primary_future = executor.submit(extract_document, doc, model)
                    understudy_future = executor.submit(extract_document, doc, understudy_model)

                    # Get primary result
                    response_text, duration_ms = primary_future.result()
                    extraction = parse_extraction_response(response_text, doc_id)
                    save_extraction(extraction, output_dir)

                    entity_count = len(extraction.get("entities", []))
                    relation_count = len(extraction.get("relations", []))
                    print(f"OK ({entity_count} entities, {relation_count} relations, {duration_ms}ms)")
                    succeeded += 1

                    # Get understudy result
                    try:
                        us_response, us_duration = understudy_future.result()
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

            else:
                # Sequential: Call primary API first
                response_text, duration_ms = extract_document(doc, model=model)
                extraction = parse_extraction_response(response_text, doc_id)
                save_extraction(extraction, output_dir)

                entity_count = len(extraction.get("entities", []))
                relation_count = len(extraction.get("relations", []))
                print(f"OK ({entity_count} entities, {relation_count} relations, {duration_ms}ms)")
                succeeded += 1

                # Shadow mode: run understudy sequentially
                if shadow_mode and understudy_model:
                    try:
                        us_response, us_duration = extract_document(doc, model=understudy_model)
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

            # Log shadow comparison (for both parallel and sequential)
            if shadow_mode and understudy_model:
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
        "--shadow-only",
        action="store_true",
        help="Run only the understudy model against existing primary extractions (no primary API calls)",
    )
    parser.add_argument(
        "--escalate",
        action="store_true",
        help="Escalation mode: run cheap model first, escalate to specialist if quality is low",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run primary and understudy extractions in parallel (requires --shadow)",
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
        print(f"No docpack found: {docpack_path} (no documents to extract)")
        print()
        print("Done. Processed: 0, Succeeded: 0, Failed: 0")
        return 0

    model = args.model or get_default_model()
    understudy = args.understudy_model or get_understudy_model()

    print(f"Extraction runner v{EXTRACTOR_VERSION}")

    escalated = 0

    if args.shadow_only:
        if not understudy:
            print("ERROR: --shadow-only requires UNDERSTUDY_MODEL env var or --understudy-model")
            return 1
        print(f"Shadow-only mode: {understudy}")
        print(f"Docpack: {docpack_path}")
        print(f"Extractions dir: {args.output_dir}")
        print()

        processed, succeeded, failed = run_shadow_only(
            docpack_path=docpack_path,
            output_dir=Path(args.output_dir),
            understudy_model=understudy,
            db_path=Path(args.db),
            max_docs=args.max_docs,
        )

    elif args.escalate:
        if not understudy:
            print("ERROR: --escalate requires UNDERSTUDY_MODEL env var or --understudy-model")
            return 1
        cheap = understudy
        specialist = model
        print(f"Escalation mode: {cheap} -> {specialist} (threshold: {ESCALATION_THRESHOLD})")
        print(f"Docpack: {docpack_path}")
        print(f"Output: {args.output_dir}")
        print()

        processed, succeeded, failed, escalated = run_escalation(
            docpack_path=docpack_path,
            output_dir=Path(args.output_dir),
            cheap_model=cheap,
            specialist_model=specialist,
            max_docs=args.max_docs,
            skip_existing=not args.no_skip,
            db_path=Path(args.db),
        )

    else:
        print(f"Model: {model}")
        if args.shadow:
            mode = "parallel" if args.parallel else "sequential"
            print(f"Shadow mode: ON ({mode}, understudy: {understudy or 'NOT SET'})")
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
            parallel=args.parallel,
        )

    print()
    summary = f"Done. Processed: {processed}, Succeeded: {succeeded}, Failed: {failed}"
    if escalated:
        pct = (escalated / processed * 100) if processed else 0
        summary += f", Escalated: {escalated}/{processed} ({pct:.0f}%)"
    print(summary)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
