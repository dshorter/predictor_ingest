#!/usr/bin/env python3
"""
Docpack Generator

Generates daily document bundles for manual extraction via ChatGPT (Mode B).
Outputs both JSONL (machine-readable) and Markdown (ChatGPT-ready) formats.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import date
from pathlib import Path


def get_documents(conn, target_date, max_docs):
    """
    Query documents from the database for a specific date.

    Args:
        conn: SQLite connection
        target_date: Date string (YYYY-MM-DD)
        max_docs: Maximum number of documents to retrieve

    Returns:
        List of document dicts
    """
    cursor = conn.cursor()

    query = """
        SELECT doc_id, url, source, title, published_at, fetched_at, text_path
        FROM documents
        WHERE status IN ('fetched', 'cleaned')
          AND date(fetched_at) = ?
        ORDER BY fetched_at DESC
        LIMIT ?
    """

    cursor.execute(query, (target_date, max_docs))

    columns = [desc[0] for desc in cursor.description]
    documents = []

    for row in cursor.fetchall():
        doc = dict(zip(columns, row))
        documents.append(doc)

    return documents


def read_text_content(text_path, repo_root):
    """
    Read cleaned text content from file.

    Args:
        text_path: Relative path to text file
        repo_root: Repository root directory

    Returns:
        Text content or None if file doesn't exist
    """
    if not text_path:
        return None

    full_path = repo_root / text_path

    if not full_path.exists():
        return None

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"  WARNING: Failed to read {text_path}: {e}", file=sys.stderr)
        return None


def build_jsonl(documents, repo_root):
    """
    Build JSONL format (one JSON object per line).

    Args:
        documents: List of document dicts from DB
        repo_root: Repository root directory

    Returns:
        List of JSON objects (dicts)
    """
    jsonl_data = []

    for doc in documents:
        text_content = read_text_content(doc['text_path'], repo_root)

        if text_content is None:
            print(f"  WARNING: Skipping {doc['doc_id']}: text file not found", file=sys.stderr)
            continue

        jsonl_obj = {
            "docId": doc['doc_id'],
            "url": doc['url'],
            "source": doc['source'],
            "title": doc['title'],
            "published": doc['published_at'] or "",
            "fetched": doc['fetched_at'],
            "text": text_content
        }

        jsonl_data.append(jsonl_obj)

    return jsonl_data


def build_markdown(documents, repo_root, target_date):
    """
    Build Markdown format for ChatGPT paste.

    Args:
        documents: List of document dicts from DB
        repo_root: Repository root directory
        target_date: Date string for header

    Returns:
        Markdown string
    """
    lines = []

    # Header
    lines.append(f"# Daily Document Bundle — {target_date}")
    lines.append("")
    lines.append("Extract entities, relations, and evidence from each document below.")
    lines.append("Output one JSON object per document following the schema in schemas/extraction.json.")
    lines.append("Required top-level fields: docId, extractorVersion, entities, relations, techTerms, dates.")
    lines.append("")

    # Documents
    doc_count = 0
    for idx, doc in enumerate(documents, 1):
        text_content = read_text_content(doc['text_path'], repo_root)

        if text_content is None:
            print(f"  WARNING: Skipping {doc['doc_id']}: text file not found", file=sys.stderr)
            continue

        lines.append("---")
        lines.append("")
        lines.append(f"## Document {idx}: {doc['title']}")
        lines.append("")
        lines.append(f"- **docId:** {doc['doc_id']}")
        lines.append(f"- **URL:** {doc['url']}")
        lines.append(f"- **Source:** {doc['source']}")
        lines.append(f"- **Published:** {doc['published_at'] or 'Unknown'}")
        lines.append("")
        lines.append("### Text")
        lines.append("")
        lines.append(text_content)
        lines.append("")

        doc_count += 1

    return "\n".join(lines), doc_count


def main():
    parser = argparse.ArgumentParser(
        description="Generate document bundles for manual extraction (Mode B)"
    )
    parser.add_argument(
        '--db',
        default='data/db/predictor.db',
        help='Database path (default: data/db/predictor.db)'
    )
    parser.add_argument(
        '--date',
        default=str(date.today()),
        help='Filter documents by fetch date YYYY-MM-DD (default: today)'
    )
    parser.add_argument(
        '--max-docs',
        type=int,
        default=20,
        help='Maximum documents in bundle (default: 20)'
    )
    parser.add_argument(
        '--output-dir',
        default='data/docpacks',
        help='Output directory (default: data/docpacks)'
    )

    args = parser.parse_args()

    # Resolve paths
    repo_root = Path(__file__).parent.parent
    db_path = repo_root / args.db
    output_dir = repo_root / args.output_dir

    # Validate database
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        print("Run 'make init-db' first to initialize the database.", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(str(db_path))

    try:
        # Get documents
        documents = get_documents(conn, args.date, args.max_docs)

        if not documents:
            print(f"No documents found for {args.date}")
            sys.exit(0)

        print(f"Found {len(documents)} document(s) for {args.date}")

        # Build JSONL
        jsonl_data = build_jsonl(documents, repo_root)

        if not jsonl_data:
            print("ERROR: No valid documents with readable text files", file=sys.stderr)
            sys.exit(1)

        # Build Markdown
        markdown_content, md_count = build_markdown(documents, repo_root, args.date)

        # Write JSONL file
        jsonl_path = output_dir / f"daily_bundle_{args.date}.jsonl"
        with open(jsonl_path, 'w', encoding='utf-8') as f:
            for obj in jsonl_data:
                f.write(json.dumps(obj, ensure_ascii=False) + '\n')

        print(f"Bundled {len(jsonl_data)} documents → {jsonl_path}")

        # Write Markdown file
        md_path = output_dir / f"daily_bundle_{args.date}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        print(f"Bundled {md_count} documents → {md_path}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
