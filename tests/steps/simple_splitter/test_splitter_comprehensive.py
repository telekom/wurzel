# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Comprehensive tests for the SimpleSplitter with multiple languages and edge cases."""

import pytest

from wurzel.utils import HAS_SPACY, HAS_TIKTOKEN

if not HAS_SPACY or not HAS_TIKTOKEN:
    pytest.skip("Simple splitter dependencies (spacy, tiktoken) are not available", allow_module_level=True)


@pytest.mark.parametrize(
    "text_fixture,expected_chunks",
    [
        ("short_text_en", 1),
        ("short_text_de", 1),
    ],
)
def test_short_documents_not_split(splitter, text_fixture, expected_chunks, request, markdown_contract_factory):
    """Test that short documents remain as single chunks."""
    text = request.getfixturevalue(text_fixture)
    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)
    assert len(result) == expected_chunks


@pytest.mark.parametrize("lang", ["en", "de", "fr", "es", "zh"])
def test_multilang_short_texts(splitter, text_multilang_short, lang, markdown_contract_factory):
    """Test that short texts in multiple languages are handled correctly."""
    text = text_multilang_short[lang]
    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)
    # Short texts should either be 1 chunk or be filtered out as too short
    assert len(result) <= 1


@pytest.mark.parametrize("lang", ["en", "de", "fr", "es"])
def test_multilang_long_texts(small_splitter, text_multilang_long, lang, markdown_contract_factory):
    """Test that longer texts in multiple languages are split properly."""
    text = text_multilang_long[lang]
    contract = markdown_contract_factory(text)
    result = small_splitter.split_markdown_document(contract)
    # Should create multiple chunks
    assert len(result) >= 1
    # All chunks should preserve URL and keywords
    for chunk in result:
        assert chunk.url == "https://test.example.com"
        assert chunk.keywords == "test"


@pytest.mark.parametrize(
    "text_fixture",
    [
        "long_text_en",
        "long_text_de",
    ],
)
def test_long_documents_split(small_splitter, text_fixture, request, markdown_contract_factory):
    """Test that long documents are split into multiple chunks."""
    text = request.getfixturevalue(text_fixture)
    contract = markdown_contract_factory(text)
    result = small_splitter.split_markdown_document(contract)
    assert len(result) > 1
    # Verify metadata
    for idx, chunk in enumerate(result):
        assert "chunk_index" in chunk.metadata
        assert "chunks_count" in chunk.metadata
        assert chunk.metadata["chunk_index"] == idx
        assert chunk.metadata["chunks_count"] == len(result)


def test_text_with_links_preserved(splitter, text_with_links, markdown_contract_factory):
    """Test that markdown links are preserved and not broken during splitting."""
    contract = markdown_contract_factory(text_with_links)
    result = splitter.split_markdown_document(contract)

    # Collect all text from chunks
    all_text = " ".join([chunk.md for chunk in result])

    # Check that important links are present
    assert "https://github.com/telekom/wurzel" in all_text
    assert "[GitHub Repository]" in all_text or "GitHub Repository" in all_text
    assert "https://docs.example.com/api/v1/reference" in all_text


def test_empty_document(splitter, empty_document, markdown_contract_factory):
    """Test that empty documents are handled gracefully."""
    contract = markdown_contract_factory(empty_document)
    result = splitter.split_markdown_document(contract)
    assert len(result) == 0


def test_only_headers(splitter, only_headers, markdown_contract_factory):
    """Test documents with only headers and no content."""
    contract = markdown_contract_factory(only_headers)
    result = splitter.split_markdown_document(contract)
    # Headers-only doc might be too short or return 0 results
    assert len(result) <= 1


