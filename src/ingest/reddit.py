"""Reddit ingest fetcher — polls subreddits for new posts via the JSON API.

Uses Reddit's public JSON endpoints (append .json to any listing URL).
For authenticated access with higher rate limits, set REDDIT_CLIENT_ID and
REDDIT_CLIENT_SECRET environment variables.

Posts are mapped to the standard document schema and stored via upsert_document().
Deduplication is handled by content_hash (SHA-256 of post text).

See ADR-006 for design rationale.
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from ingest.rss import upsert_document

# Unauthenticated JSON endpoint — 10 req/min.  Sufficient for daily polling.
# Authenticated via OAuth2 gets 100 req/min but requires registration.
REDDIT_BASE = "https://www.reddit.com"
OAUTH_BASE = "https://oauth.reddit.com"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"

# Rate limiting: 600ms between requests (conservative for unauth)
REQUEST_DELAY = 0.6

USER_AGENT = "predictor-ingest/0.1 (knowledge-graph pipeline; non-commercial research)"


def sha256_text(text: str) -> str:
    """SHA-256 hash of text for dedup."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _get_oauth_token(client_id: str, client_secret: str) -> Optional[str]:
    """Obtain OAuth2 bearer token for higher rate limits.

    Returns None if authentication fails (falls back to unauth JSON).
    """
    try:
        resp = requests.post(
            TOKEN_URL,
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except (requests.RequestException, KeyError):
        return None


def _make_session() -> tuple[requests.Session, str]:
    """Create a session, using OAuth if credentials are available.

    Returns:
        Tuple of (session, base_url).
    """
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")

    if client_id and client_secret:
        token = _get_oauth_token(client_id, client_secret)
        if token:
            session.headers["Authorization"] = f"Bearer {token}"
            print("  [reddit] authenticated via OAuth (100 req/min)", flush=True)
            return session, OAUTH_BASE
        print("  [reddit] WARNING: OAuth token request failed, falling back to "
              "unauthenticated API", file=sys.stderr, flush=True)
    else:
        print("  [reddit] WARNING: no credentials (REDDIT_CLIENT_ID not set). "
              "Unauthenticated access may return 403. "
              "See https://www.reddit.com/wiki/api/", file=sys.stderr, flush=True)

    return session, REDDIT_BASE


def _post_to_doc(post_data: dict, feed_name: str) -> dict:
    """Map a Reddit post to a document dict.

    Args:
        post_data: The 'data' dict from a Reddit listing child.
        feed_name: Name of the feed config entry (for the source field).

    Returns:
        Dict with fields matching upsert_document() parameters.
    """
    post_id = post_data.get("id", "unknown")
    subreddit = post_data.get("subreddit", "unknown")
    title = post_data.get("title", "(no title)")
    selftext = post_data.get("selftext", "")
    author = post_data.get("author", "[deleted]")
    permalink = post_data.get("permalink", "")
    created_utc = post_data.get("created_utc", 0)
    score = post_data.get("score", 0)
    num_comments = post_data.get("num_comments", 0)
    is_self = post_data.get("is_self", True)
    link_url = post_data.get("url", "")

    # Build full text: title + selftext for self posts, title + link for link posts
    if is_self and selftext:
        full_text = f"{title}\n\n{selftext}"
    elif not is_self:
        full_text = f"{title}\n\n[Link: {link_url}]"
    else:
        full_text = title

    # Web URL
    web_url = f"https://www.reddit.com{permalink}" if permalink else link_url

    # Normalize timestamp
    published_at = None
    if created_utc:
        try:
            dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)
            published_at = dt.strftime("%Y-%m-%d")
        except (ValueError, OSError):
            pass

    content_hash = sha256_text(full_text) if full_text else None
    doc_id = f"reddit_{subreddit}_{post_id}"

    return {
        "doc_id": doc_id,
        "url": web_url,
        "source": feed_name,
        "source_type": "reddit",
        "title": f"r/{subreddit}: {title[:100]}",
        "text": full_text,
        "published_at": published_at,
        "content_hash": content_hash,
        "score": score,
        "num_comments": num_comments,
    }


