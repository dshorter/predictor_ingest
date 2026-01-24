from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import feedparser
import requests

from util import (
    clean_html,
    parse_entry_date,
    sha256_text,
    short_hash,
    slugify,
    utc_now_iso,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def open_db(db_path: Path, schema_path: Optional[Path]) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    if schema_path and schema_path.exists():
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
    return conn


def upsert_document(
    conn: sqlite3.Connection,
    doc_id: str,
    url: str,
    source: str,
    title: str,
    published_at: Optional[str],
    fetched_at: str,
    raw_path: Optional[str],
    text_path: Optional[str],
    content_hash: Optional[str],
    status: str,
    error: Optional[str],
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO documents (
            doc_id,
            url,
            source,
            title,
            published_at,
            fetched_at,
            raw_path,
            text_path,
            content_hash,
            status,
            error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc_id,
            url,
            source,
            title,
            published_at,
            fetched_at,
            raw_path,
            text_path,
            content_hash,
            status,
            error,
        ),
    )


def ingest_feed(
    feed_url: str,
    session: requests.Session,
    raw_dir: Path,
    text_dir: Path,
    conn: Optional[sqlite3.Connection],
    repo: Path,
    source_override: Optional[str],
    limit: int,
    timeout: int,
    skip_existing: bool,
) -> tuple[int, int, int]:
    feed = feedparser.parse(feed_url)
    if getattr(feed, "bozo", False):
        print(f"Warning: feed parse issue for {feed_url}: {feed.bozo_exception}", file=sys.stderr)

    source = source_override or feed.feed.get("title") or feed_url
    entries = feed.entries[:limit] if limit > 0 else feed.entries

    fetched = 0
    skipped = 0
    errors = 0

    for entry in entries:
        url = entry.get("link")
        if not url:
            errors += 1
            print(f"Warning: missing link in feed entry from {feed_url}", file=sys.stderr)
            continue

        title = entry.get("title") or ""
        published_at = parse_entry_date(entry)
        fetched_at = utc_now_iso()
        date_part = published_at or fetched_at[:10]

        doc_id = f"{date_part}_{slugify(source)}_{short_hash(url)}"
        raw_path = raw_dir / f"{doc_id}.html"
        text_path = text_dir / f"{doc_id}.txt"

        if skip_existing and raw_path.exists() and text_path.exists():
            skipped += 1
            continue

        status = "error"
        error = None
        content_hash = None

        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            raw_path.write_bytes(resp.content)

            text = clean_html(resp.text)
            text_path.write_text(text + "\n", encoding="utf-8")
            content_hash = sha256_text(text)
            status = "cleaned"
        except requests.RequestException as exc:
            error = f"request_error: {exc}"
            errors += 1
        except OSError as exc:
            error = f"io_error: {exc}"
            errors += 1

        if conn is not None:
            upsert_document(
                conn,
                doc_id=doc_id,
                url=url,
                source=source,
                title=title,
                published_at=published_at,
                fetched_at=fetched_at,
                raw_path=rel_path(raw_path, repo) if raw_path.exists() else None,
                text_path=rel_path(text_path, repo) if text_path.exists() else None,
                content_hash=content_hash,
                status=status,
                error=error,
            )

        fetched += 1

    if conn is not None:
        conn.commit()

    return fetched, skipped, errors


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest RSS feeds into raw and text archives.")
    parser.add_argument("--feed", action="append", required=True, help="RSS/Atom feed URL.")
    parser.add_argument("--limit", type=int, default=0, help="Max items per feed (0 = all).")
    parser.add_argument("--raw-dir", default=None, help="Override raw output directory.")
    parser.add_argument("--text-dir", default=None, help="Override text output directory.")
    parser.add_argument(
        "--db",
        default=None,
        help="Path to sqlite db (default data/db/ingest.sqlite). Use '-' to disable.",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help="Path to schema SQL (default schemas/sqlite.sql).",
    )
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds.")
    parser.add_argument("--user-agent", default="predictor-ingest/0.1", help="HTTP User-Agent.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip if raw/text already exists.")
    parser.add_argument("--source", default=None, help="Override source name for all feeds.")
    args = parser.parse_args(argv)

    repo = repo_root()
    raw_dir = Path(args.raw_dir) if args.raw_dir else repo / "data" / "raw"
    text_dir = Path(args.text_dir) if args.text_dir else repo / "data" / "text"
    raw_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    if args.db is None:
        db_path = repo / "data" / "db" / "ingest.sqlite"
    elif args.db == "-":
        db_path = None
    else:
        db_path = Path(args.db)

    if args.schema is None:
        schema_path = repo / "schemas" / "sqlite.sql"
    else:
        schema_path = Path(args.schema)

    conn = open_db(db_path, schema_path) if db_path else None

    session = requests.Session()
    session.headers.update({"User-Agent": args.user_agent})

    total_fetched = 0
    total_skipped = 0
    total_errors = 0

    for feed_url in args.feed:
        fetched, skipped, errors = ingest_feed(
            feed_url=feed_url,
            session=session,
            raw_dir=raw_dir,
            text_dir=text_dir,
            conn=conn,
            repo=repo,
            source_override=args.source,
            limit=args.limit,
            timeout=args.timeout,
            skip_existing=args.skip_existing,
        )
        total_fetched += fetched
        total_skipped += skipped
        total_errors += errors

    if conn is not None:
        conn.close()

    print(
        f"Fetched {total_fetched} items, skipped {total_skipped}, errors {total_errors}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
