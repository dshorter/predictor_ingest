"""Diagnostic: check each feed for new vs already-fetched articles.

Run on VPS:
    python scripts/diagnose_feeds.py
    python scripts/diagnose_feeds.py --domain biosafety

Shows per-feed breakdown of:
- Total entries in feed right now
- How many already have files on disk (would be skipped)
- How many are genuinely new
- The published dates of new entries
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import feedparser
from config import load_feeds
from util import parse_entry_date, short_hash, slugify, utc_now_iso
from util.paths import _resolve_domain, get_raw_dir, get_text_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose feed freshness vs already-fetched articles."
    )
    parser.add_argument("--domain", default=None,
                        help="Domain slug (default: ai or PREDICTOR_DOMAIN env var)")
    args = parser.parse_args()

    domain = _resolve_domain(args.domain)

    # Prefer domain-specific feeds config; fall back to legacy
    config_path = Path("domains") / domain / "feeds.yaml"
    if not config_path.exists():
        config_path = Path("config/feeds.yaml")
    if not config_path.exists():
        config_path = Path(__file__).resolve().parents[1] / "config" / "feeds.yaml"

    feeds = load_feeds(config_path)
    raw_dir = get_raw_dir(domain)
    text_dir = get_text_dir(domain)

    print(f"Diagnostic run at {utc_now_iso()} (domain: {domain})")
    print(f"raw_dir: {raw_dir.resolve()} (exists={raw_dir.exists()})")
    print(f"text_dir: {text_dir.resolve()} (exists={text_dir.exists()})")
    print()

    total_new = 0
    total_existing = 0
    total_entries = 0

    for feed_cfg in feeds:
        if not feed_cfg.enabled:
            print(f"[DISABLED] {feed_cfg.name}: {feed_cfg.url}")
            print()
            continue

        print(f"--- {feed_cfg.name} ---")
        print(f"    URL: {feed_cfg.url}")

        try:
            feed = feedparser.parse(feed_cfg.url)
        except Exception as e:
            print(f"    ERROR parsing feed: {e}")
            print()
            continue

        status = getattr(feed, "status", None)
        bozo = getattr(feed, "bozo", False)
        entries = feed.entries[:feed_cfg.limit] if feed_cfg.limit > 0 else feed.entries

        print(f"    HTTP status: {status}, bozo: {bozo}, entries: {len(entries)}")

        new_entries = []
        existing_entries = []

        for entry in entries:
            url = entry.get("link", "")
            if not url:
                continue

            published_at = parse_entry_date(entry)
            fetched_at = utc_now_iso()
            date_part = published_at or fetched_at[:10]
            source = feed_cfg.name

            doc_id = f"{date_part}_{slugify(source)}_{short_hash(url)}"
            raw_path = raw_dir / f"{doc_id}.html"
            text_path = text_dir / f"{doc_id}.txt"

            raw_exists = raw_path.exists()
            text_exists = text_path.exists()

            title = entry.get("title", "")[:70]

            if raw_exists and text_exists:
                existing_entries.append((date_part, title, doc_id))
            else:
                new_entries.append((date_part, title, doc_id, raw_exists, text_exists))

        total_entries += len(entries)
        total_existing += len(existing_entries)
        total_new += len(new_entries)

        print(f"    Existing (would skip): {len(existing_entries)}")
        print(f"    NEW (would fetch):     {len(new_entries)}")

        if new_entries:
            for date_part, title, doc_id, raw_ex, text_ex in new_entries[:5]:
                partial = ""
                if raw_ex and not text_ex:
                    partial = " [raw exists, text missing]"
                elif not raw_ex and text_ex:
                    partial = " [raw missing, text exists]"
                print(f"      NEW: {date_part} | {title}")
                print(f"           doc_id: {doc_id}{partial}")
            if len(new_entries) > 5:
                print(f"      ... and {len(new_entries) - 5} more")

        # Show date distribution of existing entries
        if existing_entries:
            dates = {}
            for date_part, _, _ in existing_entries:
                dates[date_part] = dates.get(date_part, 0) + 1
            sorted_dates = sorted(dates.items())
            date_str = ", ".join(f"{d}({c})" for d, c in sorted_dates)
            print(f"    Existing by date: {date_str}")

        print()

    print("=" * 60)
    print(f"TOTAL: {total_entries} entries across all feeds")
    print(f"  Existing (skip): {total_existing}")
    print(f"  New (fetch):     {total_new}")

    if total_new == 0 and total_entries > 0:
        print()
        print("WARNING: Zero new articles found. Possible causes:")
        print("  1. Pipeline ran recently and all current feed entries are already fetched")
        print("  2. Feeds are stale or caching old results")
        print(f"  3. File paths in {raw_dir}/ and {text_dir}/ don't match expected layout")
        print()
        print(f"Check: ls {raw_dir}/ | wc -l    (should match ~document count)")
        print(f"Check: ls {raw_dir}/ | tail -5  (show most recent files)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
