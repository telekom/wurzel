# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
from collections.abc import Callable

import lxml.html
import pytest

from wurzel.utils import MarkdownConverterSettings
from wurzel.utils.to_markdown.html2md import clean_tree, html2str, normalize_urls, normalize_urls_in_tree, to_markdown


def _normalize_via_tree(html: str, base_url: str) -> str:
    """Wrapper: parse → normalize_urls_in_tree → serialize back to str."""
    tree = lxml.html.fromstring(html)
    return lxml.html.tostring(normalize_urls_in_tree(tree, base_url)).decode()


@pytest.fixture(
    params=[
        pytest.param(_normalize_via_tree, id="normalize_urls_in_tree"),
        pytest.param(normalize_urls, id="normalize_urls"),
    ]
)
def normalize_fn(request: pytest.FixtureRequest) -> Callable[[str, str], str]:
    """Parametrized fixture that exercises both URL-normalization entry points."""
    return request.param  # type: ignore[return-value]


def test_clean_tree_removes_script_link_style_svg_footer():
    html = """
    <div>
        <script>alert("hi")</script>
        <link rel="stylesheet" href="style.css">
        <style>body { color: red; }</style>
        <svg><circle cx="50" cy="50" r="40" /></svg>
        <footer>Footer content</footer>
        <p>Keep me</p>
    </div>
    """
    tree = lxml.html.fromstring(html)
    cleaned = clean_tree(tree)
    result = lxml.html.tostring(cleaned).decode()
    assert "<script" not in result
    assert "<link" not in result
    assert "<style" not in result
    assert "<svg" not in result
    assert "<footer" not in result
    assert "<p>Keep me</p>" in result


def test_clean_tree_replaces_img_with_alt_text():
    html = """
    <div>
        <img src="test.png" alt="AltText">
        <img src="noalt.png">
        <p>Other</p>
    </div>
    """
    tree = lxml.html.fromstring(html)
    cleaned = clean_tree(tree)
    result = lxml.html.tostring(cleaned).decode()
    assert "<img" not in result
    assert "AltText" in result
    assert "noalt.png" not in result
    assert "<span>AltText</span>" in result
    assert "<span></span>" in result  # for img without alt


def test_clean_tree_removes_js_footer_div():
    html = """
    <div>
        <div id="js-footer">Should be removed</div>
        <div>Should stay</div>
    </div>
    """
    tree = lxml.html.fromstring(html)
    cleaned = clean_tree(tree)
    result = lxml.html.tostring(cleaned).decode()
    assert "Should be removed" not in result
    assert "Should stay" in result


def test_clean_tree_handles_no_removals():
    html = "<div><p>Nothing to remove</p></div>"
    tree = lxml.html.fromstring(html)
    cleaned = clean_tree(tree)
    result = lxml.html.tostring(cleaned).decode()
    assert "Nothing to remove" in result


def test_normalize_urls_converts_relative_to_absolute(normalize_fn: Callable[[str, str], str]):
    html = """
    <div>
        <a href="/relative/path">Link</a>
        <img src="/images/pic.png" alt="pic">
        <link rel="stylesheet" href="/css/style.css">
        <script src="/js/app.js"></script>
        <a href="https://external.com/page">External</a>
        <img src="https://external.com/img.png">
    </div>
    """
    result = normalize_fn(html, "https://example.com")
    assert 'href="https://example.com/relative/path"' in result
    assert 'src="https://example.com/images/pic.png"' in result
    assert 'href="https://example.com/css/style.css"' in result
    assert 'src="https://example.com/js/app.js"' in result
    assert 'href="https://external.com/page"' in result
    assert 'src="https://external.com/img.png"' in result


def test_normalize_urls_leaves_non_relative_urls_untouched(normalize_fn: Callable[[str, str], str]):
    html = """
    <div>
        <a href="http://already.absolute/path">Absolute</a>
        <img src="data:image/png;base64,abc123">
        <a href="mailto:test@example.com">Mail</a>
        <a href="#fragment">Fragment</a>
    </div>
    """
    result = normalize_fn(html, "https://base.url")
    assert 'href="http://already.absolute/path"' in result
    assert 'src="data:image/png;base64,abc123"' in result
    assert 'href="mailto:test@example.com"' in result
    assert 'href="#fragment"' in result


