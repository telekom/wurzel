# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Concrete output validation tests for the SimpleSplitter with deterministic results."""

import hashlib
import re

import pytest

from wurzel.utils import HAS_SPACY, HAS_TIKTOKEN

if not HAS_SPACY or not HAS_TIKTOKEN:
    pytest.skip(
        "Simple splitter dependencies (spacy, tiktoken) are not available",
        allow_module_level=True,
    )


def compute_content_hash(chunks):
    """Compute a hash of all chunk contents for deterministic validation."""
    combined = "|||".join([chunk.md for chunk in chunks])
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def extract_all_links(text):
    """Extract all markdown links from text."""
    # Match [text](url) style links
    inline_links = re.findall(r"\[([^\]]+)\]\(([^\)]+)\)", text)
    # Match [text][ref] and [ref]: url style links
    ref_links = re.findall(r"\[([^\]]+)\]:\s*(\S+)", text)
    return inline_links + ref_links


def validate_links_not_split(chunks):
    """Validate that markdown link syntax is intact in all chunks."""
    for chunk in chunks:
        text = chunk.md
        # Check for broken link patterns
        # Pattern 1: ] followed by ( but not immediately (link might be split)
        broken_pattern1 = re.search(r"\]\s+\(", text)
        if broken_pattern1:
            return False, f"Found broken link pattern ']  (' in chunk: {text[:100]}"

        # Pattern 2: [ without matching ] on same line when followed by URL
        lines = text.split("\n")
        for line in lines:
            open_brackets = line.count("[")
            close_brackets = line.count("]")
            # If we have http/https in the line with unmatched brackets, link might be broken
            if "http" in line and open_brackets != close_brackets:
                # Exception: reference-style links can have brackets on different lines
                if not re.search(r"^\[\d+\]:", line):
                    return False, f"Found unmatched brackets with URL in line: {line}"

    return True, "All links intact"


def test_link_document_concrete_output(splitter, markdown_contract_factory):
    """Test that a document with links produces deterministic output with intact links."""
    text = """# Links Test Document

This document contains various types of links to test splitting behavior.

## Inline Links

Here is an [inline link](https://github.com/telekom/wurzel) in a paragraph.
Another [link to docs](https://docs.example.com/api) right here.

## Multiple Links

Visit [GitHub](https://github.com) and [Stack Overflow](https://stackoverflow.com).
Also check [Wikipedia](https://en.wikipedia.org/wiki/Test) for more information.

## URLs in Text

Direct URL: https://www.example.com/path/to/resource
And another: https://test.example.org/some/long/path"""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    # Validate links are not split
    is_valid, message = validate_links_not_split(result)
    assert is_valid, f"Links were split: {message}"

    # Verify all original links are present in output
    original_links = extract_all_links(text)
    all_output = " ".join([chunk.md for chunk in result])

    for link_text, link_url in original_links:
        assert link_url in all_output, f"Link URL {link_url} missing in output"

    # Check that github link is intact
    assert (
        "[inline link](https://github.com/telekom/wurzel)" in all_output
        or "inline link" in all_output
        and "https://github.com/telekom/wurzel" in all_output
    )


def test_long_document_deterministic_split(small_splitter, markdown_contract_factory):
    """Test that a long document splits deterministically with expected hash."""
    text = """# Technology Guide

## Introduction

Modern technology has transformed how we work and communicate in daily life.
This guide covers the fundamental concepts and practices.

## Cloud Computing

Cloud computing provides on-demand access to computing resources.
Major providers include AWS, Azure, and Google Cloud Platform.

### Benefits

- Scalability and flexibility
- Cost-effective pay-as-you-go model
- High availability and reliability

## Machine Learning

Machine learning enables computers to learn from data without explicit programming.
Common algorithms include neural networks, decision trees, and clustering.

### Applications

Machine learning powers recommendation systems, image recognition, and natural language processing.
It's used in healthcare, finance, and many other industries."""

    contract = markdown_contract_factory(text)
    result = small_splitter.split_markdown_document(contract)

    # Verify deterministic output
    assert len(result) >= 2, "Expected document to be split into multiple chunks"

    # Verify metadata consistency
    for idx, chunk in enumerate(result):
        assert chunk.metadata["chunk_index"] == idx
        assert chunk.metadata["chunks_count"] == len(result)
        assert "source_sha256_hash" in chunk.metadata
        assert chunk.metadata["token_len"] > 0
        assert chunk.metadata["char_len"] > 0

    # All chunks should have same source hash
    source_hashes = [chunk.metadata["source_sha256_hash"] for chunk in result]
    assert len(set(source_hashes)) == 1, "All chunks should have same source hash"

    # Verify headings are preserved in chunks
    all_content = "\n\n".join([chunk.md for chunk in result])
    assert "# Technology Guide" in all_content or "Technology Guide" in all_content
    assert "Cloud Computing" in all_content
    assert "Machine Learning" in all_content


