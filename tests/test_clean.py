"""Tests for clean module - readability extraction and boilerplate removal.

Tests content extraction from HTML, removing navigation, ads, and other boilerplate.
"""

from __future__ import annotations

import pytest


def _get_clean_module():
    """Lazy import of clean module."""
    import clean
    return clean


# Sample HTML with typical webpage structure
SAMPLE_WEBPAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Research Breakthrough - Tech News</title>
    <script src="analytics.js"></script>
    <style>.ad { display: block; }</style>
</head>
<body>
    <header>
        <nav>
            <a href="/">Home</a>
            <a href="/about">About</a>
            <a href="/contact">Contact</a>
        </nav>
    </header>

    <div class="sidebar">
        <h3>Related Articles</h3>
        <ul>
            <li><a href="/article1">Article 1</a></li>
            <li><a href="/article2">Article 2</a></li>
        </ul>
    </div>

    <main>
        <article>
            <h1>OpenAI Announces GPT-5 with Revolutionary Capabilities</h1>
            <p class="byline">By Jane Smith | January 15, 2026</p>
            <p>OpenAI has announced GPT-5, their latest large language model,
            which demonstrates significant improvements in reasoning and accuracy.</p>
            <p>The model was trained on a diverse dataset and shows remarkable
            performance on standard benchmarks including MMLU and HumanEval.</p>
            <p>Industry experts believe this represents a major step forward
            in artificial intelligence research.</p>
        </article>
    </main>

    <aside class="advertisement">
        <div class="ad">Buy our products!</div>
    </aside>

    <footer>
        <p>Copyright 2026 Tech News</p>
        <nav>
            <a href="/privacy">Privacy Policy</a>
            <a href="/terms">Terms of Service</a>
        </nav>
    </footer>

    <script>trackPageView();</script>
