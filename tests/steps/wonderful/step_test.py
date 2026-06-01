# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for WonderfulRAGStep using requests-mock for HTTP fixtures."""

import pytest
import requests

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed
from wurzel.steps.wonderful import WonderfulRAGStep

# ── Constants ─────────────────────────────────────────────────────────────────

KB_ID = "kb-123"
BASE_URL = "https://tenant.api.wonderful.ai"  # host only; the step hardcodes /api/v1
API = f"{BASE_URL}/api/v1"
KB_FILES = f"{API}/knowledgebases/{KB_ID}/files"
KB_SYNC = f"{API}/knowledgebases/{KB_ID}/sync"  # whole-KB sync (no per-file endpoint)
STORAGE_UPLOAD = f"{API}/storage/upload"
PRESIGNED = "https://s3.example.com/presigned"


# ── Response shape helpers ────────────────────────────────────────────────────


def kb_list_payload(*files: tuple[str, str]) -> dict:
    """Wonderful's /kb/files response shape: {data: [{name, id}, ...]}."""
    return {"data": [{"name": name, "id": fid} for name, fid in files]}


def kb_create_payload(file_id: str, presigned: str = PRESIGNED) -> dict:
    """Response from POST /kb/files: {data: {id, url}} where url is the presigned S3 URL."""
    return {"data": {"id": file_id, "url": presigned}}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def wonderful_env(env):
    env.set("BASE_URL", BASE_URL)
    env.set("API_KEY", "test-api-key")
    env.set("KNOWLEDGEBASE_ID", KB_ID)
    env.set("MAX_RETRIES", "1")  # no retries in unit tests — keeps mocks simple
    env.set("RETRY_BACKOFF", "0")  # no sleep in unit tests
    return env


@pytest.fixture
def step(wonderful_env):
    s = WonderfulRAGStep()
    yield s
    s.finalize()


@pytest.fixture
def sample_doc():
    return MarkdownDataContract(
        md="# Test Title\n\nThis is test content.",
        url="https://example.com/docs/test-doc",
        keywords="test, sample",
        metadata={"author": "tester"},
    )


@pytest.fixture
def two_docs():
    return [
        MarkdownDataContract(md="# Doc 1", url="https://example.com/doc1", keywords=""),
        MarkdownDataContract(md="# Doc 2", url="https://example.com/doc2", keywords=""),
    ]


# ── Init ──────────────────────────────────────────────────────────────────────


class TestInit:
    def test_uses_kb_id_from_settings(self, step):
        assert step._kb_id == KB_ID

    def test_build_session_sets_api_key_header(self, step):
        with step._build_session() as session:
            assert session.headers["x-api-key"] == "test-api-key"


# ── Empty input ───────────────────────────────────────────────────────────────


class TestEmptyInput:
    def test_returns_empty_list(self, step):
        assert step.run([]) == []


# ── Filename generation ───────────────────────────────────────────────────────


class TestGenerateFilename:
    @pytest.mark.parametrize(
        "url, idx, expected",
        [
            ("https://example.com/tmcz/baze/magenta-wi-fi", 0, "tmcz/baze/magenta-wi-fi.md"),
            ("https://example.com/docs/page.md", 0, "docs/page.md"),
            ("https://example.com/some-page", 0, "some-page.md"),
            ("", 5, "document_0005.md"),
        ],
        ids=["mirrors_url_path", "preserves_md_extension", "appends_md_extension", "fallback_when_no_url"],
    )
    def test_generates_expected_filename(self, step, url, idx, expected):
        doc = MarkdownDataContract(md="x", url=url, keywords="")
        assert step._generate_filename(doc, idx) == expected

    def test_stable_across_calls(self, step):
        doc = MarkdownDataContract(md="x", url="https://example.com/docs/my-article", keywords="")
        assert step._generate_filename(doc, 0) == step._generate_filename(doc, 99)

    def test_different_paths_yield_different_filenames(self, step):
        a = MarkdownDataContract(md="x", url="https://example.com/en/article", keywords="")
        b = MarkdownDataContract(md="x", url="https://example.com/cs/article", keywords="")
        assert step._generate_filename(a, 0) != step._generate_filename(b, 1)


# ── Upload ────────────────────────────────────────────────────────────────────


