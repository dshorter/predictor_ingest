"""Build a daily document pack from cleaned documents in the database.

Outputs:
- JSONL file (one JSON object per line) for programmatic use
- Markdown file for ChatGPT paste/upload (Mode B workflow)

When --budget is set, applies quality-based selection to control
extraction costs while ensuring feed representation. See src/doc_select/
for the scoring algorithm.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db import init_db


def build_docpack(
    db_path: Path,
    target_date: str,
    max_docs: int,
    output_dir: Path,
    all_docs: bool = False,
    label: str | None = None,
    budget: int | None = None,
    stretch_max: int | None = None,
    feeds_config: Path | None = None,
) -> int:
    """Build JSONL and markdown bundles from cleaned documents.

    Args:
        db_path: Path to SQLite database
        target_date: Date to filter by (YYYY-MM-DD), ignored if all_docs=True
        max_docs: Maximum documents per bundle (hard cap on DB query)
        output_dir: Directory to write bundles
        all_docs: If True, ignore date filter and grab all cleaned documents
        label: Override the bundle filename label (default: date or "all")
        budget: If set, apply quality-based selection to pick this many docs
                (with feed representation). None = no selection, use all.
        stretch_max: Max docs when stretching beyond budget for high-quality
                     docs. Defaults to budget + 5 if budget is set.
        feeds_config: Path to feeds.yaml for tier/signal info. If None and
                      budget is set, all feeds default to tier 1 / primary.

    Returns:
        Number of documents bundled
    """
    conn = init_db(db_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Query documents - only select docs that have text files recorded
    if all_docs:
        cursor = conn.execute(
            """
            SELECT doc_id, url, source, title, published_at, fetched_at, text_path
            FROM documents
            WHERE status = 'cleaned'
              AND text_path IS NOT NULL
            ORDER BY fetched_at DESC
            LIMIT ?
            """,
            (max_docs,),
        )
        bundle_label = label or "all"
    else:
        # Filter by published_at so daily runs prioritise articles
        # actually published on the target date.
        # published_at is stored as ISO-8601 date or datetime; substr
        # extracts the date portion for comparison.
        cursor = conn.execute(
            """
            SELECT doc_id, url, source, title, published_at, fetched_at, text_path
            FROM documents
            WHERE status = 'cleaned'
              AND text_path IS NOT NULL
              AND published_at IS NOT NULL
              AND substr(published_at, 1, 10) = ?
            ORDER BY fetched_at DESC
            LIMIT ?
            """,
            (target_date, max_docs),
        )
        bundle_label = label or target_date
    rows = [dict(row) for row in cursor.fetchall()]

    # Backlog fallback: if the date filter found nothing (or we already got
    # today's docs), also pick up any cleaned docs from other dates that
    # have never been extracted.  This prevents docs from being stranded
    # when their published_at doesn't match the daily run date.
    # Skip anything older than 6 months — stale content isn't worth extracting.
    if not all_docs:
        already_ids = {r["doc_id"] for r in rows}
        remaining = max_docs - len(rows)
        cutoff_date = (date.fromisoformat(target_date) - timedelta(days=180)).isoformat()
        if remaining > 0:
            backlog_cursor = conn.execute(
                """
                SELECT doc_id, url, source, title, published_at, fetched_at, text_path
                FROM documents
                WHERE status = 'cleaned'
                  AND text_path IS NOT NULL
                  AND (published_at IS NULL OR substr(published_at, 1, 10) != ?)
                  AND COALESCE(substr(published_at, 1, 10),
                               substr(fetched_at, 1, 10)) >= ?
                ORDER BY fetched_at DESC
                LIMIT ?
                """,
                (target_date, cutoff_date, remaining),
            )
            backlog_rows = [dict(r) for r in backlog_cursor.fetchall()
                           if r["doc_id"] not in already_ids]
            if backlog_rows:
                print(f"Backlog: adding {len(backlog_rows)} cleaned docs from other dates "
                      f"(cutoff: {cutoff_date})")
                rows.extend(backlog_rows)

    if not rows:
        # Diagnostic: show total docs by status so user knows why nothing was bundled
        status_rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM documents GROUP BY status"
        ).fetchall()
        if status_rows:
            status_info = ", ".join(f"{r[0]}={r[1]}" for r in status_rows)
            print(f"No unextracted documents found (DB status: {status_info})")
        else:
            print(f"No documents found for {bundle_label} (database is empty)")
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
        print(f"No documents with readable text for {bundle_label}")
        conn.close()
        return 0

    # --- Quality-based selection (when budget is set) ---
    if budget is not None and len(docs) > budget:
        from doc_select import select_for_extraction
        from config import load_feeds

        effective_stretch = stretch_max if stretch_max is not None else budget + 5

        # Load feed tier/signal info from config
        feed_tiers: dict[str, int] = {}
        feed_signals: dict[str, str] = {}
        if feeds_config and feeds_config.exists():
            for fc in load_feeds(feeds_config, include_disabled=True):
                feed_tiers[fc.name] = fc.tier
                feed_signals[fc.name] = fc.signal

        # Convert docs to candidate format for selection
        candidates = [
            {
                "doc_id": d["docId"],
                "source": d["source"],
                "title": d["title"],
                "published_at": d["published"],
                "text": d["text"],
                "url": d["url"],
                "fetched": d["fetched"],
            }
            for d in docs
        ]

        print(f"Selection: {len(docs)} candidates, budget={budget}, "
              f"stretch_max={effective_stretch}")

        selected = select_for_extraction(
            candidates=candidates,
            feed_tiers=feed_tiers,
            feed_signals=feed_signals,
            budget=budget,
            stretch_max=effective_stretch,
        )

        # Report per-feed breakdown
        feed_counts: dict[str, int] = {}
        for s in selected:
            feed_counts[s.source] = feed_counts.get(s.source, 0) + 1
        for feed, count in sorted(feed_counts.items()):
            print(f"  {feed}: {count} docs")

        if selected:
            avg_q = sum(s.quality_score for s in selected) / len(selected)
            min_q = min(s.quality_score for s in selected)
            print(f"Selected {len(selected)} docs (avg quality={avg_q:.2f}, "
                  f"min={min_q:.2f})")
        else:
            print("Selection: no docs met quality threshold")

        # Rebuild docs list from selection
        docs = [
            {
                "docId": s.doc_id,
                "url": s.row.get("url", ""),
                "source": s.source,
                "title": s.title,
                "published": s.published_at,
                "fetched": s.row.get("fetched", ""),
                "text": s.text,
            }
            for s in selected
        ]

        if not docs:
            print(f"No documents passed quality selection for {bundle_label}")
            conn.close()
            return 0

    # Write JSONL
    jsonl_path = output_dir / f"daily_bundle_{bundle_label}.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    # Write Markdown
    md_path = output_dir / f"daily_bundle_{bundle_label}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Document Bundle — {bundle_label}\n\n")
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
        "--max-docs", type=int, default=500,
        help="Maximum documents per bundle (default: 500)",
    )
    parser.add_argument(
        "--output-dir", default="data/docpacks",
        help="Output directory (default: data/docpacks)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Ignore date filter, bundle all cleaned documents",
    )
    parser.add_argument(
        "--label", default=None,
        help="Override bundle filename label (default: date or 'all')",
    )
    parser.add_argument(
        "--budget", type=int, default=None,
        help="Target number of docs to select (enables quality-based selection). "
             "Goal: 10-20 docs, stretch up to --stretch-max if quality warrants.",
    )
    parser.add_argument(
        "--stretch-max", type=int, default=None,
        help="Maximum docs when stretching beyond budget for high-quality docs "
             "(default: budget + 5)",
    )
    parser.add_argument(
        "--feeds-config", default=None,
        help="Path to feeds.yaml for source tier/signal info "
             "(default: config/feeds.yaml)",
    )
    args = parser.parse_args()

    # Resolve feeds config path
    feeds_config = None
    if args.feeds_config:
        feeds_config = Path(args.feeds_config)
    elif args.budget is not None:
        # Auto-detect feeds.yaml when budget is enabled
        default_feeds = Path(__file__).resolve().parents[1] / "config" / "feeds.yaml"
        if default_feeds.exists():
            feeds_config = default_feeds

    count = build_docpack(
        db_path=Path(args.db),
        target_date=args.date,
        max_docs=args.max_docs,
        output_dir=Path(args.output_dir),
        all_docs=args.all,
        label=args.label,
        budget=args.budget,
        stretch_max=args.stretch_max,
        feeds_config=feeds_config,
    )

    return 0 if count >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
