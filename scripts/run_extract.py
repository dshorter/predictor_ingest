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
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    if key and key not in os.environ:
                        os.environ[key] = value


# Load environment variables from .env file
load_dotenv()

from extract import (
    build_extraction_prompt,
    parse_extraction_response,
    save_extraction,
    ExtractionError,
    EXTRACTOR_VERSION,
)


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
    return os.environ.get("PRIMARY_MODEL", "claude-sonnet-4-20250514")


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
) -> tuple[int, int, int]:
    """Run extraction on all documents in a docpack.

    Args:
        docpack_path: Path to JSONL docpack file
        output_dir: Directory to save extractions
        model: Model ID to use
        max_docs: Maximum documents to process (None for all)
        skip_existing: Skip documents that already have extractions

    Returns:
        Tuple of (processed, succeeded, failed) counts
    """
    if model is None:
        model = get_default_model()

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
            # Call API
            response_text, duration_ms = extract_with_anthropic(doc, model=model)

            # Parse and validate
            extraction = parse_extraction_response(response_text, doc_id)

            # Save
            save_extraction(extraction, output_dir)

            entity_count = len(extraction.get("entities", []))
            relation_count = len(extraction.get("relations", []))
            print(f"OK ({entity_count} entities, {relation_count} relations, {duration_ms}ms)")
            succeeded += 1

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
    args = parser.parse_args()

    docpack_path = Path(args.docpack)
    if not docpack_path.exists():
        print(f"ERROR: Docpack not found: {docpack_path}")
        return 1

    model = args.model or get_default_model()
    print(f"Extraction runner v{EXTRACTOR_VERSION}")
    print(f"Model: {model}")
    print(f"Docpack: {docpack_path}")
    print(f"Output: {args.output_dir}")
    print()

    processed, succeeded, failed = run_extraction(
        docpack_path=docpack_path,
        output_dir=Path(args.output_dir),
        model=model,
        max_docs=args.max_docs,
        skip_existing=not args.no_skip,
    )

    print()
    print(f"Done. Processed: {processed}, Succeeded: {succeeded}, Failed: {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
