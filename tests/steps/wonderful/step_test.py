# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for WonderfulRAGStep with mocked API calls."""

import threading
from unittest.mock import MagicMock, patch

import pytest
import requests

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed
from wurzel.steps.wonderful import WonderfulRAGStep

KB_ID = "kb-123"


@pytest.fixture
def wonderful_env(env):
    env.set("BASE_URL", "https://tenant.api.wonderful.ai")
    env.set("API_KEY", "test-api-key")
    env.set("KNOWLEDGEBASE_ID", KB_ID)
    return env


@pytest.fixture
def sample_doc():
    return MarkdownDataContract(
        md="# Test Title\n\nThis is test content.",
        url="https://example.com/docs/test-doc",
        keywords="test, sample",
        metadata={"author": "tester"},
    )


# ── Response helpers ──────────────────────────────────────────────────────────

def make_kb_list_response(files: list[dict] | None = None) -> MagicMock:
    r = MagicMock()
    r.ok = True
    r.json.return_value = {"data": files or []}
    r.raise_for_status = MagicMock()
    return r


def make_kb_upload_response(file_id: str, presigned_url: str = "https://s3.example.com/presigned") -> MagicMock:
    r = MagicMock()
    r.ok = True
    r.json.return_value = {"data": {"id": file_id, "url": presigned_url}}
    r.raise_for_status = MagicMock()
    return r


def make_ok_response() -> MagicMock:
    r = MagicMock()
    r.ok = True
    r.json.return_value = {}
    r.raise_for_status = MagicMock()
    return r


def methods_called(mock_sess) -> list[str]:
    return [c.args[0] for c in mock_sess.request.call_args_list]


@pytest.fixture
def mock_session(wonderful_env):
    with patch("wurzel.steps.wonderful.step.requests.Session") as mock_session_cls:
        mock_sess = MagicMock()
        mock_session_cls.return_value = mock_sess
        step = WonderfulRAGStep()
        mock_sess.request.reset_mock()
        yield step, mock_sess
        step.finalize()


# ── Init ──────────────────────────────────────────────────────────────────────

class TestInit:

    def test_uses_knowledgebase_id_from_settings(self, wonderful_env):
        with patch("wurzel.steps.wonderful.step.requests.Session") as mock_session_cls:
            mock_sess = MagicMock()
            mock_session_cls.return_value = mock_sess
            step = WonderfulRAGStep()
            assert step._kb_id == KB_ID
            mock_sess.request.assert_not_called()
            step.finalize()

    def test_sets_api_key_header(self, wonderful_env):
        with patch("wurzel.steps.wonderful.step.requests.Session") as mock_session_cls:
            mock_sess = MagicMock()
            mock_session_cls.return_value = mock_sess
            step = WonderfulRAGStep()
            call_args = mock_sess.headers.update.call_args[0][0]
            assert call_args["x-api-key"] == "test-api-key"
            step.finalize()


# ── Empty input ───────────────────────────────────────────────────────────────

class TestEmptyInput:

    def test_returns_empty_list(self, mock_session):
        step, _ = mock_session
        assert step.run([]) == []


# ── Filename generation ───────────────────────────────────────────────────────

class TestGenerateFilename:

    def test_mirrors_url_path(self, mock_session):
        step, _ = mock_session
        doc = MarkdownDataContract(md="x", url="https://example.com/tmcz/baze/magenta-wi-fi", keywords="")
        assert step._generate_filename(doc, 0) == "tmcz/baze/magenta-wi-fi.md"

    def test_stable_across_calls(self, mock_session):
        step, _ = mock_session
        doc = MarkdownDataContract(md="x", url="https://example.com/docs/my-article", keywords="")
        assert step._generate_filename(doc, 0) == step._generate_filename(doc, 99)

    def test_different_paths_different_filenames(self, mock_session):
        step, _ = mock_session
        doc_a = MarkdownDataContract(md="x", url="https://example.com/en/article", keywords="")
        doc_b = MarkdownDataContract(md="x", url="https://example.com/cs/article", keywords="")
        assert step._generate_filename(doc_a, 0) != step._generate_filename(doc_b, 1)

    def test_ends_with_md(self, mock_session):
        step, _ = mock_session
        doc = MarkdownDataContract(md="x", url="https://example.com/some-page", keywords="")
        assert step._generate_filename(doc, 0).endswith(".md")

    def test_preserves_existing_md_extension(self, mock_session):
        step, _ = mock_session
        doc = MarkdownDataContract(md="x", url="https://example.com/docs/page.md", keywords="")
        assert step._generate_filename(doc, 0) == "docs/page.md"

    def test_fallback_when_no_url(self, mock_session):
        step, _ = mock_session
        doc = MarkdownDataContract(md="x", url="", keywords="")
        assert step._generate_filename(doc, 5) == "document_0005.md"


