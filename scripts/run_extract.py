"""Synchronous single-doc extraction — fallback only.

The primary extraction path is now submit_batch.py + collect_batch.py
(ADR-008). This script is retained as a direct synchronous fallback for:
  - Testing individual documents
  - Incident recovery when the Batch API is unavailable
  - CI / unit-test extraction runs

Usage:
    python scripts/run_extract.py --docpack data/docpacks/film/daily_bundle_2026-03-25.jsonl --domain film
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

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

from extract import (
    build_extraction_prompt,
    parse_extraction_response,
    save_extraction,
    ExtractionError,
    EXTRACTOR_VERSION,
    ANTHROPIC_EXTRACTION_SCHEMA,
)


def get_model() -> str:
    model = os.environ.get("PRIMARY_MODEL", "").strip()
    return model if model else "claude-sonnet-4-6-20260218"


def load_docpack(path: Path) -> list[dict[str, Any]]:
    docs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line))
    return docs


def extract_with_anthropic(doc: dict[str, Any], model: str, max_tokens: int = 8192) -> tuple[str, int]:
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_extraction_prompt(doc, EXTRACTOR_VERSION)

    start = time.time()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": ANTHROPIC_EXTRACTION_SCHEMA,
            }
        },
    )
    duration_ms = int((time.time() - start) * 1000)
    return response.content[0].text, duration_ms


def run_extraction(
    docpack_path: Path,
    output_dir: Path,
    model: str | None = None,
    max_docs: Optional[int] = None,
    skip_existing: bool = True,
) -> tuple[int, int, int]:
    if model is None:
        model = get_model()

    output_dir.mkdir(parents=True, exist_ok=True)
    docs = load_docpack(docpack_path)
    print(f"Loaded {len(docs)} documents from {docpack_path}")
    print(f"Model: {model}")

    if max_docs:
        docs = docs[:max_docs]
        print(f"Limiting to first {max_docs} documents")

    processed = succeeded = failed = 0

    for i, doc in enumerate(docs, 1):
        doc_id = doc.get("docId", f"unknown_{i}")

        if skip_existing and (output_dir / f"{doc_id}.json").exists():
            print(f"  [{i}/{len(docs)}] {doc_id}: SKIPPED (exists)")
            continue

        print(f"  [{i}/{len(docs)}] {doc_id}: extracting...", end=" ", flush=True)
        processed += 1

        try:
            response_text, duration_ms = extract_with_anthropic(doc, model=model)
            extraction = parse_extraction_response(response_text, doc_id)
            save_extraction(extraction, output_dir)

            n_e = len(extraction.get("entities", []))
            n_r = len(extraction.get("relations", []))
            print(f"OK ({n_e}e, {n_r}r, {duration_ms}ms)")
            succeeded += 1

        except ExtractionError as e:
            print(f"FAILED: {e}")
            failed += 1
            (output_dir / f"{doc_id}.error").write_text(f"ExtractionError: {e}\n")

        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1
            (output_dir / f"{doc_id}.error").write_text(f"{type(e).__name__}: {e}\n")

        if i < len(docs):
            time.sleep(0.5)

    return processed, succeeded, failed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronous extraction fallback (primary path: submit_batch + collect_batch)"
    )
    parser.add_argument("--docpack", default="data/docpacks/daily_bundle_all.jsonl")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-docs", type=int, default=None)
    parser.add_argument("--no-skip", action="store_true")
    parser.add_argument("--domain", default=None)
    args = parser.parse_args()

    if args.domain:
        os.environ["PREDICTOR_DOMAIN"] = args.domain
        from domain import set_active_domain
        set_active_domain(args.domain)

    from util.paths import get_extractions_dir
    output_dir = Path(args.output_dir) if args.output_dir else get_extractions_dir(args.domain)

    docpack_path = Path(args.docpack)
    if not docpack_path.exists():
        print(f"No docpack found: {docpack_path}")
        print()
        print("Done. Processed: 0, Succeeded: 0, Failed: 0")
        return 0

    processed, succeeded, failed = run_extraction(
        docpack_path=docpack_path,
        output_dir=output_dir,
        model=args.model,
        max_docs=args.max_docs,
        skip_existing=not args.no_skip,
    )

    print()
    print(f"Done. Processed: {processed}, Succeeded: {succeeded}, Failed: {failed}")

    from extract import get_unmapped_relation_types
    unmapped = get_unmapped_relation_types()
    if unmapped:
        print(f"Unmapped relation types: {', '.join(f'{t}({c})' for t, c in unmapped.most_common())}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
