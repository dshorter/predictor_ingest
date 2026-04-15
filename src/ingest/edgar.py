"""SEC EDGAR ingest fetcher — polls company filings via the EDGAR API.

Uses the SEC EDGAR data API (data.sec.gov) to fetch recent filings for
semiconductor companies. No authentication required, but SEC fair access
policy requires a User-Agent header with a contact email.

Filings are mapped to the standard document schema and stored via
upsert_document(). Deduplication is handled by accession number as doc_id.

Environment variables:
    SEC_EDGAR_EMAIL: Contact email for User-Agent (required by SEC policy).
                     Falls back to a generic placeholder if not set.

Rate limit: 10 requests/second per SEC guidelines.

See docs/methodology/deep-research-report.md for rationale.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from ingest.rss import upsert_document

# SEC EDGAR API base URL
EDGAR_SUBMISSIONS_BASE = "https://data.sec.gov/submissions"
EDGAR_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

# SEC requires User-Agent with company name + email
DEFAULT_AGENT = "predictor-ingest/0.1"

# Rate limiting: 100ms between requests (10 req/sec per SEC guidelines)
REQUEST_DELAY = 0.1


def _user_agent() -> str:
    """Build User-Agent string per SEC fair access policy."""
    email = os.environ.get("SEC_EDGAR_EMAIL", "")
    if email:
        return f"{DEFAULT_AGENT} ({email})"
    print("  [edgar] WARNING: SEC_EDGAR_EMAIL not set. SEC fair access policy "
          "requires a contact email in User-Agent. Set SEC_EDGAR_EMAIL env var.",
          file=sys.stderr, flush=True)
    return DEFAULT_AGENT


def sha256_text(text: str) -> str:
    """SHA-256 hash of text for dedup."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pad_cik(cik: str) -> str:
    """Pad CIK to 10 digits as required by EDGAR API."""
    digits = re.sub(r"\D", "", cik)
    return digits.zfill(10)


def _accession_to_path(accession: str) -> str:
    """Convert accession number (0000050863-24-000042) to path format (no dashes)."""
    return accession.replace("-", "")


def fetch_company_filings(
    cik: str,
    company_name: str,
    filing_types: list[str],
    limit: int = 20,
    session: Optional[requests.Session] = None,
) -> list[dict]:
    """Fetch recent filings for a company from EDGAR.

    Args:
        cik: SEC Central Index Key (e.g., "0000050863" for Intel).
        company_name: Human-readable company name for logging.
        filing_types: Form types to include (e.g., ["10-K", "10-Q", "8-K"]).
        limit: Max filings to return across all types.
        session: Optional requests session with User-Agent set.

    Returns:
        List of filing dicts with keys: accession, form, filing_date,
        primary_doc, company, cik, doc_url.
    """
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = _user_agent()

    padded_cik = _pad_cik(cik)
    url = f"{EDGAR_SUBMISSIONS_BASE}/CIK{padded_cik}.json"

    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        print(f"  [edgar] FAIL {company_name} (CIK {cik}): {exc}",
              file=sys.stderr, flush=True)
        return []

    time.sleep(REQUEST_DELAY)

    # Extract recent filings from the inline filings object
    recent = data.get("filings", {}).get("recent", {})
    if not recent:
        return []

    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])

    # Filter by filing type and collect
    filing_types_upper = {ft.upper() for ft in filing_types}
    filings = []

    for i, form in enumerate(forms):
        if form.upper() not in filing_types_upper:
            continue
        if i >= len(accessions) or i >= len(filing_dates) or i >= len(primary_docs):
            break

        accession = accessions[i]
        accession_path = _accession_to_path(accession)
        raw_cik = re.sub(r"\D", "", cik)
        doc_url = (
            f"{EDGAR_ARCHIVES_BASE}/{raw_cik}/{accession_path}/{primary_docs[i]}"
        )

        filings.append({
            "accession": accession,
            "form": form,
            "filing_date": filing_dates[i],
            "primary_doc": primary_docs[i],
            "description": descriptions[i] if i < len(descriptions) else "",
            "company": company_name,
            "cik": cik,
            "doc_url": doc_url,
        })

        if len(filings) >= limit:
            break

    return filings


