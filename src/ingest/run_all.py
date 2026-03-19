"""Unified ingest orchestrator — routes all feed types through dispatch.

Replaces the previous approach of calling `python -m ingest.rss` directly,
which could only process RSS/Atom feeds. This module reads feeds.yaml,
groups feeds by type, and routes each to the appropriate fetcher via
the dispatch registry.

Usage:
    python -m ingest.run_all --config domains/film/feeds.yaml --db data/db/film.db
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from config import load_feeds
from ingest.rss import (
    open_db,
    repo_root,
    ingest_feed,
)

# Feed types handled by the RSS module (feedparser-based).
_RSS_TYPES = {"rss", "atom"}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest all feed types.")
    parser.add_argument("--config", required=True, help="Path to feeds.yaml")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--skip-existing", action="store_true", default=False)
    parser.add_argument("--limit", type=int, default=0,
                        help="Override per-feed limit (0 = use config)")
    parser.add_argument("--timeout", type=int, default=30,
                        help="HTTP timeout in seconds")
    parser.add_argument("--delay", type=float, default=5.0,
                        help="Delay between article fetches (RSS only)")
    parser.add_argument("--user-agent", default="predictor-ingest/0.1")
    parser.add_argument("--schema", default=None,
                        help="Path to SQLite schema file")
    return parser


def _load_dotenv() -> None:
    """Load .env from project root if it exists (for BSKY/Reddit credentials)."""
    import os
    env_path = Path(__file__).resolve().parents[2] / ".env"
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


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    feeds = load_feeds(config_path)
    if not feeds:
        print("No feeds to ingest.", file=sys.stderr)
        return 1

    repo = repo_root()
    from util.paths import get_raw_dir, get_text_dir
    raw_dir = get_raw_dir()
    text_dir = get_text_dir()
    raw_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    db_path = Path(args.db)
    schema_path = Path(args.schema) if args.schema else repo / "schemas" / "sqlite.sql"
    conn = open_db(db_path, schema_path)

    import requests
    session = requests.Session()
    session.headers.update({"User-Agent": args.user_agent})

    n_feeds = len(feeds)
    print(f"Ingesting {n_feeds} feed(s)...", flush=True)
    ingest_start = time.monotonic()

    total_fetched = 0
    total_skipped = 0
    total_errors = 0
    total_reachable = 0

    for idx, feed in enumerate(feeds):
        effective_limit = args.limit if args.limit > 0 else feed.limit
        limit_info = f" (limit {effective_limit})" if effective_limit > 0 else ""
        elapsed = time.monotonic() - ingest_start
        print(f"  [{idx+1}/{n_feeds}] Processing feed: "
              f"{feed.name}{limit_info}  (elapsed {elapsed:.0f}s)", flush=True)

        feed_type = feed.type.lower()

        if feed_type in _RSS_TYPES:
            if not feed.url:
                print(f"    Feed CRASHED: RSS/Atom feed '{feed.name}' has no url",
                      file=sys.stderr, flush=True)
                print(f"    Feed CRASHED: {feed.name}", flush=True)
                total_errors += 1
                continue
            try:
                fetched, skipped, errors, reachable = ingest_feed(
                    feed_url=feed.url,
                    session=session,
                    raw_dir=raw_dir,
                    text_dir=text_dir,
                    conn=conn,
                    repo=repo,
                    source_override=feed.name,
                    limit=effective_limit,
                    timeout=args.timeout,
                    skip_existing=args.skip_existing,
                    delay=args.delay,
                    feed_index=idx + 1,
                    feed_total=n_feeds,
                )
            except Exception as exc:
                print(f"    Feed CRASHED: {type(exc).__name__}: {exc}",
                      file=sys.stderr, flush=True)
                print(f"    Feed CRASHED: {feed.name}", flush=True)
                total_errors += 1
                continue

            total_fetched += fetched
            total_skipped += skipped
            total_errors += errors
            if reachable:
                total_reachable += 1

            if not reachable:
                print(f"    Feed UNREACHABLE: {feed.name}", flush=True)
            elif errors == 0:
                print(f"    Feed OK: {fetched} new documents, {skipped} duplicates skipped",
                      flush=True)
            else:
                print(f"    Feed errors: {errors} fetch errors, {fetched} saved, "
                      f"{skipped} duplicates skipped", flush=True)

        elif feed_type == "bluesky":
            try:
                from ingest.bluesky import ingest_bluesky
                # Build feed_config dict from FeedConfig + extra fields
                feed_config = {
                    "name": feed.name,
                    "limit": effective_limit,
                    **feed.extra,
                }
                fetched, skipped, errors = ingest_bluesky(
                    feed_config=feed_config,
                    conn=conn,
                    raw_dir=raw_dir,
                    text_dir=text_dir,
                    repo=repo,
                    skip_existing=args.skip_existing,
                )
                total_fetched += fetched
                total_skipped += skipped
                total_errors += errors
                if fetched > 0 or skipped > 0:
                    total_reachable += 1
                    print(f"    Feed OK: {fetched} new documents, {skipped} duplicates skipped",
                          flush=True)
                elif errors == 0:
                    total_reachable += 1
                    print(f"    Feed OK: 0 new documents, 0 duplicates skipped", flush=True)
                else:
                    print(f"    Feed errors: {errors} errors, {fetched} saved", flush=True)
            except Exception as exc:
                print(f"    Feed CRASHED: {type(exc).__name__}: {exc}",
                      file=sys.stderr, flush=True)
                print(f"    Feed CRASHED: {feed.name}", flush=True)
                total_errors += 1

        elif feed_type == "reddit":
            try:
                from ingest.reddit import ingest_reddit
                feed_config = {
                    "name": feed.name,
                    "limit": effective_limit,
                    **feed.extra,
                }
                fetched, skipped, errors = ingest_reddit(
                    feed_config=feed_config,
                    conn=conn,
                    raw_dir=raw_dir,
                    text_dir=text_dir,
                    repo=repo,
                    skip_existing=args.skip_existing,
                )
                total_fetched += fetched
                total_skipped += skipped
                total_errors += errors
                if fetched > 0 or skipped > 0:
                    total_reachable += 1
                    print(f"    Feed OK: {fetched} new documents, {skipped} duplicates skipped",
                          flush=True)
                elif errors == 0:
                    total_reachable += 1
                    print(f"    Feed OK: 0 new documents, 0 duplicates skipped", flush=True)
                else:
                    print(f"    Feed errors: {errors} errors, {fetched} saved", flush=True)
            except Exception as exc:
                print(f"    Feed CRASHED: {type(exc).__name__}: {exc}",
                      file=sys.stderr, flush=True)
                print(f"    Feed CRASHED: {feed.name}", flush=True)
                total_errors += 1

        else:
            print(f"    Feed SKIPPED: unknown feed type '{feed_type}'",
                  file=sys.stderr, flush=True)
            total_errors += 1

    conn.close()

    total_sec = time.monotonic() - ingest_start
    print(
        f"Fetched {total_fetched} items, skipped {total_skipped}, errors {total_errors}. "
        f"Feeds reachable: {total_reachable}/{n_feeds}. Total time: {total_sec:.1f}s.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