class TestUpload:
    def test_new_file_passthrough(self, step, sample_doc, requests_mock):
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(KB_FILES, json=kb_create_payload("file-abc"))
        requests_mock.put(PRESIGNED)
        requests_mock.post(KB_SYNC, json={})

        result = step.run([sample_doc])

        assert result == [sample_doc]
        assert [r.method for r in requests_mock.request_history] == ["GET", "POST", "PUT", "POST"]

    def test_multiple_new_files_passthrough(self, step, two_docs, requests_mock):
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(
            KB_FILES,
            [
                {"json": kb_create_payload("file-1")},
                {"json": kb_create_payload("file-2")},
            ],
        )
        requests_mock.put(PRESIGNED)
        requests_mock.post(KB_SYNC, json={})

        assert step.run(two_docs) == two_docs

        methods = [r.method for r in requests_mock.request_history]
        assert methods.count("GET") == 1
        assert methods.count("POST") == 3  # 2× create + 1× whole-KB sync
        assert methods.count("PUT") == 2

    def test_input_deduped_by_filename(self, step, requests_mock):
        """Two input docs that map to the same filename should issue only one create
        (avoids the worker-pool race Copilot flagged). Passthrough still returns both.
        """
        same_url_docs = [
            MarkdownDataContract(md="# v1", url="https://example.com/same/path", keywords=""),
            MarkdownDataContract(md="# v2", url="https://example.com/same/path", keywords=""),
        ]
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(KB_FILES, json=kb_create_payload("file-1"))
        requests_mock.put(PRESIGNED)
        requests_mock.post(KB_SYNC, json={})

        result = step.run(same_url_docs)

        # Output preserves both input docs (passthrough contract).
        assert result == same_url_docs
        # But only one create + one sync hit the KB — not two of each.
        methods = [r.method for r in requests_mock.request_history]
        assert methods.count("POST") == 2  # 1× create + 1× sync
        assert methods.count("PUT") == 1

    def test_existing_file_updates_in_place(self, step, sample_doc, requests_mock):
        existing_filename = step._generate_filename(sample_doc, 0)
        existing_id = "existing-file-id"
        requests_mock.get(KB_FILES, json=kb_list_payload((existing_filename, existing_id)))
        requests_mock.post(STORAGE_UPLOAD, json={})
        requests_mock.post(KB_SYNC, json={})

        result = step.run([sample_doc])

        assert result == [sample_doc]
        # Existing-file path: GET, POST /storage/upload, POST /sync — no new file record, no DELETE.
        history = [(r.method, r.url) for r in requests_mock.request_history]
        assert history[0] == ("GET", KB_FILES)
        assert history[1] == ("POST", STORAGE_UPLOAD)
        assert history[2][0] == "POST" and history[2][1].startswith(KB_SYNC)
        assert not any(m == "DELETE" for m, _ in history)


# ── Failure scenarios ─────────────────────────────────────────────────────────


class TestFailureScenarios:
    def test_all_fail_raises_step_failed(self, step, sample_doc, requests_mock):
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(KB_FILES, exc=requests.exceptions.ConnectionError("Failed"))

        with pytest.raises(StepFailed, match="All 1 documents failed"):
            step.run([sample_doc])

    def test_missing_presigned_url_raises_step_failed(self, step, sample_doc, requests_mock):
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(KB_FILES, json={"data": {"id": "file-abc"}})  # no "url"
        requests_mock.delete(KB_FILES, json={})  # orphan rollback (batch delete)

        with pytest.raises(StepFailed, match="All 1 documents failed"):
            step.run([sample_doc])

    def test_sync_failure_does_not_fail_step(self, step, two_docs, requests_mock):
        # Sync is fire-and-forget: a sync error must NOT fail the step (uploads persisted).
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(
            KB_FILES,
            [
                {"json": kb_create_payload("file-1")},
                {"json": kb_create_payload("file-2")},
            ],
        )
        requests_mock.put(PRESIGNED)
        requests_mock.post(KB_SYNC, exc=requests.exceptions.ConnectionError("sync failed"))

        assert step.run(two_docs) == two_docs

    def test_sync_524_does_not_fail_step(self, step, sample_doc, requests_mock):
        # A Cloudflare 524 (gateway timeout) means indexing started server-side → don't fail.
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(KB_FILES, json=kb_create_payload("file-1"))
        requests_mock.put(PRESIGNED)
        requests_mock.post(KB_SYNC, status_code=524, text="<html>gateway timeout</html>")

        assert step.run([sample_doc]) == [sample_doc]

    def test_sync_timeout_does_not_fail_step(self, step, sample_doc, requests_mock):
        # A client read timeout on the sync trigger is fire-and-forget → don't fail.
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(KB_FILES, json=kb_create_payload("file-1"))
        requests_mock.put(PRESIGNED)
        requests_mock.post(KB_SYNC, exc=requests.exceptions.ReadTimeout("slow"))

        assert step.run([sample_doc]) == [sample_doc]

    def test_partial_kb_create_failure_does_not_raise(self, step, two_docs, requests_mock):
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(
            KB_FILES,
            [
                {"exc": requests.exceptions.ConnectionError("Failed")},
                {"json": kb_create_payload("file-2")},
            ],
        )
        requests_mock.put(PRESIGNED)
        requests_mock.post(KB_SYNC, json={})

        assert step.run(two_docs) == two_docs

    def test_s3_upload_failure_does_not_abort_remaining(self, step, two_docs, requests_mock):
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(
            KB_FILES,
            [
                {"json": kb_create_payload("file-1")},
                {"json": kb_create_payload("file-2")},
            ],
        )
        # First S3 PUT fails, second succeeds.
        requests_mock.put(
            PRESIGNED,
            [
                {"exc": requests.exceptions.ConnectionError("S3 failed")},
                {"status_code": 200},
            ],
        )
        requests_mock.post(KB_SYNC, json={})
        requests_mock.delete(KB_FILES, json={})  # orphan rollback (batch delete)

        assert step.run(two_docs) == two_docs


