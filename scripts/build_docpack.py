"""Build a daily document pack from cleaned documents in the database.

Outputs:
- JSONL file (one JSON object per line) for programmatic use
- Markdown file for ChatGPT paste/upload (Mode B workflow)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db import init_db


def build_docpack(
    db_path: Path,
    target_date: str,
    max_docs: int,
    output_dir: Path,
) -> int:
    """Build JSONL and markdown bundles from cleaned documents.

    Args:
        db_path: Path to SQLite database
        target_date: Date to filter by (YYYY-MM-DD)
        max_docs: Maximum documents per bundle
        output_dir: Directory to write bundles

    Returns:
        Number of documents bundled
    """
    conn = init_db(db_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Query documents cleaned/fetched on the target date
    cursor = conn.execute(
        """
        SELECT doc_id, url, source, title, published_at, fetched_at, text_path
        FROM documents
        WHERE status IN ('fetched', 'cleaned')
          AND date(fetched_at) = ?
        ORDER BY fetched_at DESC
        LIMIT ?
        """,
        (target_date, max_docs),
    )
    rows = [dict(row) for row in cursor.fetchall()]

    if not rows:
        print(f"No documents found for {target_date}")
        conn.close()
        return 0

    # Build document list, reading cleaned text from text_path
    docs = []
    for row in rows:
        text_path = row.get("text_path")
        if not text_path:
            print(f"  WARNING: {row['doc_id']} has no text_path, skipping")
            continue

        text_file = Path(text_path)
        if not text_file.exists():
            print(f"  WARNING: {row['doc_id']} text file not found: {text_path}, skipping")
            continue

        text = text_file.read_text(encoding="utf-8")
        docs.append({
            "docId": row["doc_id"],
            "url": row["url"],
            "source": row["source"],
            "title": row["title"],
            "published": row["published_at"],
            "fetched": row["fetched_at"],
            "text": text,
        })

    if not docs:
        print(f"No documents with readable text for {target_date}")
        conn.close()
        return 0

    # Write JSONL
    jsonl_path = output_dir / f"daily_bundle_{target_date}.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    # Write Markdown
    md_path = output_dir / f"daily_bundle_{target_date}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Daily Document Bundle — {target_date}\n\n")
        f.write(
            "Extract entities, relations, and evidence from each document below.\n"
            "Output one JSON object per document following the schema in schemas/extraction.json.\n"
            "Required top-level fields: docId, extractorVersion, entities, relations, techTerms, dates.\n"
        )
        f.write("\n---\n\n")

        for i, doc in enumerate(docs, 1):
            f.write(f"## Document {i}: {doc['title']}\n\n")
            f.write(f"- **docId:** {doc['docId']}\n")
            f.write(f"- **URL:** {doc['url']}\n")
            f.write(f"- **Source:** {doc['source']}\n")
            f.write(f"- **Published:** {doc['published']}\n\n")
            f.write("### Text\n\n")
            f.write(doc["text"])
            f.write("\n\n---\n\n")

    print(f"Bundled {len(docs)} documents → {jsonl_path}")
    print(f"Bundled {len(docs)} documents → {md_path}")

    conn.close()
    return len(docs)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build daily document pack (JSONL + Markdown)."
    )
    parser.add_argument(
        "--db", default="data/db/predictor.db",
        help="Path to SQLite database (default: data/db/predictor.db)",
    )
    parser.add_argument(
        "--date", default=date.today().isoformat(),
        help="Date to filter by, YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--max-docs", type=int, default=20,
        help="Maximum documents per bundle (default: 20)",
    )
    parser.add_argument(
        "--output-dir", default="data/docpacks",
        help="Output directory (default: data/docpacks)",
    )
    args = parser.parse_args()

    count = build_docpack(
        db_path=Path(args.db),
        target_date=args.date,
        max_docs=args.max_docs,
        output_dir=Path(args.output_dir),
    )

    return 0 if count >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
