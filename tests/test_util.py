"""Tests for utility functions in util module.

Covers:
- slugify: ID generation per AGENTS.md slug rules
- short_hash / sha256_text: deterministic hashing
- clean_html: HTML to plain text conversion
- parse_entry_date: RSS/Atom date parsing
"""

import pytest

from util import (
    clean_html,
    parse_entry_date,
    sha256_text,
    short_hash,
    slugify,
)


class TestSlugify:
    """Test slugify() against AGENTS.md slug rules:
    - lowercase
    - alphanumerics + underscore only
    - strip punctuation
    - keep short
    """

    def test_lowercase(self):
        assert slugify("OpenAI") == "openai"
        assert slugify("HUGGING FACE") == "hugging_face"

    def test_spaces_to_underscores(self):
        assert slugify("hello world") == "hello_world"
        assert slugify("one two three") == "one_two_three"

    def test_punctuation_stripped(self):
        assert slugify("hello-world") == "hello_world"
        assert slugify("test.value") == "test_value"
        assert slugify("what's up?") == "what_s_up"

    def test_multiple_special_chars_collapse(self):
        assert slugify("a---b") == "a_b"
        assert slugify("a   b") == "a_b"
        assert slugify("a@#$%b") == "a_b"

    def test_leading_trailing_underscores_stripped(self):
        assert slugify("_hello_") == "hello"
        assert slugify("---test---") == "test"
        assert slugify("  spaces  ") == "spaces"

    def test_empty_string_returns_source(self):
        assert slugify("") == "source"
        assert slugify("!!!") == "source"
        assert slugify("   ") == "source"

    def test_unicode_stripped(self):
        assert slugify("café") == "caf"
        assert slugify("naïve") == "na_ve"

    def test_realistic_source_names(self):
        assert slugify("arXiv CS.AI") == "arxiv_cs_ai"
        assert slugify("Hugging Face Blog") == "hugging_face_blog"
        assert slugify("OpenAI Blog") == "openai_blog"
        assert slugify("MIT Technology Review") == "mit_technology_review"


class TestShortHash:
    """Test short_hash() returns consistent 8-char SHA1 prefix."""

    def test_returns_8_chars(self):
        result = short_hash("https://example.com/article")
        assert len(result) == 8

    def test_deterministic(self):
        url = "https://example.com/test"
        assert short_hash(url) == short_hash(url)

    def test_different_inputs_different_hashes(self):
        assert short_hash("a") != short_hash("b")

    def test_hex_characters_only(self):
        result = short_hash("test string")
        assert all(c in "0123456789abcdef" for c in result)


class TestSha256Text:
    """Test sha256_text() returns full SHA256 hash."""

    def test_returns_64_chars(self):
        result = sha256_text("hello world")
        assert len(result) == 64

    def test_deterministic(self):
        text = "some article text"
        assert sha256_text(text) == sha256_text(text)

    def test_known_hash(self):
        # Known SHA256 of "hello"
        assert sha256_text("hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    def test_hex_characters_only(self):
        result = sha256_text("test")
        assert all(c in "0123456789abcdef" for c in result)


class TestCleanHtml:
    """Test clean_html() strips tags and normalizes whitespace."""

    def test_strips_basic_tags(self):
        html = "<p>Hello <b>world</b></p>"
        assert clean_html(html) == "Hello world"

    def test_strips_script_tags(self):
        html = "<p>Text</p><script>alert('xss')</script><p>More</p>"
        assert clean_html(html) == "Text More"

    def test_strips_style_tags(self):
        html = "<style>.foo{color:red}</style><p>Content</p>"
        assert clean_html(html) == "Content"

    def test_strips_noscript_tags(self):
        html = "<noscript>Enable JS</noscript><div>Main content</div>"
        assert clean_html(html) == "Main content"

    def test_normalizes_whitespace(self):
        html = "<p>Too    many     spaces</p>"
        assert clean_html(html) == "Too many spaces"

    def test_handles_newlines(self):
        html = "<p>Line one</p>\n\n<p>Line two</p>"
        result = clean_html(html)
        assert "Line one" in result
        assert "Line two" in result

    def test_empty_html(self):
        assert clean_html("") == ""
        assert clean_html("<div></div>") == ""

    def test_preserves_text_content(self):
        html = """
        <article>
            <h1>Article Title</h1>
            <p>First paragraph with <a href="#">link</a>.</p>
            <p>Second paragraph.</p>
        </article>
        """
        result = clean_html(html)
        assert "Article Title" in result
        assert "First paragraph" in result
        assert "link" in result
        assert "Second paragraph" in result


class TestParseEntryDate:
    """Test parse_entry_date() extracts dates from RSS/Atom entries."""

    def test_published_parsed(self):
        # feedparser provides parsed tuples
        entry = {"published_parsed": (2025, 12, 1, 10, 30, 0, 0, 335, 0)}
        assert parse_entry_date(entry) == "2025-12-01"

    def test_updated_parsed_fallback(self):
        entry = {"updated_parsed": (2025, 6, 15, 8, 0, 0, 0, 166, 0)}
        assert parse_entry_date(entry) == "2025-06-15"

    def test_published_string_rfc2822(self):
        # RFC 2822 format common in RSS
        entry = {"published": "Mon, 01 Dec 2025 10:30:00 GMT"}
        assert parse_entry_date(entry) == "2025-12-01"

    def test_updated_string_fallback(self):
        entry = {"updated": "Tue, 15 Jun 2025 08:00:00 +0000"}
        assert parse_entry_date(entry) == "2025-06-15"

    def test_prefers_published_over_updated(self):
        entry = {
            "published_parsed": (2025, 1, 1, 0, 0, 0, 0, 1, 0),
            "updated_parsed": (2025, 12, 31, 0, 0, 0, 0, 365, 0),
        }
        assert parse_entry_date(entry) == "2025-01-01"

    def test_returns_none_for_missing(self):
        assert parse_entry_date({}) is None
        assert parse_entry_date({"title": "No date here"}) is None

    def test_returns_none_for_invalid_string(self):
        entry = {"published": "not a real date"}
        assert parse_entry_date(entry) is None

    def test_handles_timezone_naive(self):
        # Some feeds don't include timezone
        entry = {"published": "Mon, 01 Dec 2025 10:30:00"}
        result = parse_entry_date(entry)
        # Should still parse, treating as UTC
        assert result == "2025-12-01"