# ── Upload ────────────────────────────────────────────────────────────────────

class TestUpload:

    def test_new_file_passthrough(self, mock_session, sample_doc):
        step, mock_sess = mock_session
        mock_sess.request.side_effect = [
            make_kb_list_response(),              # GET  existing files
            make_kb_upload_response("file-abc"),  # POST /kb/files
            make_ok_response(),                   # POST /kb/files/sync
        ]

        with patch("wurzel.steps.wonderful.step.requests.put", return_value=make_ok_response()):
            result = step.run([sample_doc])

        assert methods_called(mock_sess) == ["GET", "POST", "POST"]
        assert result == [sample_doc]

    def test_multiple_new_files_passthrough(self, mock_session):
        step, mock_sess = mock_session
        docs = [
            MarkdownDataContract(md="# Doc 1", url="https://example.com/doc1", keywords=""),
            MarkdownDataContract(md="# Doc 2", url="https://example.com/doc2", keywords=""),
        ]
        # Uploads + syncs are concurrent — use a function side_effect.
        lock = threading.Lock()
        file_ids = iter(["file-1", "file-2"])

        def side_effect(method, url, **kwargs):
            if method == "GET":
                return make_kb_list_response()
            if "/sync" in url:
                return make_ok_response()
            with lock:
                return make_kb_upload_response(next(file_ids))

        mock_sess.request.side_effect = side_effect
        with patch("wurzel.steps.wonderful.step.requests.put", return_value=make_ok_response()):
            result = step.run(docs)

        assert mock_sess.request.call_count == 5  # GET + 2x POST /kb/files + 2x POST /sync
        assert result == docs

    def test_existing_file_updates_in_place(self, mock_session, sample_doc):
        """Re-run updates S3 content via /storage/upload — no new record, no delete."""
        step, mock_sess = mock_session
        existing_filename = step._generate_filename(sample_doc, 0)
        existing_id = "existing-file-id"
        mock_sess.request.side_effect = [
            make_kb_list_response([{"name": existing_filename, "id": existing_id}]),
            make_ok_response(),  # POST /storage/upload
            make_ok_response(),  # POST /kb/files/sync
        ]

        result = step.run([sample_doc])

        assert methods_called(mock_sess) == ["GET", "POST", "POST"]
        assert "DELETE" not in methods_called(mock_sess)
        # Second POST should hit /storage/upload, not the KB files endpoint.
        assert "/storage/upload" in mock_sess.request.call_args_list[1].args[1]
        assert result == [sample_doc]


# ── Failure scenarios ─────────────────────────────────────────────────────────