# ── Skip (no-op) mode ─────────────────────────────────────────────────────────


class TestSkip:
    def test_constructs_without_credentials_when_skipped(self, env, requests_mock):
        env.set("SKIP", "true")
        # No BASE_URL / API_KEY / KNOWLEDGEBASE_ID set.
        step = WonderfulRAGStep()
        try:
            assert step._kb_id == ""
            assert requests_mock.request_history == []
        finally:
            step.finalize()

    def test_run_passes_through_inputs_without_api_calls(self, env, sample_doc, requests_mock):
        env.set("SKIP", "true")
        step = WonderfulRAGStep()
        try:
            assert step.run([sample_doc]) == [sample_doc]
            assert requests_mock.request_history == []
        finally:
            step.finalize()

    def test_run_passes_through_empty_input_when_skipped(self, env):
        env.set("SKIP", "true")
        step = WonderfulRAGStep()
        try:
            assert step.run([]) == []
        finally:
            step.finalize()

    def test_active_step_with_missing_credentials_raises(self, env):
        # Default SKIP is false (active); omitting credentials must fail at init.
        with pytest.raises(Exception, match="WONDERFULRAGSTEP__"):
            WonderfulRAGStep()


# ── Per-worker session ────────────────────────────────────────────────────────


class TestPerWorkerSession:
    """Each worker must use its own requests.Session — Session is not thread-safe
    for concurrent mutation.
    """

    def test_each_worker_creates_fresh_session(self, step, two_docs, requests_mock, mocker):
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(
            KB_FILES,
            [
                {"json": kb_create_payload("file-1")},
                {"json": kb_create_payload("file-2")},
            ],
        )
        requests_mock.put(PRESIGNED)
        requests_mock.post(KB_SYNC, json={})

        spy = mocker.spy(step, "_build_session")
        step.run(two_docs)

        # 1× fetch + 2× upload workers + 1× sync loop.
        assert spy.call_count == 4


# ── Neverejny filter ──────────────────────────────────────────────────────────


class TestNeverejnyFilter:
    def test_neverejny_doc_is_not_uploaded(self, step, requests_mock):
        doc = MarkdownDataContract(md="# Secret", url="https://example.com/docs/nabidka_neverejny.md", keywords="")
        result = step.run([doc])
        assert result == [doc]  # passthrough unchanged
        assert requests_mock.request_history == []

    def test_neverejna_doc_is_not_uploaded(self, step, requests_mock):
        doc = MarkdownDataContract(md="# Secret", url="https://example.com/docs/nabidka_neverejna.md", keywords="")
        result = step.run([doc])
        assert result == [doc]  # passthrough unchanged
        assert requests_mock.request_history == []

    def test_neverejny_is_case_insensitive(self, step, requests_mock):
        doc = MarkdownDataContract(md="# Secret", url="https://example.com/docs/nabidka_NEVEREJNY.md", keywords="")
        result = step.run([doc])
        assert result == [doc]  # passthrough unchanged
        assert requests_mock.request_history == []

    def test_only_clean_doc_is_uploaded_full_input_returned(self, step, requests_mock):
        clean = MarkdownDataContract(md="# Public", url="https://example.com/docs/nabidka_verejny.md", keywords="")
        secret = MarkdownDataContract(md="# Secret", url="https://example.com/docs/nabidka_neverejny.md", keywords="")
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(KB_FILES, json=kb_create_payload("file-1"))
        requests_mock.put(PRESIGNED)
        requests_mock.post(KB_SYNC, json={})

        result = step.run([clean, secret])

        assert result == [clean, secret]  # full input returned as passthrough
        assert requests_mock.request_history[0].method == "GET"
        assert sum(1 for r in requests_mock.request_history if r.method == "POST") == 2  # create + sync

    def test_all_neverejny_skips_upload_passes_through(self, step, requests_mock):
        docs = [
            MarkdownDataContract(md="# A", url="https://example.com/docs/nabidka_neverejny.md", keywords=""),
            MarkdownDataContract(md="# B", url="https://example.com/docs/prehled_neverejny.md", keywords=""),
        ]
        result = step.run(docs)
        assert result == docs  # passthrough unchanged
        assert requests_mock.request_history == []