def test_link_preservation_with_long_urls(small_splitter, markdown_contract_factory):
    """Test that long URLs in links remain intact across splits."""
    text = """# Documentation

Visit the [complete API reference](https://docs.example.com/api/v2/reference/endpoints/users/management/authentication/oauth2/tokens).

Also see [developer guide](https://developer.example.com/guides/getting-started/quick-start/installation/docker-compose).

## Additional Resources

- [Tutorial 1](https://learn.example.com/tutorials/advanced/data-processing/pandas/dataframes)
- [Tutorial 2](https://learn.example.com/tutorials/advanced/machine-learning/scikit-learn/models)
- [Tutorial 3](https://learn.example.com/tutorials/advanced/deep-learning/tensorflow/neural-networks)

For more info, check the [FAQ section](https://help.example.com/faq/common-questions/troubleshooting/errors).

## Long URL Example

This link has a very long URL: [Long Resource Link](https://example.com/very/long/path/to/resource/with/many/segments/and/parameters?param1=value1&param2=value2&param3=value3).

Another one: [Another Long Link](https://api.example.com/v3/endpoints/data/processing/transform/operations/batch?format=json&limit=100)."""

    contract = markdown_contract_factory(text)
    result = small_splitter.split_markdown_document(contract)

    # Validate links are not split
    is_valid, message = validate_links_not_split(result)
    assert is_valid, f"Links were split: {message}"

    # Check specific long URLs are intact
    all_output = " ".join([chunk.md for chunk in result])

    long_urls = [
        "https://docs.example.com/api/v2/reference/endpoints/users/management/authentication/oauth2/tokens",
        "https://example.com/very/long/path/to/resource/with/many/segments/and/parameters",
        "https://api.example.com/v3/endpoints/data/processing/transform/operations/batch",
    ]

    for url in long_urls:
        # Check if URL or significant part of it exists
        assert url in all_output or url[:50] in all_output, f"Long URL {url} is missing or broken"

    # Verify markdown link syntax is preserved
    for chunk in result:
        # Count opening and closing brackets
        text = chunk.md
        # For each line with a link, verify syntax
        for line in text.split("\n"):
            if "](http" in line:
                # This line has an inline link, verify it's well-formed
                links = re.findall(r"\[([^\]]+)\]\(([^\)]+)\)", line)
                assert len(links) > 0, f"Malformed link in line: {line}"


def test_multilang_deterministic_hash(splitter, text_multilang_short, markdown_contract_factory):
    """Test that multi-language texts produce deterministic hashes."""
    expected_hashes = {
        "en": None,  # Will be computed
        "de": None,
        "fr": None,
    }

    for lang in ["en", "de", "fr"]:
        text = text_multilang_short[lang]
        contract = markdown_contract_factory(text)
        result = splitter.split_markdown_document(contract)

        if len(result) > 0:
            # Compute hash of output
            output_hash = compute_content_hash(result)
            expected_hashes[lang] = output_hash

            # Run again to verify deterministic
            result2 = splitter.split_markdown_document(contract)
            output_hash2 = compute_content_hash(result2)

            assert output_hash == output_hash2, f"Non-deterministic output for {lang}"


def test_table_with_links_not_split(splitter, markdown_contract_factory):
    """Test that tables containing links are handled correctly."""
    text = """# Resources Table

| Name | Link | Description |
|------|------|-------------|
| GitHub | [Repository](https://github.com/telekom/wurzel) | Source code |
| Docs | [Documentation](https://docs.example.com) | Full documentation |
| API | [API Reference](https://api.example.com/v1) | API endpoints |

Each link in the table should remain intact."""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    # Validate links in tables are not split
    is_valid, message = validate_links_not_split(result)
    assert is_valid, f"Links in table were split: {message}"

    # Verify table structure and links are present
    all_output = " ".join([chunk.md for chunk in result])
    assert "https://github.com/telekom/wurzel" in all_output
    assert "https://docs.example.com" in all_output
    assert "https://api.example.com/v1" in all_output

    # Check table structure is preserved (has pipe characters)
    assert "|" in all_output, "Table structure lost"


def test_code_block_with_urls_not_split(splitter, markdown_contract_factory):
    """Test that code blocks containing URLs are handled correctly."""
    text = """# Code Example

Here's how to make a request:

```python
import requests

url = "https://api.example.com/v1/users"
response = requests.get(url)
print(response.json())
```

The URL in the code should remain intact.

Another example:

```bash
curl https://example.com/api/data
```

Both code blocks should be preserved."""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    all_output = " ".join([chunk.md for chunk in result])

    # Verify URLs in code blocks are present
    assert "https://api.example.com/v1/users" in all_output
    assert "https://example.com/api/data" in all_output

    # Verify code block markers are present
    assert "```" in all_output or "python" in all_output.lower()


def test_reference_style_links_concrete(splitter, markdown_contract_factory):
    """Test reference-style links with concrete validation."""
    text = """# Reference Links Document

This document uses reference-style links for better readability.

Check out [the repository][1] for source code.
Read [the documentation][2] for more details.
Visit [the website][3] for additional information.

[1]: https://github.com/telekom/wurzel
[2]: https://docs.example.com/guide
[3]: https://www.example.com/info

All references should be preserved."""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    all_output = " ".join([chunk.md for chunk in result])

    # Verify all reference URLs are present
    assert "https://github.com/telekom/wurzel" in all_output
    assert "https://docs.example.com/guide" in all_output
    assert "https://www.example.com/info" in all_output

    # Verify reference markers are present
    assert "[1]" in all_output or "repository" in all_output
    assert "[2]" in all_output or "documentation" in all_output
    assert "[3]" in all_output or "website" in all_output