class TestFailureScenarios:

    def test_all_fail_raises_step_failed(self, mock_session, sample_doc):
        step, mock_sess = mock_session
        mock_sess.request.side_effect = [
            make_kb_list_response(),
            requests.exceptions.ConnectionError("Failed"),
        ]

        with pytest.raises(StepFailed, match="All 1 documents failed"):
            step.run([sample_doc])

    def test_missing_presigned_url_raises_step_failed(self, mock_session, sample_doc):
        step, mock_sess = mock_session
        missing_url_response = MagicMock()
        missing_url_response.ok = True
        missing_url_response.json.return_value = {"data": {"id": "file-abc"}}  # no "url"
        missing_url_response.raise_for_status = MagicMock()
        mock_sess.request.side_effect = [
            make_kb_list_response(),
            missing_url_response,
        ]

        with pytest.raises(StepFailed, match="All 1 documents failed"):
            step.run([sample_doc])

    def test_sync_failure_does_not_raise_when_others_succeed(self, mock_session):
        """Sync failure for one doc is logged but does not affect output (passthrough)."""
        step, mock_sess = mock_session
        docs = [
            MarkdownDataContract(md="# Doc 1", url="https://example.com/doc1", keywords=""),
            MarkdownDataContract(md="# Doc 2", url="https://example.com/doc2", keywords=""),
        ]
        lock = threading.Lock()
        file_ids = iter(["file-1", "file-2"])
        sync_count = {"n": 0}

        def side_effect(method, url, **kwargs):
            if method == "GET":
                return make_kb_list_response()
            if "/sync" in url:
                with lock:
                    n = sync_count["n"]
                    sync_count["n"] += 1
                if n == 0:
                    raise requests.exceptions.ConnectionError("sync failed")
                return make_ok_response()
            with lock:
                return make_kb_upload_response(next(file_ids))

        mock_sess.request.side_effect = side_effect
        with patch("wurzel.steps.wonderful.step.requests.put", return_value=make_ok_response()):
            result = step.run(docs)

        assert result == docs

    def test_partial_upload_failure_does_not_raise(self, mock_session):
        step, mock_sess = mock_session
        docs = [
            MarkdownDataContract(md="# Doc 1", url="https://example.com/doc1", keywords=""),
            MarkdownDataContract(md="# Doc 2", url="https://example.com/doc2", keywords=""),
        ]
        lock = threading.Lock()
        upload_count = {"n": 0}

        def side_effect(method, url, **kwargs):
            if method == "GET":
                return make_kb_list_response()
            if "/sync" in url:
                return make_ok_response()
            with lock:
                n = upload_count["n"]
                upload_count["n"] += 1
            if n == 0:
                raise requests.exceptions.ConnectionError("Failed")
            return make_kb_upload_response(f"file-{n + 1}")

        mock_sess.request.side_effect = side_effect
        with patch("wurzel.steps.wonderful.step.requests.put", return_value=make_ok_response()):
            result = step.run(docs)

        assert result == docs

    def test_upload_failure_does_not_abort_remaining(self, mock_session):
        step, mock_sess = mock_session
        docs = [
            MarkdownDataContract(md="# Doc 1", url="https://example.com/doc1", keywords=""),
            MarkdownDataContract(md="# Doc 2", url="https://example.com/doc2", keywords=""),
        ]
        lock = threading.Lock()
        upload_count = {"n": 0}

        def side_effect(method, url, **kwargs):
            if method == "GET":
                return make_kb_list_response()
            if "/sync" in url:
                return make_ok_response()
            with lock:
                n = upload_count["n"]
                upload_count["n"] += 1
            return make_kb_upload_response(f"file-{n + 1}")

        put_lock = threading.Lock()
        put_count = {"n": 0}

        def put_side_effect(*args, **kwargs):
            with put_lock:
                n = put_count["n"]
                put_count["n"] += 1
            if n == 0:
                raise requests.exceptions.ConnectionError("S3 failed")
            return make_ok_response()

        mock_sess.request.side_effect = side_effect
        with patch("wurzel.steps.wonderful.step.requests.put", side_effect=put_side_effect):
            result = step.run(docs)

        assert result == docs


# ── Disabled (no-op) mode ─────────────────────────────────────────────────────

class TestDisabled:

    def test_constructs_without_credentials_when_disabled(self, env):
        env.set("ENABLED", "false")
        # No BASE_URL / API_KEY / KNOWLEDGEBASE_ID set.
        with patch("wurzel.steps.wonderful.step.requests.Session") as mock_session_cls:
            step = WonderfulRAGStep()
            mock_session_cls.assert_not_called()
            step.finalize()  # must not raise even though no session was created

    def test_run_passes_through_inputs_without_api_calls(self, env, sample_doc):
        env.set("ENABLED", "false")
        with patch("wurzel.steps.wonderful.step.requests.Session") as mock_session_cls:
            mock_sess = MagicMock()
            mock_session_cls.return_value = mock_sess
            step = WonderfulRAGStep()
            with patch("wurzel.steps.wonderful.step.requests.put") as mock_put:
                result = step.run([sample_doc])
            mock_sess.request.assert_not_called()
            mock_put.assert_not_called()
            assert result == [sample_doc]
            step.finalize()

    def test_run_passes_through_empty_input_when_disabled(self, env):
        env.set("ENABLED", "false")
        step = WonderfulRAGStep()
        assert step.run([]) == []
        step.finalize()

    def test_enabled_true_with_missing_credentials_raises(self, env):
        # Default ENABLED is true; omitting credentials must fail at init.
        with pytest.raises(Exception, match="WONDERFULRAGSTEP__"):
            WonderfulRAGStep()


# ── Finalize ──────────────────────────────────────────────────────────────────

class TestFinalize:

    def test_closes_session(self, wonderful_env):
        with patch("wurzel.steps.wonderful.step.requests.Session") as mock_session_cls:
            mock_sess = MagicMock()
            mock_session_cls.return_value = mock_sess
            step = WonderfulRAGStep()
            step.finalize()
            mock_sess.close.assert_called_once()