def _fetch_filing_text(
    doc_url: str,
    session: requests.Session,
    max_chars: int = 50000,
) -> Optional[str]:
    """Fetch the text content of a filing document.

    For HTML filings, returns raw text (extraction happens downstream).
    Caps at max_chars to avoid ingesting 200-page 10-Ks in full.

    Args:
        doc_url: Full URL to the filing document.
        session: Requests session with User-Agent.
        max_chars: Max characters to keep (default 50K ~= first 10-15 pages).

    Returns:
        Filing text content, or None on failure.
    """
    try:
        resp = session.get(doc_url, timeout=30)
        resp.raise_for_status()
        text = resp.text[:max_chars]
        time.sleep(REQUEST_DELAY)
        return text
    except requests.RequestException as exc:
        print(f"  [edgar] FAIL fetching {doc_url}: {exc}",
              file=sys.stderr, flush=True)
        return None


def _filing_to_doc(filing: dict, feed_name: str) -> dict:
    """Map an EDGAR filing to a document dict.

    Args:
        filing: Dict from fetch_company_filings().
        feed_name: Name of the feed config entry (for the source field).

    Returns:
        Dict with fields matching upsert_document() parameters.
    """
    accession = filing["accession"]
    company = filing["company"]
    form = filing["form"]
    filing_date = filing["filing_date"]
    description = filing.get("description", "")

    doc_id = f"edgar_{accession}"
    title = f"{company} — {form}"
    if description:
        title += f": {description[:80]}"

    return {
        "doc_id": doc_id,
        "url": filing["doc_url"],
        "source": feed_name,
        "source_type": "edgar",
        "title": title,
        "published_at": filing_date,
    }


def ingest_edgar(
    feed_config: dict,
    conn,
    raw_dir: Path,
    text_dir: Path,
    repo: Path,
    skip_existing: bool = True,
) -> tuple[int, int, int]:
    """Ingest SEC EDGAR filings for a feed config entry.

    Args:
        feed_config: Dict from feeds.yaml with keys: name, companies,
                     filing_types, limit.
        conn: SQLite database connection.
        raw_dir: Directory for raw content storage.
        text_dir: Directory for cleaned text storage.
        repo: Repository root path.
        skip_existing: Skip filings already in the database.

    Returns:
        Tuple of (fetched, skipped, errors).
    """
    feed_name = feed_config.get("name", "SEC EDGAR")
    companies = feed_config.get("companies", [])
    filing_types = feed_config.get("filing_types", ["10-K", "10-Q", "8-K"])
    total_limit = feed_config.get("limit", 20)

    if not companies:
        print(f"  [edgar] {feed_name}: no companies configured, skipping",
              file=sys.stderr, flush=True)
        return 0, 0, 1

    session = requests.Session()
    session.headers["User-Agent"] = _user_agent()
    session.headers["Accept"] = "application/json"

    fetched = 0
    skipped = 0
    errors = 0

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Distribute limit across companies
    per_company_limit = max(1, total_limit // len(companies))

    print(f"  [edgar] {feed_name}: polling {len(companies)} companies "
          f"(forms: {', '.join(filing_types)})", flush=True)

    for company_info in companies:
        name = company_info.get("name", "Unknown")
        cik = company_info.get("cik", "")
        if not cik:
            print(f"  [edgar] WARNING: no CIK for {name}, skipping",
                  file=sys.stderr, flush=True)
            errors += 1
            continue

        filings = fetch_company_filings(
            cik=cik,
            company_name=name,
            filing_types=filing_types,
            limit=per_company_limit,
            session=session,
        )

        for filing in filings:
            doc = _filing_to_doc(filing, feed_name)

            # Skip existing
            if skip_existing and conn is not None:
                existing = conn.execute(
                    "SELECT 1 FROM documents WHERE doc_id = ?", (doc["doc_id"],)
                ).fetchone()
                if existing:
                    skipped += 1
                    continue

            # Fetch filing text
            text = _fetch_filing_text(filing["doc_url"], session)
            if text is None:
                errors += 1
                continue

            content_hash = sha256_text(text)

            raw_path = raw_dir / f"{doc['doc_id']}.txt"
            text_path = text_dir / f"{doc['doc_id']}.txt"

            try:
                raw_path.write_text(text, encoding="utf-8")
                text_path.write_text(text, encoding="utf-8")
            except OSError as exc:
                print(f"  [edgar] FAIL write {doc['doc_id']}: {exc}",
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
                    source_type="edgar",
                )
                conn.commit()

            fetched += 1

            if fetched >= total_limit:
                break

        if fetched >= total_limit:
            break

    print(f"  [edgar] {feed_name}: fetched={fetched}, skipped={skipped}, "
          f"errors={errors}", flush=True)
    return fetched, skipped, errors
