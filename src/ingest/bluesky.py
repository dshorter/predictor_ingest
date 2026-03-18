"""Bluesky ingest fetcher — polls the search API for keyword-matched posts.

Authenticates via AT Protocol session (BSKY_HANDLE + BSKY_APP_PASSWORD env vars).
Falls back to the public AppView endpoint, which may return 403 for search.

Authenticated requests go through the PDS (bsky.social), which proxies to the
AppView.  See: https://docs.bsky.app/docs/advanced-guides/api-directory

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

# Endpoints
PDS_HOST = "https://bsky.social"
PUBLIC_HOST = "https://public.api.bsky.app"
SEARCH_PATH = "/xrpc/app.bsky.feed.searchPosts"
CREATE_SESSION_PATH = "/xrpc/com.atproto.server.createSession"
REFRESH_SESSION_PATH = "/xrpc/com.atproto.server.refreshSession"

# Rate limit: ~3,000 requests per 5 minutes.  We're polite: 200ms between requests.
REQUEST_DELAY = 0.2

# Default keywords for Southeast film domain (overridden by feed config).
DEFAULT_KEYWORDS = [
    "indie film Georgia",
    "Atlanta film production",
    "Trilith Studios",
    "Southeast film",
]


def sha256_text(text: str) -> str:
    """SHA-256 hash of text for dedup."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _post_to_doc(post: dict, feed_name: str) -> dict:
    """Map a Bluesky post to a document dict.

    Args:
        post: A post object from the searchPosts response.
        feed_name: Name of the feed config entry (for the source field).

    Returns:
        Dict with fields matching upsert_document() parameters.
    """
    # Extract fields from the AT Protocol post structure
    uri = post.get("uri", "")
    author = post.get("author", {})
    record = post.get("record", {})

    handle = author.get("handle", "unknown")
    display_name = author.get("displayName", handle)
    text = record.get("text", "")
    created_at = record.get("createdAt", "")

    # Build a web URL from the AT URI: at://did:plc:xxx/app.bsky.feed.post/yyy
    # → https://bsky.app/profile/{handle}/post/{rkey}
    rkey = uri.rsplit("/", 1)[-1] if "/" in uri else uri
    web_url = f"https://bsky.app/profile/{handle}/post/{rkey}"

    # Title: first line of post, truncated
    first_line = text.split("\n")[0][:120] if text else "(no text)"
    title = f"@{handle}: {first_line}"

    # Normalize created_at to ISO date
    published_at = None
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            published_at = dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass

    content_hash = sha256_text(text) if text else None

    # Build a doc_id from the AT URI (stable, unique)
    # at://did:plc:abc123/app.bsky.feed.post/xyz → bsky_abc123_xyz
    did_part = uri.split("/")[2].split(":")[-1][:12] if "://" in uri else "unknown"
    doc_id = f"bsky_{did_part}_{rkey}"

    return {
        "doc_id": doc_id,
        "url": web_url,
        "source": feed_name,
        "source_type": "bluesky",
        "title": title,
        "text": text,
        "published_at": published_at,
        "content_hash": content_hash,
        "author_handle": handle,
        "author_name": display_name,
        "like_count": post.get("likeCount", 0),
        "repost_count": post.get("repostCount", 0),
        "reply_count": post.get("replyCount", 0),
    }


