"""Clean module for readability extraction and boilerplate removal.

Extracts main content from HTML, removing navigation, ads, and other boilerplate.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from bs4 import BeautifulSoup, Comment, NavigableString


# Tags to completely remove (including their content)
REMOVE_TAGS = frozenset([
    "script", "style", "noscript", "iframe", "object", "embed",
    "svg", "canvas", "video", "audio", "map", "form",
])

# Tags that typically contain boilerplate
BOILERPLATE_TAGS = frozenset([
    "nav", "header", "footer", "aside",
])

# Class/ID patterns that indicate boilerplate
BOILERPLATE_PATTERNS = [
    r"nav(igation)?",
    r"menu",
    r"sidebar",
    r"footer",
    r"header",
    r"banner",
    r"ad(vertis(e|ing|ement))?s?",
    r"sponsor",
    r"promo(tion)?",
    r"social(-?share)?",
    r"share(-?buttons?)?",
    r"cookie(-?consent|-?notice|-?banner)?",
    r"newsletter",
    r"subscribe",
    r"signup",
    r"sign-?up",
    r"comment(s|section)?",
    r"related(-?articles?|-?posts?)?",
    r"popular(-?posts?)?",
    r"trending",
    r"widget",
    r"breadcrumb",
    r"pagination",
    r"meta(-?data)?",
    r"byline",
    r"author(-?info)?",
    r"tags?",
    r"categories",
]

# Compiled regex for boilerplate detection
BOILERPLATE_REGEX = re.compile(
    "|".join(BOILERPLATE_PATTERNS),
    re.IGNORECASE
)

# Tags/classes that likely contain main content
CONTENT_SELECTORS = [
    "article",
    "main",
    "[role=main]",
    ".post-content",
    ".article-content",
    ".entry-content",
    ".content",
    ".post",
    ".article",
    "#content",
    "#main",
    "#article",
]


def _is_boilerplate(element) -> bool:
    """Check if an element is likely boilerplate based on class/id."""
    # Check if element is still valid (not decomposed)
    if not hasattr(element, 'name') or element.name is None:
        return False

    if element.name in BOILERPLATE_TAGS:
        return True

    # Check if element has attrs
    if not hasattr(element, 'attrs') or element.attrs is None:
        return False

    classes = element.get("class", [])
    if isinstance(classes, str):
        classes = [classes]
    class_str = " ".join(classes)

    element_id = element.get("id", "")

    # Check class and id against boilerplate patterns
    if BOILERPLATE_REGEX.search(class_str):
        return True
    if element_id and BOILERPLATE_REGEX.search(element_id):
        return True

    return False


def _remove_boilerplate(soup: BeautifulSoup) -> None:
    """Remove boilerplate elements from soup in place."""
    # Remove tags that should be completely removed
    for tag in REMOVE_TAGS:
        for element in list(soup.find_all(tag)):
            element.decompose()

    # Remove HTML comments
    for comment in list(soup.find_all(string=lambda text: isinstance(text, Comment))):
        comment.extract()

    # Collect boilerplate elements first, then remove
    # (to avoid modifying during iteration)
    to_remove = []
    for element in soup.find_all(True):
        if _is_boilerplate(element):
            to_remove.append(element)

    for element in to_remove:
        # Check if element is still in the tree (not already removed as child of another)
        if element.parent is not None:
            element.decompose()


def _find_main_content(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """Try to find the main content container."""
    for selector in CONTENT_SELECTORS:
        if selector.startswith("."):
            element = soup.find(class_=selector[1:])
        elif selector.startswith("#"):
            element = soup.find(id=selector[1:])
        elif selector.startswith("["):
            # Handle attribute selectors like [role=main]
            match = re.match(r"\[(\w+)=(\w+)\]", selector)
            if match:
                element = soup.find(attrs={match.group(1): match.group(2)})
            else:
                element = None
        else:
            element = soup.find(selector)

        if element:
            return element

    return None


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text."""
    # Replace multiple whitespace with single space
    text = re.sub(r"\s+", " ", text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


def _extract_text(element) -> str:
    """Extract and clean text from an element."""
    if element is None:
        return ""

    # Get text, separating block elements with newlines
    texts = []
    for child in element.descendants:
        if isinstance(child, NavigableString) and not isinstance(child, Comment):
            text = str(child).strip()
            if text:
                texts.append(text)

    text = " ".join(texts)
    return _normalize_whitespace(text)


def extract_content(html: str) -> str:
    """Extract main content from HTML, removing boilerplate.

    Args:
        html: Raw HTML string

    Returns:
        Cleaned text content
    """
    if not html or not html.strip():
        return ""

    # Check if it's plain text (no HTML tags)
    if "<" not in html:
        return _normalize_whitespace(html)

    soup = BeautifulSoup(html, "html.parser")

    # Remove boilerplate
    _remove_boilerplate(soup)

    # Try to find main content container
    main_content = _find_main_content(soup)

    if main_content:
        text = _extract_text(main_content)
    else:
        # Fall back to body or entire document
        body = soup.find("body")
        if body:
            text = _extract_text(body)
        else:
            text = _extract_text(soup)

    return text


def extract_title(html: str) -> Optional[str]:
    """Extract title from HTML.

    Prefers h1 over title tag.

    Args:
        html: Raw HTML string

    Returns:
        Title string or None
    """
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Try h1 first
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
        if title:
            return _normalize_whitespace(title)

    # Fall back to title tag
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
        if title:
            return _normalize_whitespace(title)

    return None


def extract_metadata(html: str) -> dict[str, Any]:
    """Extract metadata from HTML meta tags.

    Args:
        html: Raw HTML string

    Returns:
        Dictionary of metadata
    """
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    metadata = {}

    # Author
    author_meta = soup.find("meta", attrs={"name": "author"})
    if author_meta and author_meta.get("content"):
        metadata["author"] = author_meta["content"]

    # Description
    desc_meta = soup.find("meta", attrs={"name": "description"})
    if desc_meta and desc_meta.get("content"):
        metadata["description"] = desc_meta["content"]

    # Published date - check various sources
    date_selectors = [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "date"}),
        ("meta", {"name": "pubdate"}),
        ("meta", {"property": "og:published_time"}),
        ("time", {"itemprop": "datePublished"}),
    ]

    for tag, attrs in date_selectors:
        element = soup.find(tag, attrs=attrs)
        if element:
            date_val = element.get("content") or element.get("datetime")
            if date_val:
                metadata["published"] = date_val
                break

    # Open Graph title/description as fallback
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content") and "title" not in metadata:
        metadata["og_title"] = og_title["content"]

    og_desc = soup.find("meta", attrs={"property": "og:description"})
    if og_desc and og_desc.get("content") and "description" not in metadata:
        metadata["og_description"] = og_desc["content"]

    return metadata


def clean_document(html: str) -> dict[str, Any]:
    """Clean an HTML document and extract structured data.

    Args:
        html: Raw HTML string

    Returns:
        Dictionary with:
            - content: Cleaned text content
            - title: Extracted title
            - metadata: Extracted metadata
    """
    return {
        "content": extract_content(html),
        "title": extract_title(html),
        "metadata": extract_metadata(html),
    }
