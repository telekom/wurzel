# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Additional edge case tests for the SimpleSplitter."""

import pytest

from wurzel.utils import HAS_SPACY, HAS_TIKTOKEN

if not HAS_SPACY or not HAS_TIKTOKEN:
    pytest.skip(
        "Simple splitter dependencies (spacy, tiktoken) are not available",
        allow_module_level=True,
    )


def test_link_preservation_inline(splitter, markdown_contract_factory):
    """Test that inline links in paragraphs are preserved and not split."""
    text = """# Links Test

This is a paragraph with an [inline link](https://github.com/telekom/wurzel)
that should not be broken during splitting.

Visit [example.com](https://www.example.com) for more info."""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    all_text = " ".join([chunk.md for chunk in result])

    # Verify both link URL and text are present
    assert "https://github.com/telekom/wurzel" in all_text
    assert "https://www.example.com" in all_text

    # Verify link syntax is intact - check each chunk
    import re

    for chunk in result:
        # If chunk contains a URL, verify link syntax is not broken
        if "github.com" in chunk.md or "example.com" in chunk.md:
            # Check for proper link format [text](url)
            links = re.findall(r"\[([^\]]+)\]\(([^\)]+)\)", chunk.md)
            # If we find the URL, we should also find it in a proper link
            if "github.com/telekom/wurzel" in chunk.md:
                assert any("github.com/telekom/wurzel" in url for _, url in links), "GitHub link is not properly formatted"


def test_link_preservation_reference_style(splitter, markdown_contract_factory):
    """Test that reference-style links are preserved and not split."""
    text = """# Reference Links

Check out [this repo][1] and [that site][2].

[1]: https://github.com/telekom/wurzel
[2]: https://www.example.com"""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    all_text = " ".join([chunk.md for chunk in result])

    # Verify both URLs are present
    assert "https://github.com/telekom/wurzel" in all_text
    assert "https://www.example.com" in all_text

    # Verify reference markers are present
    assert "[1]" in all_text or "repo" in all_text
    assert "[2]" in all_text or "site" in all_text

    # Check that reference definitions are intact
    import re

    for chunk in result:
        # Look for reference definitions like [1]: url
        refs = re.findall(r"\[(\d+)\]:\s*(\S+)", chunk.md)
        for ref_num, ref_url in refs:
            # If we find a reference, verify it's a complete URL
            assert ref_url.startswith("http"), f"Incomplete reference URL: {ref_url}"


def test_very_short_document(splitter, markdown_contract_factory):
    """Test handling of very short documents below minimum token length."""
    short_texts = [
        "# Hi",
        "Test",
        "## H2",
        "* Item",
    ]

    for text in short_texts:
        contract = markdown_contract_factory(text)
        result = splitter.split_markdown_document(contract)
        # Very short docs should be filtered out
        assert len(result) <= 1


def test_document_with_tables(splitter, markdown_contract_factory):
    """Test that tables are handled properly."""
    text = """# Data Table

| Name    | Age | City   |
|---------|-----|--------|
| Alice   | 30  | Berlin |
| Bob     | 25  | Munich |
| Charlie | 35  | Hamburg|

Some text after the table."""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    # Check that table structure is present
    all_text = " ".join([chunk.md for chunk in result])
    assert "|" in all_text or "Name" in all_text


def test_mixed_heading_levels(splitter, markdown_contract_factory):
    """Test documents with mixed heading levels."""
    text = """# H1
## H2
### H3
#### H4
##### H5
###### H6

Content under various heading levels."""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    # Should handle mixed levels
    assert len(result) >= 1


def test_consecutive_headings(splitter, markdown_contract_factory):
    """Test multiple consecutive headings without content."""
    text = """# First Heading
## Second Heading
### Third Heading

Finally some content here."""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    # Should handle consecutive headings
    assert len(result) >= 1


def test_list_with_nested_items(splitter, markdown_contract_factory):
    """Test nested list structures."""
    text = """# Shopping

- Fruits
  - Apples
  - Bananas
- Vegetables
  - Carrots
  - Broccoli
- Dairy
  - Milk
  - Cheese"""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    all_text = " ".join([chunk.md for chunk in result])
    # Should preserve list structure
    assert "Fruits" in all_text or "Apples" in all_text


def test_blockquotes(splitter, markdown_contract_factory):
    """Test that blockquotes are handled."""
    text = """# Quotes

> This is a blockquote.
> It can span multiple lines.

Regular text after quote."""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    # Should process blockquotes
    assert len(result) >= 1


def test_horizontal_rules(splitter, markdown_contract_factory):
    """Test documents with horizontal rules."""
    text = """# Section 1

Content in section 1.

---

# Section 2

Content in section 2."""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    # Should handle horizontal rules
    assert len(result) >= 1


def test_special_characters(splitter, markdown_contract_factory):
    """Test handling of special characters and unicode."""
    text = """# Special Characters Test

Text with emojis 🎉 and unicode: ñ, ü, ö, 中文, العربية

Math symbols: ∑, ∏, ∫, √

Symbols: @, #, $, %, &, *, ©, ®, ™"""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    # Should handle special characters
    assert len(result) >= 1
    all_text = " ".join([chunk.md for chunk in result])
    # At least some special chars should remain
    assert "Test" in all_text or "Special" in all_text


@pytest.mark.parametrize(
    "text,description",
    [
        ("# H\n\nA.", "minimal doc"),
        ("# " + "A" * 1000, "very long heading"),
        ("\n\n\n# H\n\n\n", "excess whitespace"),
        ("*" * 100, "repetitive chars"),
    ],
)
def test_edge_case_formats(splitter, text, description, markdown_contract_factory):
    """Test various edge case document formats."""
    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    # Should handle without crashing
    assert isinstance(result, list)


def test_url_only_document(splitter, markdown_contract_factory):
    """Test document that is mostly URLs."""
    text = """# Links

https://github.com/telekom/wurzel
https://www.example.com/page1
https://www.example.com/page2
https://www.example.com/page3"""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    # URLs should be preserved
    all_text = " ".join([chunk.md for chunk in result])
    assert "https://" in all_text


def test_code_fence_with_language(splitter, markdown_contract_factory):
    """Test code blocks with language specification."""
    text = """# Code Examples

```python
def hello():
    return "world"
```

```javascript
function hello() {
    return "world";
}
```"""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    # Code should be preserved
    all_text = " ".join([chunk.md for chunk in result])
    assert "def" in all_text or "function" in all_text or "hello" in all_text


def test_mixed_content_document(small_splitter, markdown_contract_factory):
    """Test document with mixed content types."""
    text = """# Complete Document

## Introduction

This document has various content types.

### Code

```python
x = 1
```

### Lists

- Item 1
- Item 2

### Table

| Col1 | Col2 |
|------|------|
| A    | B    |

### Links

Visit [GitHub](https://github.com).

## Conclusion

That's all folks!"""

    contract = markdown_contract_factory(text)
    result = small_splitter.split_markdown_document(contract)

    # Should handle mixed content
    assert len(result) >= 1

    # Check metadata consistency
    for chunk in result:
        assert "chunk_index" in chunk.metadata
        assert "chunks_count" in chunk.metadata
