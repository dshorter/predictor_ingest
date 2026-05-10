"""USPTO PatentsView ingest fetcher — searches recent semiconductor patents.

Uses the PatentsView API (api.patentsview.org) to search for recently
published patents by CPC classification codes, keywords, and assignees
relevant to the semiconductor domain.

Patents are mapped to the standard document schema and stored via
upsert_document(). Deduplication is handled by patent number as doc_id.

Environment variables:
    USPTO_API_KEY: Optional API key for higher rate limits.
                   Works without a key at lower throughput.

Rate limit: 45 requests/minute with API key, lower without.

See docs/methodology/deep-research-report.md for rationale.
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests

from ingest.rss import upsert_document

# PatentsView API endpoint
PATENTSVIEW_BASE = "https://api.patentsview.org/patents/query"

# USPTO patent detail URL
PATENT_URL_BASE = "https://patents.google.com/patent"

# Rate limiting: 1.5s between requests (~40 req/min, under 45 limit)
REQUEST_DELAY = 1.5

USER_AGENT = "predictor-ingest/0.1 (knowledge-graph pipeline; non-commercial research)"


def sha256_text(text: str) -> str:
    """SHA-256 hash of text for dedup."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_query(
    cpc_codes: list[str],
    keywords: list[str],
    assignees: list[str],
    days_back: int = 90,
) -> dict:
    """Build a PatentsView API query combining CPC codes, keywords, and assignees.

    Uses an OR across CPC codes, AND with keyword/assignee filters.
    Restricts to patents granted in the last `days_back` days.

    Args:
        cpc_codes: CPC classification prefixes (e.g., ["H01L", "H10B"]).
        keywords: Keywords to search in patent title/abstract.
        assignees: Assignee organization names.
        days_back: How far back to search (default 90 days).

    Returns:
        Query dict for the PatentsView API.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

    # Build CPC filter: OR across codes (prefix match)
    conditions = []

    if cpc_codes:
        cpc_conditions = [
            {"cpc_subgroup_id": code} for code in cpc_codes
        ]
        if len(cpc_conditions) == 1:
            conditions.append(cpc_conditions[0])
        else:
            conditions.append({"_or": cpc_conditions})

    # Date filter: only recent patents
    conditions.append({"_gte": {"patent_date": cutoff}})

    # Keyword filter in title/abstract (OR across keywords)
    if keywords:
        kw_conditions = [
            {"_text_any": {"patent_abstract": kw}} for kw in keywords
        ]
        if len(kw_conditions) == 1:
            conditions.append(kw_conditions[0])
        else:
            conditions.append({"_or": kw_conditions})

    # Assignee filter (OR across assignees)
    if assignees:
        assignee_conditions = [
            {"_contains": {"assignee_organization": a}} for a in assignees
        ]
        if len(assignee_conditions) == 1:
            conditions.append(assignee_conditions[0])
        else:
            conditions.append({"_or": assignee_conditions})

    if len(conditions) == 1:
        return conditions[0]
    return {"_and": conditions}


def fetch_patents(
    cpc_codes: list[str],
    keywords: list[str],
    assignees: list[str],
    limit: int = 25,
    session: Optional[requests.Session] = None,
) -> list[dict]:
    """Fetch recent patents from the PatentsView API.

    Args:
        cpc_codes: CPC classification prefixes.
        keywords: Keywords for title/abstract search.
        assignees: Assignee organization names.
        limit: Max patents to return.
        session: Optional requests session.

    Returns:
        List of patent dicts with keys: patent_number, patent_title,
        patent_abstract, patent_date, assignees, cpc_codes, url.
    """
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

    query = _build_query(cpc_codes, keywords, assignees)

    payload = {
        "q": query,
        "f": [
            "patent_number",
            "patent_title",
            "patent_abstract",
            "patent_date",
            "assignee_organization",
            "cpc_subgroup_id",
        ],
        "o": {
            "page": 1,
            "per_page": min(limit, 100),
        },
        "s": [{"patent_date": "desc"}],
    }

    api_key = os.environ.get("USPTO_API_KEY", "")
    headers = {}
    if api_key:
        headers["X-Api-Key"] = api_key

    try:
        resp = session.post(
            PATENTSVIEW_BASE,
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        print(f"  [patents] FAIL PatentsView query: {exc}",
              file=sys.stderr, flush=True)
        return []

    time.sleep(REQUEST_DELAY)

    patents_raw = data.get("patents", [])
    if not patents_raw:
        return []

    patents = []
    for p in patents_raw:
        patent_number = p.get("patent_number", "")
        if not patent_number:
            continue

        # Collect assignee names
        assignee_list = []
        for a in p.get("assignees", []):
            org = a.get("assignee_organization")
            if org:
                assignee_list.append(org)

        # Collect CPC codes
        cpc_list = []
        for c in p.get("cpcs", []):
            code = c.get("cpc_subgroup_id")
            if code:
                cpc_list.append(code)

        patents.append({
            "patent_number": patent_number,
            "title": p.get("patent_title", "(no title)"),
            "abstract": p.get("patent_abstract", ""),
            "date": p.get("patent_date", ""),
            "assignees": assignee_list,
            "cpc_codes": cpc_list,
            "url": f"{PATENT_URL_BASE}/US{patent_number}",
        })

    return patents[:limit]


def _patent_to_doc(patent: dict, feed_name: str) -> dict:
    """Map a patent to a document dict.

    Args:
        patent: Dict from fetch_patents().
        feed_name: Name of the feed config entry (for the source field).

    Returns:
        Dict with fields matching upsert_document() parameters.
    """
    patent_number = patent["patent_number"]
    title = patent["title"]
    assignees = patent.get("assignees", [])

    doc_id = f"patent_US{patent_number}"

    # Build a richer title with assignee
    display_title = f"US{patent_number}: {title}"
    if assignees:
        display_title += f" ({assignees[0]})"

    # Build full text: title + abstract + metadata
    parts = [display_title, ""]
    if patent.get("abstract"):
        parts.append(patent["abstract"])
    if assignees:
        parts.append(f"\nAssignees: {', '.join(assignees)}")
    if patent.get("cpc_codes"):
        parts.append(f"CPC: {', '.join(patent['cpc_codes'][:5])}")

    full_text = "\n".join(parts)

    return {
        "doc_id": doc_id,
        "url": patent["url"],
        "source": feed_name,
        "source_type": "patents",
        "title": display_title[:200],
        "text": full_text,
        "published_at": patent.get("date"),
    }


def ingest_patents(
    feed_config: dict,
    conn,
    raw_dir: Path,
    text_dir: Path,
    repo: Path,
    skip_existing: bool = True,
) -> tuple[int, int, int]:
    """Ingest patents from USPTO PatentsView for a feed config entry.

    Args:
        feed_config: Dict from feeds.yaml with keys: name, cpc_codes,
                     keywords, assignees, limit.
        conn: SQLite database connection.
        raw_dir: Directory for raw content storage.
        text_dir: Directory for cleaned text storage.
        repo: Repository root path.
        skip_existing: Skip patents already in the database.

    Returns:
        Tuple of (fetched, skipped, errors).
    """
    feed_name = feed_config.get("name", "USPTO Patents")
    cpc_codes = feed_config.get("cpc_codes", [])
    keywords = feed_config.get("keywords", [])
    assignees = feed_config.get("assignees", [])
    limit = feed_config.get("limit", 25)

    if not cpc_codes and not keywords and not assignees:
        print(f"  [patents] {feed_name}: no search criteria configured, skipping",
              file=sys.stderr, flush=True)
        return 0, 0, 1

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    fetched = 0
    skipped = 0
    errors = 0

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"  [patents] {feed_name}: searching CPC={cpc_codes}, "
          f"keywords={len(keywords)}, assignees={len(assignees)}", flush=True)

    patents = fetch_patents(
        cpc_codes=cpc_codes,
        keywords=keywords,
        assignees=assignees,
        limit=limit,
        session=session,
    )

    print(f"  [patents] {feed_name}: {len(patents)} patents found", flush=True)

    for patent in patents:
        doc = _patent_to_doc(patent, feed_name)

        # Skip existing
        if skip_existing and conn is not None:
            existing = conn.execute(
                "SELECT 1 FROM documents WHERE doc_id = ?", (doc["doc_id"],)
            ).fetchone()
            if existing:
                skipped += 1
                continue

        text = doc.pop("text", "")
        content_hash = sha256_text(text) if text else None

        raw_path = raw_dir / f"{doc['doc_id']}.txt"
        text_path = text_dir / f"{doc['doc_id']}.txt"

        try:
            raw_path.write_text(text, encoding="utf-8")
            text_path.write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"  [patents] FAIL write {doc['doc_id']}: {exc}",
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
                content_hash=content_hash,
                status="cleaned",
                error=None,
                source_type="patents",
            )
            conn.commit()

        fetched += 1

    print(f"  [patents] {feed_name}: fetched={fetched}, skipped={skipped}, "
          f"errors={errors}", flush=True)
    return fetched, skipped, errors
