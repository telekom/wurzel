# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
import lxml.html

from wurzel.utils.to_markdown.html2md import clean_tree, html2str, normalize_urls, normalize_urls_in_tree


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


def test_normalize_urls_in_tree_converts_relative_urls_to_absolute():
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
    tree = lxml.html.fromstring(html)
    base_url = "https://example.com"
    normalized = normalize_urls_in_tree(tree, base_url)
    result = lxml.html.tostring(normalized).decode()
    assert 'href="https://example.com/relative/path"' in result
    assert 'src="https://example.com/images/pic.png"' in result
    assert 'href="https://example.com/css/style.css"' in result
    assert 'src="https://example.com/js/app.js"' in result
    # External URLs should remain unchanged
    assert 'href="https://external.com/page"' in result
    assert 'src="https://external.com/img.png"' in result


def test_normalize_urls_in_tree_leaves_non_relative_urls_untouched():
    html = """
    <div>
        <a href="http://already.absolute/path">Absolute</a>
        <img src="data:image/png;base64,abc123">
        <a href="mailto:test@example.com">Mail</a>
        <a href="#fragment">Fragment</a>
    </div>
    """
    tree = lxml.html.fromstring(html)
    base_url = "https://base.url"
    normalized = normalize_urls_in_tree(tree, base_url)
    result = lxml.html.tostring(normalized).decode()
    assert 'href="http://already.absolute/path"' in result
    assert 'src="data:image/png;base64,abc123"' in result
    assert 'href="mailto:test@example.com"' in result
    assert 'href="#fragment"' in result


def test_normalize_urls_in_tree_handles_no_href_or_src():
    html = "<div><p>No links here</p></div>"
    tree = lxml.html.fromstring(html)
    base_url = "https://base.url"
    normalized = normalize_urls_in_tree(tree, base_url)
    result = lxml.html.tostring(normalized).decode()
    assert "No links here" in result


def test_normalize_urls_in_tree_with_empty_attributes():
    html = """
    <div>
        <a href="">Empty href</a>
        <img src="">
    </div>
    """
    tree = lxml.html.fromstring(html)
    base_url = "https://base.url"
    normalized = normalize_urls_in_tree(tree, base_url)
    result = lxml.html.tostring(normalized).decode()
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


def test_normalize_urls_converts_relative_urls_to_absolute():
    html = """
    <div>
        <a href="/about">About</a>
        <img src="/img/logo.png" alt="Logo">
        <link rel="stylesheet" href="/css/main.css">
        <script src="/js/app.js"></script>
        <a href="https://external.com/page">External</a>
        <img src="https://external.com/img.png">
    </div>
    """
    base_url = "https://example.org"
    result = normalize_urls(html, base_url)
    assert 'href="https://example.org/about"' in result
    assert 'src="https://example.org/img/logo.png"' in result
    assert 'href="https://example.org/css/main.css"' in result
    assert 'src="https://example.org/js/app.js"' in result
    # External URLs should remain unchanged
    assert 'href="https://external.com/page"' in result
    assert 'src="https://external.com/img.png"' in result


def test_normalize_urls_leaves_absolute_and_special_urls_untouched():
    html = """
    <div>
        <a href="http://already.absolute/path">Absolute</a>
        <img src="data:image/png;base64,abc123">
        <a href="mailto:test@example.com">Mail</a>
        <a href="#fragment">Fragment</a>
    </div>
    """
    base_url = "https://base.url"
    result = normalize_urls(html, base_url)
    assert 'href="http://already.absolute/path"' in result
    assert 'src="data:image/png;base64,abc123"' in result
    assert 'href="mailto:test@example.com"' in result
    assert 'href="#fragment"' in result


def test_normalize_urls_with_no_href_or_src():
    html = "<div><p>No links here</p></div>"
    base_url = "https://base.url"
    result = normalize_urls(html, base_url)
    assert "No links here" in result


def test_normalize_urls_with_empty_attributes():
    html = """
    <div>
        <a href="">Empty href</a>
        <img src="">
    </div>
    """
    base_url = "https://base.url"
    result = normalize_urls(html, base_url)
    assert 'href=""' in result
    assert 'src=""' in result


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
