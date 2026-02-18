from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path
from typing import Optional

import feedparser
import requests

from config import load_feeds
from util import (
    clean_html,
    parse_entry_date,
    sha256_text,
    short_hash,
    slugify,
    utc_now_iso,
)

# Default inter-request delay (seconds).
# 5s is polite (each feed hits a different server) while keeping
# total run time within the pipeline timeout for 12+ feeds.
DEFAULT_DELAY = 5.0


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_default_config_path() -> Path:
    """Return default path to feeds.yaml config."""
    return repo_root() / "config" / "feeds.yaml"


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


def fetch_once(
    session: requests.Session,
    url: str,
    timeout: int,
) -> requests.Response:
    """Fetch a URL once.  No retries — if it fails, log and move on.

    This is a daily batch job processing ~20 articles.  Retries add
    complexity and can trigger CDN-level throttling that cascades to
    other feeds.  A failed article can be retried tomorrow.
    """
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp


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
    delay: float = DEFAULT_DELAY,
) -> tuple[int, int, int, bool]:
    """Ingest a single RSS/Atom feed.

    Returns:
        Tuple of (fetched, skipped, errors, reachable).
        reachable is True if the feed XML was successfully fetched and parsed.
    """
    feed = feedparser.parse(feed_url)

    # Diagnostic info for every feed
    feed_status = getattr(feed, "status", None)
    bozo = getattr(feed, "bozo", False)
    bozo_exc = getattr(feed, "bozo_exception", None)
    n_entries = len(feed.entries)
    print(
        f"    [diag] url={feed_url} status={feed_status} bozo={bozo} entries={n_entries}",
        file=sys.stderr,
    )
    if bozo and bozo_exc:
        print(
            f"    [diag] bozo_exception={type(bozo_exc).__name__}: {bozo_exc}",
            file=sys.stderr,
        )

    # Determine if the feed was actually reachable
    reachable = True
    if bozo and not feed.entries:
        exc_name = type(bozo_exc).__name__ if bozo_exc else "unknown"
        print(f"    Feed unreachable: {exc_name}: {bozo_exc}", file=sys.stderr)
        reachable = False
    if feed_status and feed_status >= 400:
        print(f"    Feed HTTP {feed_status}: {feed_url}", file=sys.stderr)
        reachable = False

    source = source_override or feed.feed.get("title") or feed_url
    entries = feed.entries[:limit] if limit > 0 else feed.entries

    fetched = 0
    skipped = 0
    errors = 0

    for i, entry in enumerate(entries):
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

        # Polite delay before each request (skip before the very first)
        if delay > 0 and i > 0:
            time.sleep(delay)

        status = "error"
        error = None
        content_hash = None

        try:
            resp = fetch_once(session, url, timeout)
            raw_path.write_bytes(resp.content)

            text = clean_html(resp.text)
            text_path.write_text(text + "\n", encoding="utf-8")
            content_hash = sha256_text(text)
            status = "cleaned"
        except requests.RequestException as exc:
            error = f"request_error: {exc}"
            errors += 1
            print(f"    [skip] {error[:90]}  url={url[:80]}", file=sys.stderr)
        except OSError as exc:
            error = f"io_error: {exc}"
            errors += 1
            print(f"    [skip] {error[:90]}  url={url[:80]}", file=sys.stderr)

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

    return fetched, skipped, errors, reachable


