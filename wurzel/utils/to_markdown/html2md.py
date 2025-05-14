# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import platform
import re
import subprocess
import tempfile
from pathlib import Path

# Related third-party imports
import lxml.etree
import lxml.html
from mistletoe import Document
from mistletoe.block_token import ThematicBreak
from mistletoe.markdown_renderer import MarkdownRenderer
from mistletoe.span_token import Image

from wurzel.exceptions import InvalidPlatform, MarkdownConvertFailed

# pylint: disable=c-extension-no-member


def __get_html2md() -> Path:
    default_path = {
        "Linux_x86_64": Path(__file__).parent / "html2md",
        "Darwin_arm64": Path(__file__).parent / "html2md_darwin_arm",
        "Darwin_x86_64": Path(__file__).parent / "html2md_darwin_amd64",
    }
    fallback = default_path.get(f"{platform.uname().system}_{platform.uname().machine}", None)
    if fallback is None:
        raise InvalidPlatform(f"Could not create path to binary from {platform.uname()} we only support {default_path.keys()}")
    return Path(fallback)


__HTML2MD: Path = __get_html2md()


"""
Wrapper module around html2md binary
"""


# mypy: ignore-errors


def to_markdown(html: str, binary_path: Path = __HTML2MD) -> str:
    """Convert HTML XML string to Markdown using an external binary or a Python library.

    In acknowledge to https://github.com/suntong/html2md.

    Parameters
    ----------
    html : str
        The input HTML/XML string to be converted to Markdown.
    binary_path : Path, optional
        The path to the html2md binary (default is './html2md').

    Returns
    -------
    str
        The resulting Markdown string.

    Notes
    -----
    This function first checks if the html2md binary is available. If not, it raises an error.
    The binary path can be specified in the environment variable 'HTML2MD_BINARY_PATH'.

    The html2md binary can be found at: https://github.com/suntong/html2md

    Examples
    --------
    >>> from pathlib import Path
    >>> html = '<h1>Title</h1><p>Hello, world!</p>'
    >>> markdown = to_markdown(html)
    >>> print(markdown)
    # Title
    Hello, world!

    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w+") as file:
        cleaned_html = clean_html(html)
        file.write(cleaned_html)
        file.close()
        convert_cmd = f"{binary_path.absolute().as_posix()} -i {file.name}"
        status_code, markdown = subprocess.getstatusoutput(convert_cmd)
        Path(file.name).unlink()
    if status_code != 0:
        raise MarkdownConvertFailed(f"{binary_path} returned {status_code} ({markdown} based on {html})")
    if not markdown.replace(" ", "").replace("\n", ""):
        raise MarkdownConvertFailed(f"Failed to convert {html} to md {markdown}")
    return markdown


def remove_images(markdown: str) -> str:
    """Recursively remove image and thematic break tokens from a Markdown string.

    This function processes a Markdown string, removes any image and thematic break
    tokens, and returns the cleaned Markdown content.

    markdown : str
        The input Markdown string to be processed.

    str
        The cleaned Markdown string with image and thematic break tokens removed.
    """

    def _to_markdown(doc: Document) -> str:
        with MarkdownRenderer() as renderer:
            rendered = renderer.render(doc)
        # Adjust for excessive newlines
        return re.sub(r"\n\n+", "\n\n", rendered)

    def _remove_image_from_document(doc: Document) -> Document:
        if not hasattr(doc, "children") or not doc.children:
            return doc
        doc.children = [_remove_image_from_document(x) for x in doc.children if not isinstance(x, (Image, ThematicBreak))]
        return doc

    doc = Document(markdown)
    cleaned = _remove_image_from_document(doc)
    return _to_markdown(cleaned)


def clean_tree(div: lxml.etree.ElementBase) -> lxml.etree.ElementBase:
    """Cleans the lxml.html tree from html unneded html obstacales."""
    # Remove all link or script tags
    for tag in ["script", "link", "style", "svg", "footer"]:
        for bad in div.xpath("//" + tag):
            bad.getparent().remove(bad)
    # replace img with it's alt text
    for img in div.xpath("//img"):
        alt_text = img.get("alt", "")
        # Create a text node with the alt text
        text_node = lxml.html.Element("span")
        text_node.text = alt_text
        # Replace the img tag with the text node
        img.addnext(text_node)
        img.getparent().remove(img)

    for bad in div.xpath("//div[@id='js-footer']"):
        bad.getparent().remove(bad)

    return div


def clean_html(html: str) -> str:
    """Clean HTML string."""
    tree = lxml.html.fromstring(html)
    cleaned_tree = clean_tree(tree)
    cleaned_html = lxml.html.tostring(cleaned_tree).decode()
    return cleaned_html


def normalize_urls_in_tree(tree: lxml.html.HtmlElement, base_url: str = "https://www.magenta.at"):
    """Normalizes all relative URLs within an lxml HTML tree by converting them to absolute URLs.

    This function searches through the parsed HTML tree (`tree`) for elements that contain
    `href` or `src` attributes (commonly found in `<a>`, `<img>`, `<link>`, etc.), and if the value
    of these attributes is a relative URL (starting with `/`), it replaces the relative path with an
    absolute URL based on the provided `base_url`.

    Args:
        tree (lxml.html.HtmlElement): The root element of the parsed HTML tree.
        base_url (str, optional): The base URL to be used for converting relative URLs to absolute URLs.
                                  Defaults to "https://www.magenta.at".

    Example:
        If an element has a `href` or `src` like "/faq", it will be replaced with "https://www.magenta.at/faq".

    Returns:
        None: The function modifies the HTML tree in place.

    """
    # List of attributes to check for relative URLs
    attributes = ["href", "src"]

    # Loop over all elements that could have relative URLs
    for element in tree.xpath("//*[@href or @src]"):
        for attr in attributes:
            url = element.get(attr)
            if url and url.startswith("/"):
                # Replace with the absolute URL
                element.set(attr, base_url + url)
    return tree


def normalize_urls(html_content: str, base_url: str = "https://www.magenta.at"):
    """Converts all relative URLs in the provided HTML content to absolute URLs.

    This function parses the input HTML content, searches for elements with
    attributes that typically contain URLs (such as `href` and `src`), and
    replaces any URLs that start with a relative path (e.g., `/path`) with
    an absolute URL. The base URL used for this transformation is specified
    by the `base_url` parameter, which defaults to "https://www.magenta.at".

    Args:
        html_content (str): The HTML content as a string where relative URLs
                            need to be normalized.
        base_url (str): The base URL to prepend to relative URLs. Defaults to
                        "https://www.magenta.at".

    Returns:
        str: The HTML content with all relative URLs replaced by absolute URLs.

    """
    tree = lxml.html.fromstring(html_content)
    tree = normalize_urls_in_tree(tree, base_url)
    return html2str(tree)


def html2str(html: lxml) -> str:
    """Convert an lxml HTML element to a string.

    Args:
        html (lxml): The lxml HTML element to be converted.

    Returns:
        str: The HTML content as a string.

    """
    return lxml.html.tostring(html, pretty_print=False, method="html").decode("utf-8")
