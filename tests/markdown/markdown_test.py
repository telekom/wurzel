# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import tempfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from wurzel.exceptions import InvalidPlatform, MarkdownConvertFailed
from wurzel.utils.to_markdown.html2md import __get_html2md, remove_images, to_markdown

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Webpage</title>
</head>
<body>
    <header>
        <h1>Welcome to My Webpage</h1>
    </header>
    <main>
        <p>
            Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer nec odio. Praesent libero.
            Sed cursus ante dapibus diam. Sed nisi. Nulla quis sem at nibh elementum imperdiet. Duis
            sagittis ipsum. Praesent mauris. Fusce nec tellus sed augue semper porta. Mauris massa.
            Vestibulum lacinia arcu eget nulla. Class aptent taciti sociosqu ad litora torquent per
            conubia nostra, per inceptos himenaeos. Curabitur sodales ligula in libero. Sed dignissim
            lacinia nunc. Curabitur tortor. Pellentesque nibh. Aenean quam. In scelerisque sem at dolor.
            Maecenas mattis. Sed convallis tristique sem. Proin ut ligula vel nunc egestas porttitor.
            Morbi lectus risus, iaculis vel, suscipit quis, luctus non, massa. Fusce ac turpis quis ligula
            lacinia aliquet. Mauris ipsum. Nulla metus metus, ullamcorper vel, tincidunt sed, euismod in,
            nibh. Quisque volutpat condimentum velit. Class aptent taciti sociosqu ad litora torquent per
            conubia nostra, per inceptos himenaeos. Nam nec ante. Sed lacinia, urna non tincidunt mattis,
            tortor neque adipiscing diam, a cursus ipsum ante quis turpis. Nulla facilisi. Ut fringilla.
            Suspendisse potenti. Nunc feugiat mi a tellus consequat imperdiet. Vestibulum sapien. Proin
            quam. Etiam ultrices. Suspendisse in justo eu magna luctus suscipit.
        </p>
    </main>

    <footer>
        <p>&copy; 2024 My Webpage. All rights reserved.</p>
    </footer>
</body>
</html>

"""


def test_to_markdown_long():
    markdown: str = to_markdown(HTML)

    assert "Lorem ipsum dolor sit amet, consectetur adipiscing elit" in markdown, markdown
    assert "# Welcome to My Webpage" in markdown, markdown


def test_to_markdown_and_remove_images_integration():
    """Test integration of `to_markdown` and `remove_images` methods.

    Parameters
    ----------
    converter : ConvertToMarkdown
        An instance of ConvertToMarkdown.

    """
    html_content = "<p>This is a test</p><img src='test.jpg'/>"
    markdown_content = remove_images(html_content)
    assert "![img](test.jpg)" not in markdown_content
    assert "This is a test" in markdown_content


def test_to_markdown():
    """Test handling of invalid binary."""
    html_content = "<h1>hello-world</h1><p>text</p>."
    r = to_markdown(html=html_content)
    assert r.startswith("#")
    assert "hello-world" in r
    assert "text" in r


def test_failed_to_markdown():
    """Test handling of invalid content."""
    html_content = "<a></a>"
    with pytest.raises(MarkdownConvertFailed):
        _ = to_markdown(html=html_content)


@patch("platform.uname")
def test_file_not_found_error(mock_is_file):
    """Test handling of FileNotFoundError."""
    # Simulate the html2md binary file not being found
    mock_is_file.return_value = Namespace(machine="invalid_platform_mock", system="invalid_platform_mock_system")
    with pytest.raises(InvalidPlatform):
        __get_html2md()


def test_failed_to_markdown_invalid_binary():
    """Test handling of invalid binary."""
    html_content = "<h1>hello-world</h1><p>text</p>."
    with tempfile.NamedTemporaryFile("wb") as file:
        file.write(b"hello-world")
        with pytest.raises(MarkdownConvertFailed):
            _ = to_markdown(html=html_content, binary_path=Path(file.name))


def test_html2md():
    from wurzel.utils.to_markdown.html2md import __HTML2MD

    assert isinstance(__HTML2MD, Path)
