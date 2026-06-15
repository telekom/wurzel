# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for DecagonKnowledgeBaseStep with mocked API calls."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed
from wurzel.steps.decagon import DecagonKnowledgeBaseStep


@pytest.fixture
def decagon_env(env):
    """Set up required environment variables for Decagon."""
    env.set("API_KEY", "test-api-key")
    env.set("API_URL", "https://api.test.decagon.ai")
    env.set("SOURCE", "TestSource")
    return env


@pytest.fixture
def sample_doc():
    """Create a sample MarkdownDataContract."""
    return MarkdownDataContract(
        md="# Test Title\n\nThis is test content.",
        url="https://example.com/test",
        keywords="test, sample",
        metadata={"author": "tester"},
    )


@pytest.fixture
def mock_session(decagon_env):
    """Create a step with mocked session."""
    with patch("wurzel.steps.decagon.step.requests.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        step = DecagonKnowledgeBaseStep()
        yield step, mock_session
        step.finalize()


class TestDecagonKnowledgeBaseStepInit:
    """Tests for step initialization."""

    def test_init_sets_headers(self, decagon_env):
        """Test that init sets proper authorization headers."""
        with patch("wurzel.steps.decagon.step.requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session
            step = DecagonKnowledgeBaseStep()

            mock_session.headers.update.assert_called_once()
            call_args = mock_session.headers.update.call_args[0][0]
            assert call_args["Content-Type"] == "application/json"
            assert "Bearer test-api-key" in call_args["Authorization"]
            step.finalize()

    def test_init_skips_session_when_push_disabled(self, env):
        """Test that no session is created when PUSH_ENABLED is False."""
        env.set("PUSH_ENABLED", "false")
        with patch("wurzel.steps.decagon.step.requests.Session") as mock_session_cls:
            step = DecagonKnowledgeBaseStep()
            mock_session_cls.assert_not_called()
            step.finalize()


class TestEmptyInput:
    """Tests for empty input handling."""

    def test_empty_input_returns_empty_list(self, mock_session):
        """Test that empty input returns an empty list."""
        step, _ = mock_session
        result = step.run([])
        assert result == []


class TestSuccessfulProcessing:
    """Tests for successful document processing."""

    def test_single_document_success_returns_input(self, mock_session, sample_doc):
        """Test that a successfully processed document is returned unchanged."""
        step, mock_sess = mock_session

        chunk_response = MagicMock()
        chunk_response.json.return_value = {"chunks": ["chunk1", "chunk2"]}
        chunk_response.raise_for_status = MagicMock()

        article_response = MagicMock()
        article_response.json.return_value = {"article_id": 123}
        article_response.raise_for_status = MagicMock()

        mock_sess.post.side_effect = [
            chunk_response,
            article_response,
            article_response,
        ]

        result = step.run([sample_doc])

        assert result == [sample_doc]

    def test_no_chunks_returns_input(self, mock_session, sample_doc):
        """Test that when API returns no chunks, input is still returned unchanged."""
        step, mock_sess = mock_session

        chunk_response = MagicMock()
        chunk_response.json.return_value = {"chunks": None}
        chunk_response.raise_for_status = MagicMock()

        article_response = MagicMock()
        article_response.json.return_value = {"article_id": 456}
        article_response.raise_for_status = MagicMock()

        mock_sess.post.side_effect = [chunk_response, article_response]

        result = step.run([sample_doc])

        assert result == [sample_doc]

    def test_push_disabled_returns_input_without_api_calls(self, env, sample_doc):
        """Test that PUSH_ENABLED=False returns input without any API calls."""
        env.set("PUSH_ENABLED", "false")
        with patch("wurzel.steps.decagon.step.requests.Session") as mock_session_cls:
            step = DecagonKnowledgeBaseStep()
            result = step.run([sample_doc])

            mock_session_cls.assert_not_called()
            assert result == [sample_doc]
            step.finalize()


class TestChunkingFailure:
    """Tests for chunking failure scenarios."""

    def test_chunking_failure_raises_step_failed(self, mock_session, sample_doc):
        """Test that chunking failure raises StepFailed when all fail."""
        step, mock_sess = mock_session

        mock_sess.post.side_effect = requests.exceptions.ConnectionError("Connection failed")

        with pytest.raises(StepFailed, match="All 1 chunks failed"):
            step.run([sample_doc])

    def test_chunking_failure_with_some_success_does_not_raise(self, mock_session):
        """Test partial chunking failure doesn't raise StepFailed."""
        step, mock_sess = mock_session

        docs = [
            MarkdownDataContract(md="# Doc 1\nContent", url="url1", keywords=""),
            MarkdownDataContract(md="# Doc 2\nContent", url="url2", keywords=""),
        ]

        chunk_response = MagicMock()
        chunk_response.json.return_value = {"chunks": ["chunk1"]}
        chunk_response.raise_for_status = MagicMock()

        article_response = MagicMock()
        article_response.json.return_value = {"article_id": 123}
        article_response.raise_for_status = MagicMock()

        # First doc succeeds, second fails during chunking
        mock_sess.post.side_effect = [
            chunk_response,
            article_response,
            requests.exceptions.ConnectionError("Failed"),
        ]

        result = step.run(docs)
        assert result == docs


class TestArticleCreationFailure:
    """Tests for article creation failure scenarios."""

    def test_article_creation_failure_raises_step_failed(self, mock_session, sample_doc):
        """Test that article creation failure raises StepFailed when all fail."""
        step, mock_sess = mock_session

        chunk_response = MagicMock()
        chunk_response.json.return_value = {"chunks": ["chunk1"]}
        chunk_response.raise_for_status = MagicMock()

        error_response = MagicMock()
        error_response.status_code = 500
        error_response.json.return_value = {"detail": "Server error"}
        exc = requests.exceptions.HTTPError()
        exc.response = error_response

        mock_sess.post.side_effect = [chunk_response, exc]

        with pytest.raises(StepFailed, match="All 1 chunks failed"):
            step.run([sample_doc])

    def test_all_chunks_fail_raises_step_failed(self, mock_session, sample_doc):
        """Test that StepFailed is raised when all chunks fail."""
        step, mock_sess = mock_session

        chunk_response = MagicMock()
        chunk_response.json.return_value = {"chunks": ["chunk1", "chunk2"]}
        chunk_response.raise_for_status = MagicMock()

        exc = requests.exceptions.ConnectionError("Failed")

        mock_sess.post.side_effect = [chunk_response, exc, exc]

        with pytest.raises(StepFailed, match="All 2 chunks failed"):
            step.run([sample_doc])

    def test_partial_failure_returns_input(self, mock_session, sample_doc):
        """Test that partial failure returns input unchanged and doesn't raise StepFailed."""
        step, mock_sess = mock_session

        chunk_response = MagicMock()
        chunk_response.json.return_value = {"chunks": ["chunk1", "chunk2"]}
        chunk_response.raise_for_status = MagicMock()

        success_response = MagicMock()
        success_response.json.return_value = {"article_id": 789}
        success_response.raise_for_status = MagicMock()

        exc = requests.exceptions.ConnectionError("Failed")

        mock_sess.post.side_effect = [chunk_response, success_response, exc]

        result = step.run([sample_doc])
        assert result == [sample_doc]


class TestExtractTitle:
    """Tests for the _extract_title method."""

    def test_extract_title_from_metadata(self, mock_session):
        """Test title extraction from metadata."""
        step, _ = mock_session
        doc = MarkdownDataContract(
            md="Some content",
            url="https://example.com",
            keywords="",
            metadata={"title": "Metadata Title"},
        )
        assert step._extract_title(doc) == "Metadata Title"

    def test_extract_title_from_heading(self, mock_session):
        """Test title extraction from markdown heading."""
        step, _ = mock_session
        doc = MarkdownDataContract(
            md="# Heading Title\n\nContent here",
            url="https://example.com",
            keywords="",
        )
        assert step._extract_title(doc) == "Heading Title"

    def test_extract_title_from_url(self, mock_session):
        """Test title extraction from URL filename."""
        step, _ = mock_session
        doc = MarkdownDataContract(
            md="No heading here",
            url="https://example.com/my-cool-article.md",
            keywords="",
        )
        assert step._extract_title(doc) == "My Cool Article"

    def test_extract_title_from_url_with_underscores(self, mock_session):
        """Test title extraction from URL with underscores."""
        step, _ = mock_session
        doc = MarkdownDataContract(
            md="No heading",
            url="https://example.com/path/some_file_name.md",
            keywords="",
        )
        assert step._extract_title(doc) == "Some File Name"

    def test_extract_title_fallback_to_content(self, mock_session):
        """Test title extraction falls back to first line of content."""
        step, _ = mock_session
        doc = MarkdownDataContract(
            md="First line of content\nMore content",
            url="",
            keywords="",
        )
        assert step._extract_title(doc) == "First line of content"

    def test_extract_title_fallback_untitled(self, mock_session):
        """Test title extraction returns Untitled for empty content."""
        step, _ = mock_session
        doc = MarkdownDataContract(
            md="",
            url="",
            keywords="",
        )
        assert step._extract_title(doc) == "Untitled"


class TestFormatError:
    """Tests for the _format_error method."""

    def test_format_error_with_json_detail(self, mock_session):
        """Test error formatting with JSON detail."""
        step, _ = mock_session

        response = MagicMock()
        response.status_code = 400
        response.json.return_value = {"detail": "Bad request"}

        exc = requests.exceptions.HTTPError()
        exc.response = response

        assert step._format_error(exc) == "400: Bad request"

    def test_format_error_with_text_response(self, mock_session):
        """Test error formatting with text response when JSON fails."""
        step, _ = mock_session

        response = MagicMock()
        response.status_code = 500
        response.json.side_effect = ValueError("Not JSON")
        response.text = "Internal Server Error"

        exc = requests.exceptions.HTTPError()
        exc.response = response

        assert step._format_error(exc) == "500: Internal Server Error"

    def test_format_error_without_response(self, mock_session):
        """Test error formatting when no response attached."""
        step, _ = mock_session

        exc = requests.exceptions.ConnectionError("Connection refused")

        assert step._format_error(exc) == "Connection refused"

    def test_format_error_empty_text(self, mock_session):
        """Test error formatting with empty response text."""
        step, _ = mock_session

        response = MagicMock()
        response.status_code = 503
        response.json.side_effect = ValueError()
        response.text = ""

        exc = requests.exceptions.HTTPError("Service Unavailable")
        exc.response = response

        result = step._format_error(exc)
        assert "503" in result


class TestFinalize:
    """Tests for the finalize method."""

    def test_finalize_closes_session(self, decagon_env):
        """Test that finalize closes the session."""
        with patch("wurzel.steps.decagon.step.requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session

            step = DecagonKnowledgeBaseStep()
            step.finalize()

            mock_session.close.assert_called_once()

    def test_finalize_no_session_when_push_disabled(self, env):
        """Test that finalize is safe when no session was created."""
        env.set("PUSH_ENABLED", "false")
        with patch("wurzel.steps.decagon.step.requests.Session") as mock_session_cls:
            step = DecagonKnowledgeBaseStep()
            step.finalize()  # should not raise
            mock_session_cls.assert_not_called()