# ── Retry / back-off ──────────────────────────────────────────────────────────


class TestRetry:
    """Back-off retry is applied per HTTP call. Tests use MAX_RETRIES=3, RETRY_BACKOFF=0
    (no actual sleep) so we can verify retry counts without slowing down the suite.
    """

    @pytest.fixture
    def retry_env(self, env):
        env.set("BASE_URL", BASE_URL)
        env.set("API_KEY", "test-api-key")
        env.set("KNOWLEDGEBASE_ID", KB_ID)
        env.set("MAX_RETRIES", "3")
        env.set("RETRY_BACKOFF", "0")
        return env

    @pytest.fixture
    def retry_step(self, retry_env, mocker):
        mocker.patch("wurzel.steps.wonderful.step.time.sleep")
        s = WonderfulRAGStep()
        yield s
        s.finalize()

    def test_upload_retries_on_transient_error(self, retry_step, sample_doc, requests_mock):
        """A transient upload failure is retried; success on the third attempt."""
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(
            KB_FILES,
            [
                {"exc": requests.exceptions.ConnectionError("transient")},
                {"exc": requests.exceptions.ConnectionError("transient")},
                {"json": kb_create_payload("file-ok")},
            ],
        )
        requests_mock.put(PRESIGNED)
        requests_mock.post(KB_SYNC, json={})

        result = retry_step.run([sample_doc])

        assert result == [sample_doc]
        assert sum(1 for r in requests_mock.request_history if r.method == "POST" and r.url == KB_FILES) == 3

    def test_sync_triggered_once_not_retried(self, retry_step, sample_doc, requests_mock):
        """Sync is fire-and-forget: triggered exactly once, never retried even on failure."""
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(KB_FILES, json=kb_create_payload("file-ok"))
        requests_mock.put(PRESIGNED)
        requests_mock.post(KB_SYNC, exc=requests.exceptions.ConnectionError("transient"))

        result = retry_step.run([sample_doc])

        assert result == [sample_doc]  # sync failure doesn't fail the step
        assert sum(1 for r in requests_mock.request_history if r.url.startswith(KB_SYNC)) == 1

    def test_exhausted_retries_raises_step_failed(self, retry_step, sample_doc, requests_mock):
        """When all retries are exhausted and every document fails, StepFailed is raised."""
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(KB_FILES, exc=requests.exceptions.ConnectionError("permanent"))

        with pytest.raises(StepFailed):
            retry_step.run([sample_doc])

        assert sum(1 for r in requests_mock.request_history if r.method == "POST") == 3  # 3 attempts

    def test_create_not_retried_on_read_timeout(self, retry_step, sample_doc, requests_mock):
        """Create is non-idempotent: a read timeout must not be retried (avoids duplicates)."""
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(KB_FILES, exc=requests.exceptions.ReadTimeout("timeout"))

        with pytest.raises(StepFailed):
            retry_step.run([sample_doc])

        assert sum(1 for r in requests_mock.request_history if r.method == "POST" and r.url == KB_FILES) == 1

    def test_client_error_not_retried(self, retry_step, sample_doc, requests_mock):
        """A 4xx is a permanent client error — no retry."""
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(KB_FILES, status_code=403)

        with pytest.raises(StepFailed):
            retry_step.run([sample_doc])

        assert sum(1 for r in requests_mock.request_history if r.method == "POST" and r.url == KB_FILES) == 1

    def test_server_error_is_retried(self, retry_step, sample_doc, requests_mock):
        """A 5xx is transient — retried, then succeeds."""
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(
            KB_FILES,
            [
                {"status_code": 503},
                {"json": kb_create_payload("file-ok")},
            ],
        )
        requests_mock.put(PRESIGNED)
        requests_mock.post(KB_SYNC, json={})

        result = retry_step.run([sample_doc])

        assert result == [sample_doc]
        assert sum(1 for r in requests_mock.request_history if r.method == "POST" and r.url == KB_FILES) == 2

    def test_orphan_record_rolled_back_on_upload_failure(self, retry_step, sample_doc, requests_mock):
        """If the S3 upload fails after the record is created, the record is deleted."""
        file_id = "file-orphan"
        requests_mock.get(KB_FILES, json=kb_list_payload())
        requests_mock.post(KB_FILES, json=kb_create_payload(file_id))
        requests_mock.put(PRESIGNED, exc=requests.exceptions.ConnectionError("s3 down"))
        delete_mock = requests_mock.delete(KB_FILES, json={})

        with pytest.raises(StepFailed):
            retry_step.run([sample_doc])

        assert delete_mock.called  # orphan record rolled back
        assert delete_mock.last_request.json() == {"file_ids": [file_id]}  # by id, in the body