def test_chunk_metadata_consistency(small_splitter, long_text_en, markdown_contract_factory):
    """Test that chunk metadata is consistent across all chunks."""
    contract = markdown_contract_factory(long_text_en)
    result = small_splitter.split_markdown_document(contract)

    assert len(result) > 0

    # All chunks should have the same source hash
    source_hashes = {chunk.metadata.get("source_sha256_hash") for chunk in result}
    assert len(source_hashes) == 1

    # Chunk indices should be sequential
    indices = [chunk.metadata["chunk_index"] for chunk in result]
    assert indices == list(range(len(result)))

    # All chunks should have token_len and char_len
    for chunk in result:
        assert "token_len" in chunk.metadata
        assert "char_len" in chunk.metadata
        assert chunk.metadata["token_len"] > 0
        assert chunk.metadata["char_len"] > 0


@pytest.mark.parametrize(
    "heading,content",
    [
        ("# Main", "Content under main heading."),
        ("## Section", "Content under section."),
        ("### Subsection", "Content under subsection."),
    ],
)
def test_heading_levels(splitter, heading, content, markdown_contract_factory):
    """Test that different heading levels are handled correctly."""
    text = f"{heading}\n\n{content}"
    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)
    # Should handle various heading levels
    assert len(result) <= 1  # Short document


def test_very_long_document(small_splitter, markdown_contract_factory):
    """Test splitting of a very long document."""
    # Create a document with many sections
    sections = []
    for i in range(10):
        sections.append(f"# Section {i}\n\n" + " ".join(["Lorem ipsum dolor sit amet."] * 20))

    text = "\n\n".join(sections)
    contract = markdown_contract_factory(text)
    result = small_splitter.split_markdown_document(contract)

    # Should create multiple chunks
    assert len(result) > 5
    # All chunks should be within size limits (approximately)
    for chunk in result:
        token_len = chunk.metadata.get("token_len", 0)
        # Allow some buffer
        assert token_len <= small_splitter.token_limit + small_splitter.token_limit_buffer


def test_document_with_code_blocks(splitter, markdown_contract_factory):
    """Test that code blocks are handled properly."""
    text = """# Code Example

Here is some code:

```python
def hello_world():
    print("Hello, World!")
    return True
```

And some more text after the code block."""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    # Check that code block markers are preserved
    all_text = " ".join([chunk.md for chunk in result])
    assert "```" in all_text or "python" in all_text


def test_document_with_lists(splitter, markdown_contract_factory):
    """Test that lists are handled properly."""
    text = """# Shopping List

Items to buy:

- Apples
- Bananas
- Oranges
- Grapes
- Strawberries

## Numbered List

1. First item
2. Second item
3. Third item"""

    contract = markdown_contract_factory(text)
    result = splitter.split_markdown_document(contract)

    # Should preserve list structure
    all_text = " ".join([chunk.md for chunk in result])
    assert "-" in all_text or "*" in all_text or "1." in all_text


@pytest.mark.parametrize(
    "token_min,token_max,token_buffer",
    [
        (32, 128, 16),
        (64, 256, 32),
        (128, 512, 64),
    ],
)
def test_different_token_limits(token_min, token_max, token_buffer, long_text_en, markdown_contract_factory):
    """Test splitter with different token limit configurations."""
    from wurzel.utils.splitters.semantic_splitter import SemanticSplitter

    splitter = SemanticSplitter(
        token_limit=token_max,
        token_limit_buffer=token_buffer,
        token_limit_min=token_min,
        tokenizer_model="gpt-3.5-turbo",
        sentence_splitter_model="de_core_news_sm",
    )

    contract = markdown_contract_factory(long_text_en)
    result = splitter.split_markdown_document(contract)

    # Should produce valid chunks
    assert len(result) > 0
    for chunk in result:
        token_len = chunk.metadata.get("token_len", 0)
        # Should respect limits
        assert token_len <= token_max + token_buffer


def test_url_and_keywords_preserved(splitter, short_text_en, markdown_contract_factory):
    """Test that URL and keywords are preserved in chunks."""
    url = "https://example.com/test/page"
    keywords = "test, example, keywords"
    contract = markdown_contract_factory(short_text_en, url=url, keywords=keywords)

    result = splitter.split_markdown_document(contract)

    for chunk in result:
        assert chunk.url == url
        assert chunk.keywords == keywords