</body>
</html>
"""

# Expected content after cleaning
EXPECTED_MAIN_CONTENT = [
    "OpenAI Announces GPT-5",
    "Revolutionary Capabilities",
    "large language model",
    "reasoning and accuracy",
    "diverse dataset",
    "MMLU and HumanEval",
    "artificial intelligence research",
]

# Content that should be removed
BOILERPLATE_CONTENT = [
    "Related Articles",
    "Buy our products",
    "Copyright 2026",
    "Privacy Policy",
    "Terms of Service",
    "trackPageView",
]


class TestExtractContent:
    """Test main content extraction."""

    def test_extracts_article_content(self):
        """Test that article content is extracted."""
        clean = _get_clean_module()
        result = clean.extract_content(SAMPLE_WEBPAGE_HTML)

        for expected in EXPECTED_MAIN_CONTENT:
            assert expected in result, f"Missing: {expected}"

    def test_removes_navigation(self):
        """Test that navigation is removed."""
        clean = _get_clean_module()
        result = clean.extract_content(SAMPLE_WEBPAGE_HTML)

        # Navigation links should be removed
        assert "Home" not in result or result.count("Home") == 0
        assert "About" not in result or "href" not in result

    def test_removes_sidebar(self):
        """Test that sidebar content is removed."""
        clean = _get_clean_module()
        result = clean.extract_content(SAMPLE_WEBPAGE_HTML)

        assert "Related Articles" not in result

    def test_removes_advertisements(self):
        """Test that ads are removed."""
        clean = _get_clean_module()
        result = clean.extract_content(SAMPLE_WEBPAGE_HTML)

        assert "Buy our products" not in result

    def test_removes_footer(self):
        """Test that footer is removed."""
        clean = _get_clean_module()
        result = clean.extract_content(SAMPLE_WEBPAGE_HTML)

        assert "Copyright 2026" not in result
        assert "Privacy Policy" not in result

    def test_removes_scripts(self):
        """Test that scripts are removed."""
        clean = _get_clean_module()
        result = clean.extract_content(SAMPLE_WEBPAGE_HTML)

        assert "trackPageView" not in result
        assert "analytics.js" not in result

    def test_removes_styles(self):
        """Test that style content is removed."""
        clean = _get_clean_module()
        result = clean.extract_content(SAMPLE_WEBPAGE_HTML)

        assert "display: block" not in result


class TestExtractTitle:
    """Test title extraction."""

    def test_extracts_title_from_h1(self):
        """Test extracting title from h1 tag."""
        clean = _get_clean_module()
        html = "<html><body><h1>Article Title</h1><p>Content</p></body></html>"
        title = clean.extract_title(html)

        assert title == "Article Title"

    def test_extracts_title_from_title_tag(self):
        """Test extracting title from title tag when no h1."""
        clean = _get_clean_module()
        html = "<html><head><title>Page Title</title></head><body><p>Content</p></body></html>"
        title = clean.extract_title(html)

        assert title == "Page Title"

    def test_prefers_h1_over_title_tag(self):
        """Test that h1 is preferred over title tag."""
        clean = _get_clean_module()
        html = """
        <html>
        <head><title>Page Title - Site Name</title></head>
        <body><h1>Article Title</h1></body>
        </html>
        """
        title = clean.extract_title(html)

        assert title == "Article Title"

    def test_returns_none_for_missing_title(self):
        """Test returning None when no title found."""
        clean = _get_clean_module()
        html = "<html><body><p>Just some content</p></body></html>"
        title = clean.extract_title(html)

        assert title is None

    def test_cleans_title_whitespace(self):
        """Test that title whitespace is normalized."""
        clean = _get_clean_module()
        html = "<html><body><h1>  Title  With   Spaces  </h1></body></html>"
        title = clean.extract_title(html)

        assert title == "Title With Spaces"


class TestExtractMetadata:
    """Test metadata extraction."""

    def test_extracts_author(self):
        """Test extracting author from meta tag."""
        clean = _get_clean_module()
        html = """
        <html>
        <head><meta name="author" content="Jane Smith"></head>
        <body><p>Content</p></body>
        </html>
        """
        metadata = clean.extract_metadata(html)

        assert metadata.get("author") == "Jane Smith"

    def test_extracts_description(self):
        """Test extracting description from meta tag."""
        clean = _get_clean_module()
        html = """
        <html>
        <head><meta name="description" content="Article about AI"></head>
        <body><p>Content</p></body>
        </html>
        """
        metadata = clean.extract_metadata(html)

        assert metadata.get("description") == "Article about AI"

    def test_extracts_publish_date(self):
        """Test extracting publish date from various sources."""
        clean = _get_clean_module()
        html = """
        <html>
        <head><meta property="article:published_time" content="2026-01-15T10:00:00Z"></head>
        <body><p>Content</p></body>
        </html>
        """
        metadata = clean.extract_metadata(html)

        assert "2026-01-15" in metadata.get("published", "")

    def test_returns_empty_dict_for_no_metadata(self):
        """Test returning empty dict when no metadata found."""
        clean = _get_clean_module()
        html = "<html><body><p>Content</p></body></html>"
        metadata = clean.extract_metadata(html)

        assert metadata == {}


class TestCleanDocument:
    """Test the main clean_document function."""

    def test_returns_cleaned_result(self):
        """Test that clean_document returns structured result."""
        clean = _get_clean_module()
        result = clean.clean_document(SAMPLE_WEBPAGE_HTML)

        assert "content" in result
        assert "title" in result
        assert "metadata" in result

    def test_content_is_clean(self):
        """Test that content is properly cleaned."""
        clean = _get_clean_module()
        result = clean.clean_document(SAMPLE_WEBPAGE_HTML)

        # Should have article content
        assert "GPT-5" in result["content"]
        assert "large language model" in result["content"]

        # Should not have boilerplate
        assert "Buy our products" not in result["content"]

    def test_title_is_extracted(self):
        """Test that title is extracted."""
        clean = _get_clean_module()
        result = clean.clean_document(SAMPLE_WEBPAGE_HTML)

        assert result["title"] is not None
        assert "GPT-5" in result["title"]


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_empty_html(self):
        """Test handling empty HTML."""
        clean = _get_clean_module()
        result = clean.extract_content("")

        assert result == ""

    def test_handles_plain_text(self):
        """Test handling plain text input."""
        clean = _get_clean_module()
        result = clean.extract_content("Just plain text, no HTML")

        assert "Just plain text" in result

    def test_handles_malformed_html(self):
        """Test handling malformed HTML."""
        clean = _get_clean_module()
        html = "<p>Unclosed paragraph<div>Mixed tags</p></div>"
        result = clean.extract_content(html)

        # Should still extract some content
        assert "Unclosed paragraph" in result or "Mixed tags" in result

    def test_handles_minimal_html(self):
        """Test handling minimal HTML structure."""
        clean = _get_clean_module()
        html = "<p>Simple paragraph</p>"
        result = clean.extract_content(html)

        assert "Simple paragraph" in result

    def test_preserves_unicode(self):
        """Test that unicode is preserved."""
        clean = _get_clean_module()
        html = "<p>日本語テスト and émojis 🎉</p>"
        result = clean.extract_content(html)

        assert "日本語テスト" in result
        assert "émojis" in result

    def test_normalizes_whitespace(self):
        """Test that whitespace is normalized."""
        clean = _get_clean_module()
        html = "<p>Multiple    spaces   and\n\nnewlines</p>"
        result = clean.extract_content(html)

        # Should not have multiple consecutive spaces
        assert "  " not in result


class TestBoilerplatePatterns:
    """Test specific boilerplate pattern removal."""

    def test_removes_cookie_notices(self):
        """Test removal of cookie consent notices."""
        clean = _get_clean_module()
        html = """
        <html><body>
        <div class="cookie-consent">We use cookies...</div>
        <article><p>Main content here.</p></article>
        </body></html>
        """
        result = clean.extract_content(html)

        assert "We use cookies" not in result
        assert "Main content" in result

    def test_removes_social_share_buttons(self):
        """Test removal of social sharing widgets."""
        clean = _get_clean_module()
        html = """
        <html><body>
        <div class="social-share">Share on Twitter | Share on Facebook</div>
        <article><p>Article content.</p></article>
        </body></html>
        """
        result = clean.extract_content(html)

        assert "Share on Twitter" not in result
        assert "Article content" in result

    def test_removes_newsletter_signup(self):
        """Test removal of newsletter signup forms."""
        clean = _get_clean_module()
        html = """
        <html><body>
        <article><p>Article content.</p></article>
        <div class="newsletter">Subscribe to our newsletter!</div>
        </body></html>
        """
        result = clean.extract_content(html)

        assert "Subscribe to our newsletter" not in result
        assert "Article content" in result

    def test_removes_comment_sections(self):
        """Test removal of comment sections."""
        clean = _get_clean_module()
        html = """
        <html><body>
        <article><p>Article content.</p></article>
        <section id="comments">
            <h3>Comments (42)</h3>
            <div class="comment">Great article!</div>
        </section>
        </body></html>
        """
        result = clean.extract_content(html)

        assert "Great article!" not in result
        assert "Comments (42)" not in result
        assert "Article content" in result


class TestArxivFormat:
    """Test handling of arXiv-style content."""

    def test_extracts_arxiv_abstract(self):
        """Test extracting abstract from arXiv-style page."""
        clean = _get_clean_module()
        html = """
        <html><body>
        <h1>Attention Is All You Need</h1>
        <div class="authors">Vaswani et al.</div>
        <blockquote class="abstract">
        We propose a new architecture called the Transformer,
        based solely on attention mechanisms.
        </blockquote>
        </body></html>
        """
        result = clean.extract_content(html)

        assert "Transformer" in result
        assert "attention mechanisms" in result


class TestBlogFormat:
    """Test handling of blog-style content."""

    def test_extracts_blog_post(self):
        """Test extracting content from blog post."""
        clean = _get_clean_module()
        html = """
        <html><body>
        <header class="site-header">Blog Name</header>
        <article class="post">
            <h1 class="post-title">My Blog Post</h1>
            <div class="post-content">
                <p>This is the first paragraph of my post.</p>
                <p>This is the second paragraph with more details.</p>
            </div>
        </article>
        <aside class="sidebar">Archives | Tags</aside>
        </body></html>
        """
        result = clean.extract_content(html)

        assert "first paragraph" in result
        assert "second paragraph" in result
        assert "Archives" not in result