def _create_session() -> tuple[Optional[str], Optional[str]]:
    """Authenticate with Bluesky via AT Protocol createSession.

    Reads BSKY_HANDLE and BSKY_APP_PASSWORD from environment.

    Returns:
        Tuple of (accessJwt, refreshJwt), or (None, None) if auth unavailable.
    """
    handle = os.environ.get("BSKY_HANDLE")
    password = os.environ.get("BSKY_APP_PASSWORD")

    if not handle or not password:
        return None, None

    try:
        resp = requests.post(
            f"{PDS_HOST}{CREATE_SESSION_PATH}",
            json={"identifier": handle, "password": password},
            headers={"User-Agent": "predictor-ingest/0.1"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("accessJwt"), data.get("refreshJwt")
    except requests.RequestException as exc:
        print(f"  [bluesky] auth failed: {exc}", file=sys.stderr, flush=True)
        return None, None


def _make_session() -> tuple[requests.Session, str]:
    """Create a requests session with Bluesky auth if credentials are available.

    Returns:
        Tuple of (session, search_endpoint_url).
        Authenticated sessions use the PDS host; unauthenticated use the public host.
    """
    session = requests.Session()
    session.headers["User-Agent"] = "predictor-ingest/0.1"

    access_jwt, _ = _create_session()
    if access_jwt:
        session.headers["Authorization"] = f"Bearer {access_jwt}"
        print("  [bluesky] authenticated via BSKY_HANDLE", flush=True)
        return session, f"{PDS_HOST}{SEARCH_PATH}"

    print("  [bluesky] no credentials (BSKY_HANDLE not set), using public API",
          flush=True)
    return session, f"{PUBLIC_HOST}{SEARCH_PATH}"


def search_posts(
    query: str,
    limit: int = 50,
    sort: str = "latest",
    since: Optional[str] = None,
    until: Optional[str] = None,
    session: Optional[requests.Session] = None,
    endpoint: Optional[str] = None,
) -> list[dict]:
    """Search Bluesky posts via the AT Protocol search API.

    Args:
        query: Search query (Lucene syntax supported).
        limit: Max results per request (API max is 100).
        sort: "latest" or "top".
        since: ISO datetime string for start of date range.
        until: ISO datetime string for end of date range.
        session: Optional requests session for connection reuse.
        endpoint: Full URL for searchPosts endpoint.

    Returns:
        List of post objects from the API response.
    """
    if session is None or endpoint is None:
        session, endpoint = _make_session()

    params: dict = {
        "q": query,
        "limit": min(limit, 100),
        "sort": sort,
    }
    if since:
        params["since"] = since
    if until:
        params["until"] = until

    all_posts: list[dict] = []
    cursor: Optional[str] = None
    pages = 0
    max_pages = (limit // 100) + 1  # Don't paginate forever

    while pages < max_pages:
        if cursor:
            params["cursor"] = cursor

        resp = session.get(endpoint, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        posts = data.get("posts", [])
        if not posts:
            break

        all_posts.extend(posts)
        cursor = data.get("cursor")
        pages += 1

        if not cursor or len(all_posts) >= limit:
            break

        time.sleep(REQUEST_DELAY)

    return all_posts[:limit]


def ingest_bluesky(
    feed_config: dict,
    conn,
    raw_dir: Path,
    text_dir: Path,
    repo: Path,
    skip_existing: bool = True,
) -> tuple[int, int, int]:
    """Ingest posts from Bluesky search for a feed config entry.

    Args:
        feed_config: Dict from feeds.yaml with keys: name, keywords, limit, etc.
        conn: SQLite database connection.
        raw_dir: Directory for raw content storage.
        text_dir: Directory for cleaned text storage.
        repo: Repository root path.
        skip_existing: Skip posts already in the database.

    Returns:
        Tuple of (fetched, skipped, errors).
    """
    feed_name = feed_config.get("name", "Bluesky")
    keywords = feed_config.get("keywords", DEFAULT_KEYWORDS)
    limit_per_keyword = feed_config.get("limit", 25)

    session, endpoint = _make_session()

    fetched = 0
    skipped = 0
    errors = 0
    seen_uris: set[str] = set()

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"  [bluesky] {feed_name}: searching {len(keywords)} keyword queries", flush=True)

    for keyword in keywords:
        try:
            posts = search_posts(
                query=keyword,
                limit=limit_per_keyword,
                sort="latest",
                session=session,
                endpoint=endpoint,
            )
        except requests.RequestException as exc:
            print(f"  [bluesky] FAIL query='{keyword}': {exc}", file=sys.stderr, flush=True)
            errors += 1
            continue

        print(f"  [bluesky] query='{keyword}': {len(posts)} posts", flush=True)

        for post in posts:
            uri = post.get("uri", "")
            if uri in seen_uris:
                continue
            seen_uris.add(uri)

            doc = _post_to_doc(post, feed_name)

            # Skip existing documents
            if skip_existing and conn is not None:
                existing = conn.execute(
                    "SELECT 1 FROM documents WHERE doc_id = ?", (doc["doc_id"],)
                ).fetchone()
                if existing:
                    skipped += 1
                    continue

            # Write raw text to files
            text = doc.pop("text", "")
            doc.pop("author_handle", None)
            doc.pop("author_name", None)
            doc.pop("like_count", None)
            doc.pop("repost_count", None)
            doc.pop("reply_count", None)

            raw_path = raw_dir / f"{doc['doc_id']}.txt"
            text_path = text_dir / f"{doc['doc_id']}.txt"

            try:
                raw_path.write_text(text, encoding="utf-8")
                text_path.write_text(text, encoding="utf-8")
            except OSError as exc:
                print(f"  [bluesky] FAIL write {doc['doc_id']}: {exc}",
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
                    source_type="bluesky",
                )
                conn.commit()

            fetched += 1

        time.sleep(REQUEST_DELAY)

    print(f"  [bluesky] {feed_name}: fetched={fetched}, skipped={skipped}, errors={errors}",
          flush=True)
    return fetched, skipped, errors