def test_normalize_urls_handles_no_href_or_src(normalize_fn: Callable[[str, str], str]):
    result = normalize_fn("<div><p>No links here</p></div>", "https://base.url")
    assert "No links here" in result


def test_normalize_urls_with_empty_attributes(normalize_fn: Callable[[str, str], str]):
    html = """
    <div>
        <a href="">Empty href</a>
        <img src="">
    </div>
    """
    result = normalize_fn(html, "https://base.url")
    assert 'href=""' in result
    assert 'src=""' in result


def test_html2str_returns_string_representation_of_element():
    html = "<div><p>Hello <b>world</b>!</p></div>"
    tree = lxml.html.fromstring(html)
    result = html2str(tree)
    assert isinstance(result, str)
    assert "<div>" in result
    assert "<p>Hello <b>world</b>!</p>" in result


def test_html2str_preserves_html_structure():
    html = "<section><ul><li>Item 1</li><li>Item 2</li></ul></section>"
    tree = lxml.html.fromstring(html)
    result = html2str(tree)
    assert "<section>" in result
    assert "<ul><li>Item 1</li><li>Item 2</li></ul>" in result


def test_html2str_handles_empty_element():
    html = "<div></div>"
    tree = lxml.html.fromstring(html)
    result = html2str(tree)
    assert result.strip().startswith("<div")
    assert result.strip().endswith("</div>")


def test_html2str_handles_nested_elements():
    html = "<div><span><a href='#'>Link</a></span></div>"
    tree = lxml.html.fromstring(html)
    result = html2str(tree)
    assert "Link" in result


def test_normalize_urls_handles_multiple_elements():
    html = """
    <ul>
        <li><a href="/foo">Foo</a></li>
        <li><a href="/bar">Bar</a></li>
        <li><img src="/baz.png"></li>
    </ul>
    """
    base_url = "https://site.com"
    result = normalize_urls(html, base_url)
    assert 'href="https://site.com/foo"' in result
    assert 'href="https://site.com/bar"' in result
    assert 'src="https://site.com/baz.png"' in result


@pytest.fixture
def to_markdown_settings():
    """Fixture to provide a default MarkdownConverterSettings for tests."""
    return MarkdownConverterSettings(HTML2MD_BINARY_FLAGS="-T")


_HTML_TABLE_CASES = [
    pytest.param(
        """
        <html><body>
            <h1>Sample Table</h1>
            <table border="1">
                <thead><tr><th>Name</th><th>Age</th><th>City</th></tr></thead>
                <tbody>
                    <tr><td>John</td><td>25</td><td>New York</td></tr>
                    <tr><td>Jane</td><td>30</td><td>London</td></tr>
                </tbody>
            </table>
            <p>This is a paragraph after the table.</p>
        </body></html>
        """,
        [
            "| Name | Age | City |",
            "| --- | --- | --- |",
            "| John | 25 | New York |",
            "| Jane | 30 | London |",
            "# Sample Table",
            "This is a paragraph after the table.",
        ],
        id="full_table_with_header_and_context",
    ),
    pytest.param(
        """
        <table>
            <tr><th>Product</th><th>Price</th></tr>
            <tr><td>Apple</td><td>$1.00</td></tr>
            <tr><td>Orange</td><td>$1.50</td></tr>
        </table>
        """,
        ["| Product | Price |", "| --- | --- |", "| Apple | $1.00 |", "| Orange | $1.50 |"],
        id="simple_table_without_thead",
    ),
    pytest.param(
        "<table><tr><td>Only</td><td>One</td><td>Row</td></tr></table>",
        ["| Only | One | Row |"],
        id="single_row_table",
    ),
]


@pytest.mark.parametrize("html_input,expected_substrings", _HTML_TABLE_CASES)
def test_to_markdown_table_conversion(html_input: str, expected_substrings: list[str], to_markdown_settings: MarkdownConverterSettings):
    """Test that HTML tables are properly converted to markdown table format."""
    result = to_markdown(html_input, settings=to_markdown_settings)
    for expected in expected_substrings:
        assert expected in result