def fetch_subreddit(
    subreddit: str,
    listing: str = "new",
    limit: int = 25,
    session: Optional[requests.Session] = None,
    base_url: str = REDDIT_BASE,
) -> list[dict]:
    """Fetch posts from a subreddit listing.

    Args:
        subreddit: Subreddit name (without r/ prefix). Can be multireddit: "Atlanta+Filmmakers"
        listing: One of "new", "hot", "top", "rising".
        limit: Max posts to fetch (Reddit caps at 100 per request).
        session: Optional requests session.
        base_url: Reddit base URL (changes for OAuth).

    Returns:
        List of post data dicts.
    """
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

    url = f"{base_url}/r/{subreddit}/{listing}.json"
    params = {"limit": min(limit, 100), "raw_json": 1}

    all_posts: list[dict] = []
    after: Optional[str] = None
    pages = 0
    max_pages = (limit // 100) + 1

    while pages < max_pages:
        if after:
            params["after"] = after

        resp = session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        children = data.get("data", {}).get("children", [])
        if not children:
            break

        for child in children:
            if child.get("kind") == "t3":  # t3 = link/post
                all_posts.append(child["data"])

        after = data.get("data", {}).get("after")
        pages += 1

        if not after or len(all_posts) >= limit:
            break

        time.sleep(REQUEST_DELAY)

    return all_posts[:limit]


def ingest_reddit(
    feed_config: dict,
    conn,
    raw_dir: Path,
    text_dir: Path,
    repo: Path,
    skip_existing: bool = True,
) -> tuple[int, int, int]:
    """Ingest posts from Reddit for a feed config entry.

    Args:
        feed_config: Dict from feeds.yaml with keys: name, subreddit, limit, etc.
        conn: SQLite database connection.
        raw_dir: Directory for raw content storage.
        text_dir: Directory for cleaned text storage.
        repo: Repository root path.
        skip_existing: Skip posts already in the database.

    Returns:
        Tuple of (fetched, skipped, errors).
    """
    feed_name = feed_config.get("name", "Reddit")
    subreddit = feed_config.get("subreddit", "")
    limit = feed_config.get("limit", 25)
    listing = feed_config.get("listing", "new")

    if not subreddit:
        print(f"  [reddit] {feed_name}: no subreddit configured, skipping",
              file=sys.stderr, flush=True)
        return 0, 0, 1

    session, base_url = _make_session()

    fetched = 0
    skipped = 0
    errors = 0

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"  [reddit] {feed_name}: fetching r/{subreddit}/{listing} (limit={limit})", flush=True)

    try:
        posts = fetch_subreddit(
            subreddit=subreddit,
            listing=listing,
            limit=limit,
            session=session,
            base_url=base_url,
        )
    except requests.RequestException as exc:
        print(f"  [reddit] FAIL r/{subreddit}: {exc}", file=sys.stderr, flush=True)
        return 0, 0, 1

    print(f"  [reddit] r/{subreddit}: {len(posts)} posts", flush=True)

    for post_data in posts:
        doc = _post_to_doc(post_data, feed_name)

        # Skip existing
        if skip_existing and conn is not None:
            existing = conn.execute(
                "SELECT 1 FROM documents WHERE doc_id = ?", (doc["doc_id"],)
            ).fetchone()
            if existing:
                skipped += 1
                continue

        # Write text to files
        text = doc.pop("text", "")
        doc.pop("score", None)
        doc.pop("num_comments", None)

        raw_path = raw_dir / f"{doc['doc_id']}.txt"
        text_path = text_dir / f"{doc['doc_id']}.txt"

        try:
            raw_path.write_text(text, encoding="utf-8")
            text_path.write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"  [reddit] FAIL write {doc['doc_id']}: {exc}",
                  file=sys.stderr, flush=True)
            errors += 1
            continue

        if conn is not None:
            def rel_path(p: Path, base: Path) -> str:
                try:
                    return str(p.relative_to(base))
                except ValueError:
                    return str(p)

            upsert_document(
                conn,
                doc_id=doc["doc_id"],
                url=doc["url"],
                source=doc["source"],
                title=doc["title"],
                published_at=doc["published_at"],
                fetched_at=fetched_at,
                raw_path=rel_path(raw_path, repo),
                text_path=rel_path(text_path, repo),
                content_hash=doc["content_hash"],
                status="cleaned",
                error=None,
                source_type="reddit",
            )
            conn.commit()

        fetched += 1

    print(f"  [reddit] {feed_name}: fetched={fetched}, skipped={skipped}, errors={errors}",
          flush=True)
    return fetched, skipped, errors