def build_arg_parser() -> argparse.ArgumentParser:
    """Build argument parser for RSS ingestion CLI."""
    parser = argparse.ArgumentParser(
        description="Ingest RSS feeds into raw and text archives."
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to feeds.yaml config file (default: config/feeds.yaml if exists).",
    )
    parser.add_argument(
        "--feed",
        action="append",
        default=None,
        help="RSS/Atom feed URL (can be repeated). Adds to config feeds if both specified.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max items per feed (0 = all).",
    )
    parser.add_argument(
        "--raw-dir",
        default=None,
        help="Override raw output directory.",
    )
    parser.add_argument(
        "--text-dir",
        default=None,
        help="Override text output directory.",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite database (default data/db/predictor.db). Use '-' to disable.",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help="Path to schema SQL (default schemas/sqlite.sql).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout seconds.",
    )
    parser.add_argument(
        "--user-agent",
        default="predictor-ingest/0.1",
        help="HTTP User-Agent.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip if raw/text already exists.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Seconds to wait between article fetches (default: {DEFAULT_DELAY}).",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Override source name for all feeds.",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    """Validate parsed arguments.

    Raises:
        SystemExit: If validation fails
    """
    if not args.config and not args.feed:
        # Check if default config exists
        default_config = get_default_config_path()
        if default_config.exists():
            args.config = str(default_config)
        else:
            print(
                "Error: Must specify --config or --feed (or create config/feeds.yaml)",
                file=sys.stderr,
            )
            raise SystemExit(1)


def get_feeds_from_args(args: argparse.Namespace) -> list[tuple[str, Optional[str], int]]:
    """Get list of (feed_url, source_name, per_feed_limit) from args.

    Args:
        args: Parsed arguments

    Returns:
        List of (url, source_name, limit) tuples. source_name is None for CLI feeds.
        limit is 0 (unlimited) for CLI feeds.
    """
    feeds: list[tuple[str, Optional[str], int]] = []

    # Load from config file
    if args.config:
        config_path = Path(args.config)
        config_feeds = load_feeds(config_path)
        for feed in config_feeds:
            feeds.append((feed.url, feed.name, feed.limit))

    # Add CLI feeds (no per-feed limit)
    if args.feed:
        for url in args.feed:
            feeds.append((url, None, 0))

    return feeds


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    validate_args(args)

    repo = repo_root()
    # Use CWD-relative paths for data dirs (consistent with --db which is also
    # CWD-relative when passed from Makefile/pipeline). This avoids a mismatch
    # when pip install -e was done from a different directory than the deployment.
    raw_dir = Path(args.raw_dir) if args.raw_dir else Path("data") / "raw"
    text_dir = Path(args.text_dir) if args.text_dir else Path("data") / "text"
    raw_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    if args.db is None:
        db_path = Path("data") / "db" / "predictor.db"
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

    feeds = get_feeds_from_args(args)
    if not feeds:
        print("No feeds to ingest.", file=sys.stderr)
        return 1

    print(f"Ingesting {len(feeds)} feed(s)...")

    total_fetched = 0
    total_skipped = 0
    total_errors = 0
    total_reachable = 0

    for feed_idx, (feed_url, feed_name, feed_limit) in enumerate(feeds):
        # Use feed name from config, or CLI --source override, or let ingest_feed detect
        source = args.source or feed_name

        # CLI --limit overrides per-feed config limit; otherwise use per-feed limit
        effective_limit = args.limit if args.limit > 0 else feed_limit

        # No inter-feed delay: each feed is a different server, so the
        # per-article delay within ingest_feed() is sufficient for politeness.

        limit_info = f" (limit {effective_limit})" if effective_limit > 0 else ""
        print(f"  Processing feed: {feed_name or feed_url}{limit_info}")

        try:
            fetched, skipped, errors, reachable = ingest_feed(
                feed_url=feed_url,
                session=session,
                raw_dir=raw_dir,
                text_dir=text_dir,
                conn=conn,
                repo=repo,
                source_override=source,
                limit=effective_limit,
                timeout=args.timeout,
                skip_existing=args.skip_existing,
                delay=args.delay,
            )
        except Exception as exc:
            print(f"    Feed CRASHED: {type(exc).__name__}: {exc}", file=sys.stderr)
            print(f"    Feed CRASHED: {feed_name or feed_url}")
            total_errors += 1
            continue

        total_fetched += fetched
        total_skipped += skipped
        total_errors += errors
        if reachable:
            total_reachable += 1

        if not reachable:
            print(f"    Feed UNREACHABLE: {feed_name or feed_url}")
        elif errors == 0:
            print(f"    Feed OK: {fetched} new documents, {skipped} duplicates skipped")
        else:
            print(f"    Feed errors: {errors} fetch errors, {fetched} saved, {skipped} duplicates skipped")

    if conn is not None:
        conn.close()

    print(
        f"Fetched {total_fetched} items, skipped {total_skipped}, errors {total_errors}. "
        f"Feeds reachable: {total_reachable}/{len(feeds)}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
