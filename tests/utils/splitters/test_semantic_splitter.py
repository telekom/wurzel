# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.datacontract import MarkdownDataContract
from wurzel.steps.splitter import SimpleSplitterStep

SMALL_MARKDOWN = "Short Document\nThis is a small document that should not be split.\nIt contains only a few sentences."

LONG_MARKDOWN_WITH_HEADINGS = (
    "# Main Title\n\n"
    "## Section 1\n\n"
    "This is the first section with some content. " * 50 + "\n\n"
    "## Section 2\n\n"
    "This is the second section with more content. " * 50 + "\n\n"
    "### Subsection 2.1\n\n"
    "This is a subsection with additional details. " * 50 + "\n\n"
    "## Section 3\n\n"
    "This is the third section with even more content. " * 50 + "\n\n"
    "## Section 4\n\n"
    "This is the fourth section. " * 50
)

LONG_MARKDOWN_WITH_PARAGRAPHS = (
    "This is a very long paragraph that will be split by sentences. " * 100
    + "Each sentence should be properly handled. " * 100
    + "The splitter should use sentence boundaries. " * 100
    + "This ensures semantic coherence in the chunks. " * 100
)

MARKDOWN_WITH_TABLE = (
    "# Data Table\n\n"
    "| Column 1 | Column 2 | Column 3 |\n"
    "|----------|----------|----------|\n"
    "| Value 1  | Value 2  | Value 3  |\n" * 200 + "| Value 4  | Value 5  | Value 6  |\n" * 200
)

MARKDOWN_WITH_LISTS = (
    "# List Document\n\n"
    "## Unordered List\n\n"
    "- Item 1 with some description\n" * 50 + "- Item 2 with more details\n" * 50 + "\n## Ordered List\n\n"
    "1. First item with content\n" * 50 + "2. Second item with more content\n" * 50 + "3. Third item with additional details\n" * 50
)


MIXED_MARKDOWN = (
    "# Comprehensive Document\n\n"
    "## Introduction\n\n"
    "This document contains various markdown elements. " * 30 + "\n\n"
    "## Table Section\n\n"
    "| Header 1 | Header 2 |\n|----------|----------|\n" + "| Data 1   | Data 2   |\n" * 50 + "\n## Code Section\n\n"
    "```python\nprint('Hello')\n```\n\n"
    "## List Section\n\n"
    "- Item A\n" * 30 + "- Item B\n" * 30 + "\n## Conclusion\n\n"
    "Final thoughts and summary. " * 50
)


@pytest.mark.parametrize(
    "markdown_content,description,expected_chunks_range,expect_newline",
    [
        # Small document - should not split (below token limit)
        (
            SMALL_MARKDOWN,
            "small_document_no_split",
            (1, 1),  # Should remain as 1 chunk
            False,
        ),
        # Long document with headings - semantic splitting by headings
        (
            LONG_MARKDOWN_WITH_HEADINGS,
            "long_with_headings_semantic_split",
            (2, 10),  # Should split into multiple chunks based on headings
            True,
        ),
        # Long document with paragraphs - sentence splitting
        (
            LONG_MARKDOWN_WITH_PARAGRAPHS,
            "long_with_paragraphs_sentence_split",
            (2, 20),  # Should split by sentences
            True,
        ),
        # Document with table - table splitting
        (
            MARKDOWN_WITH_TABLE,
            "markdown_with_table",
            (2, 15),  # Should split table into chunks
            True,
        ),
        # Document with lists - list splitting
        (
            MARKDOWN_WITH_LISTS,
            "markdown_with_lists",
            (2, 10),  # Should split by list items
            True,
        ),
        # Mixed markdown - various splitting strategies
        (
            MIXED_MARKDOWN,
            "mixed_markdown",
            (2, 15),  # Should use multiple splitting strategies
            True,
        ),
    ],
)
def test_splitter_various_markdown_types(markdown_content, description, expected_chunks_range, expect_newline, env):
    """Test splitter with various markdown types and splitting approaches."""
    # Set lower min token count to allow small documents in tests
    env.set("TOKEN_COUNT_MIN", "1")
    env.set("TOKEN_COUNT_MAX", "1024")

    step = SimpleSplitterStep()
    doc = MarkdownDataContract(
        md=markdown_content,
        url="https://example.com/test",
        keywords="test keywords",
    )

    output_docs = step.run([doc])
    num_chunks = len(output_docs)

    joined_text = "\n".join(doc.md for doc in output_docs)
    original_newline_count = doc.md.count("\n")
    new_newline_count = joined_text.count("\n")

    min_chunks, max_chunks = expected_chunks_range

    if not expect_newline:
        assert original_newline_count == new_newline_count

    # Verify chunk count is within expected range
    assert min_chunks <= num_chunks <= max_chunks, (
        f"Expected {min_chunks}-{max_chunks} chunks for {description}, but got {num_chunks} chunks"
    )


@pytest.mark.parametrize(
    "markdown_content,should_not_split",
    [
        # Very small documents that should not be split
        ("# Tiny\nShort text.", True),
        ("Just a few words here.", True),
        ("# Title\n\nOne paragraph only.", True),
        # Documents that should be split
        (LONG_MARKDOWN_WITH_HEADINGS, False),
        (LONG_MARKDOWN_WITH_PARAGRAPHS, False),
    ],
)
def test_splitter_small_vs_large_documents(markdown_content, should_not_split, env):
    """Test that small documents are not split while large ones are."""
    # Set lower min token count to allow small documents in tests
    env.set("TOKEN_COUNT_MIN", "1")
    env.set("TOKEN_COUNT_MAX", "256")

    step = SimpleSplitterStep()
    doc = MarkdownDataContract(
        md=markdown_content,
        url="https://example.com/test",
        keywords="test",
    )
    original_url = doc.url
    original_keywords = doc.keywords
    output_docs = step.run([doc])

    token_limit = step.splitter.token_limit

    if should_not_split:
        # Small document should remain as single chunk
        assert len(output_docs) == 1, "Small document should not be split"
        # For small documents, content should be preserved (early return path)
        # Token count should be below limit
        assert output_docs[0].metadata["token_len"] <= token_limit, (
            f"Small document token count {output_docs[0].metadata['token_len']} should be within limit {token_limit}"
        )

        assert len(output_docs[0].md) > 0, "Markdown content should not be empty"
    else:
        # Large document should be split
        assert len(output_docs) > 1, "Large document should be split into multiple chunks"
        # Verify chunks don't exceed token limit
        for chunk in output_docs:
            assert chunk.metadata["token_len"] <= token_limit, (
                f"Chunk token count {chunk.metadata['token_len']} exceeds limit {token_limit}"
            )

    # All chunks should preserve url and keywords
    for chunk in output_docs:
        assert chunk.url == original_url, "URL should be preserved in all chunks"
        assert chunk.keywords == original_keywords, "Keywords should be preserved in all chunks"
