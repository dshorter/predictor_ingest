"""Utility helpers for predictor_ingest.

Pure functions with minimal dependencies for:
- Slugging and ID generation
- Hashing (SHA1, SHA256)
- HTML cleaning
- Date parsing
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

from bs4 import BeautifulSoup


def slugify(value: str) -> str:
    """Convert string to URL-safe slug.

    Rules per AGENTS.md:
    - lowercase
    - alphanumerics + underscore only
    - strip punctuation
    - collapse multiple separators
    """
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "source"


def short_hash(value: str) -> str:
    """Return 8-character SHA1 hash prefix."""
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]


def sha256_text(text: str) -> str:
    """Return full SHA256 hash of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_entry_date(entry: dict) -> Optional[str]:
    """Extract publication date from RSS/Atom feed entry.

    Tries parsed tuples first, then string formats.
    Returns ISO date string (YYYY-MM-DD) or None.
    """
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            dt = datetime(*value[:6], tzinfo=timezone.utc)
            return dt.date().isoformat()
    for key in ("published", "updated"):
        value = entry.get(key)
        if value:
            try:
                dt = parsedate_to_datetime(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.date().isoformat()
            except (TypeError, ValueError):
                return None
    return None


def clean_html(html: str) -> str:
    """Strip HTML tags and normalize whitespace.

    Removes script, style, and noscript tags entirely.
    Returns plain text with single spaces.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()
