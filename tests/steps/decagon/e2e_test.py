# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""End-to-end tests for DecagonKnowledgeBaseStep.

These tests make real API calls to Decagon. They are skipped unless
DECAGONKBSTEP__API_KEY is set in the environment.

Run with:
    DECAGONKBSTEP__API_KEY=your-key pytest tests/steps/decagon/ -v
"""

import os

import pytest

from wurzel.datacontract import MarkdownDataContract
from wurzel.steps.decagon import DecagonKnowledgeBaseStep

# Skip all tests if API key is not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("DECAGONKBSTEP__API_KEY"),
    reason="DECAGONKBSTEP__API_KEY not set - skipping real API tests",
)


class TestDecagonKnowledgeBaseStep:
    """Integration tests for DecagonKnowledgeBaseStep with real API calls."""

    def test_empty_input_returns_empty_dataframe(self):
        """Test that empty input returns an empty DataFrame."""
        step = DecagonKnowledgeBaseStep()
        result = step.run([])

        assert len(result) == 0
        assert "article_id" in result.columns
        assert "status" in result.columns
        step.finalize()

    def test_single_document_chunked_and_created(self):
        """Test successful chunking and creation of a single document."""
        doc = MarkdownDataContract(
            md="# Test Article\n\nThis is test content from wurzel integration tests.",
            url="https://example.com/wurzel-test",
            keywords="test, wurzel, integration",
            metadata={"test": True},
        )

        step = DecagonKnowledgeBaseStep()
        result = step.run([doc])
        step.finalize()

        assert len(result) >= 1
        assert all(result["status"] == "success"), f"Failures: {result[result['status'] == 'failed']['error'].tolist()}"
        assert all(result["article_id"].notna())

    def test_multiple_documents(self):
        """Test processing multiple documents."""
        docs = [
            MarkdownDataContract(
                md=f"# Test Doc {i}\n\nContent for document {i}.",
                url=f"https://example.com/wurzel-test-{i}",
                keywords="test",
            )
            for i in range(3)
        ]

        step = DecagonKnowledgeBaseStep()
        result = step.run(docs)
        step.finalize()

        assert len(result) >= 3
        success_count = (result["status"] == "success").sum()
        assert success_count >= 3, f"Expected at least 3 successes, got {success_count}"

    def test_metadata_preserved(self):
        """Test that metadata is preserved in results."""
        doc = MarkdownDataContract(
            md="# Metadata Test\n\nChecking metadata preservation.",
            url="https://example.com/metadata-test",
            keywords="meta, test",
            metadata={"author": "wurzel-tests", "version": "1.0"},
        )

        step = DecagonKnowledgeBaseStep()
        result = step.run([doc])
        step.finalize()

        assert len(result) >= 1
        # Check original metadata is preserved
        assert result.iloc[0]["metadata"]["author"] == "wurzel-tests"
        assert "chunk_index" in result.iloc[0]["metadata"]
        assert "total_chunks" in result.iloc[0]["metadata"]
