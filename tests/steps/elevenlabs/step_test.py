# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ElevenLabsKnowledgeBaseStep using requests-mock for HTTP fixtures."""

import re
from unittest.mock import MagicMock, patch

import pytest
import requests

from wurzel.core import step_history
from wurzel.core.history import History
from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed
from wurzel.steps.elevenlabs import ElevenLabsKnowledgeBaseStep

# ── Constants ─────────────────────────────────────────────────────────────────

BASE_URL = "https://api.elevenlabs.io"
KB = f"{BASE_URL}/v1/convai/knowledge-base"
KB_TEXT = f"{KB}/text"
KB_FOLDER = f"{KB}/folder"


# ── Response shape helpers ────────────────────────────────────────────────────


def kb_list_payload(*docs: tuple[str, str], has_more: bool = False, next_cursor: str | None = None, doc_type: str = "text") -> dict:
    """ElevenLabs' GET /knowledge-base response shape. Documents default to type=text."""
    return {
        "documents": [{"id": doc_id, "name": name, "type": doc_type} for name, doc_id in docs],
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


def kb_create_payload(doc_id: str, name: str = "doc") -> dict:
    """Response from POST /knowledge-base/text."""
    return {"id": doc_id, "name": name, "folder_path": []}


def register_kb_listing(requests_mock, *, folders: tuple[tuple[str, str], ...] = (), texts: tuple[tuple[str, str], ...] = ()) -> None:
    """Mock GET /knowledge-base to return `folders` or `texts` depending on the `types` query param.

    Needed because folder resolution (``_find_folder``) and text-document listing
    (``_list_existing``) share the same GET endpoint, distinguished only by `types`.
    """

    def _respond(request, _context):
        if request.qs.get("types") == ["folder"]:
            return kb_list_payload(*folders, doc_type="folder")
        return kb_list_payload(*texts, doc_type="text")

    requests_mock.get(KB, json=_respond)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def elevenlabs_env(env):
    env.set("API_KEY", "test-api-key")
    env.set("MAX_RETRIES", "1")  # no retries by default in unit tests — keeps mocks simple
    env.set("RETRY_BACKOFF", "0")  # no sleep in unit tests
    return env


@pytest.fixture
def step(elevenlabs_env):
    s = ElevenLabsKnowledgeBaseStep()
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


@pytest.fixture
def history_scope():
    """Sets step_history for the duration of a test, resetting it afterward.

    step_history is a module-level ContextVar - left unset it stays None (the
    default, matching a step run outside the wurzel Executor). Tests using this
    fixture must reset it themselves rather than relying on test isolation,
    since pytest runs tests sequentially in the same context.
    """

    def _set(*chain: str) -> None:
        step_history.set(History(*chain))

    yield _set
    step_history.set(None)


# ── Init ──────────────────────────────────────────────────────────────────────


class TestInit:
    def test_init_sets_api_key_header(self, elevenlabs_env):
        with patch("wurzel.steps.elevenlabs.step.requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session
            step = ElevenLabsKnowledgeBaseStep()

            mock_session.headers.update.assert_called_once_with({"xi-api-key": "test-api-key"})
            step.finalize()

    def test_init_skips_session_when_push_disabled(self, env):
        env.set("PUSH_ENABLED", "false")
        with patch("wurzel.steps.elevenlabs.step.requests.Session") as mock_session_cls:
            step = ElevenLabsKnowledgeBaseStep()
            mock_session_cls.assert_not_called()
            step.finalize()

    def test_init_raises_without_api_key_when_push_enabled(self, env):
        with pytest.raises(ValueError, match="API_KEY is required"):
            ElevenLabsKnowledgeBaseStep()

    def test_init_raises_when_pruning_without_name_prefix(self, elevenlabs_env):
        elevenlabs_env.set("PRUNE_STALE", "true")
        with pytest.raises(ValueError, match="NAME_PREFIX is required"):
            ElevenLabsKnowledgeBaseStep()


# ── Empty input ───────────────────────────────────────────────────────────────


class TestEmptyInput:
    def test_returns_empty_list(self, step):
        assert step.run([]) == []


# ── Name generation ───────────────────────────────────────────────────────────


class TestGenerateName:
    @pytest.mark.parametrize(
        "url, idx, expected",
        [
            ("https://example.com/tmcz/baze/magenta-wi-fi", 0, "tmcz/baze/magenta-wi-fi"),
            ("https://example.com/", 0, "document_0000"),
            ("", 3, "document_0003"),
        ],
    )
    def test_generates_expected_name(self, step, url, idx, expected):
        doc = MarkdownDataContract(md="content", url=url, keywords="")
        assert step._generate_name(doc, idx) == expected

    def test_applies_name_prefix(self, elevenlabs_env):
        elevenlabs_env.set("NAME_PREFIX", "wurzel/")
        step = ElevenLabsKnowledgeBaseStep()
        doc = MarkdownDataContract(md="content", url="https://example.com/a", keywords="")

        assert step._generate_name(doc, 0) == "wurzel/a"
        step.finalize()

    def test_stable_across_calls(self, step, sample_doc):
        assert step._generate_name(sample_doc, 0) == step._generate_name(sample_doc, 0)

    def test_includes_history_tag_when_set(self, step, history_scope):
        history_scope("SourceA", "ElevenLabsKnowledgeBase")
        doc = MarkdownDataContract(md="content", url="https://example.com/a", keywords="")

        assert step._generate_name(doc, 0) == "SourceA-ElevenLabsKnowledgeBase/a"

    def test_no_history_tag_when_unset(self, step):
        doc = MarkdownDataContract(md="content", url="https://example.com/a", keywords="")

        assert step._generate_name(doc, 0) == "a"

    def test_history_tag_combines_with_name_prefix(self, elevenlabs_env, history_scope):
        elevenlabs_env.set("NAME_PREFIX", "wurzel/")
        history_scope("SourceA")
        step = ElevenLabsKnowledgeBaseStep()
        doc = MarkdownDataContract(md="content", url="https://example.com/a", keywords="")

        assert step._generate_name(doc, 0) == "wurzel/SourceA/a"
        step.finalize()


# ── History-scoped isolation ────────────────────────────────────────────────────


class TestHistoryScopedIsolation:
    """Covers the reviewer concern: wurzel calls run() once per upstream file, so a
    step with multiple dependsOn (or one upstream step sharding its output across
    files) gets invoked more than once within a single run. Without scoping,
    prune from one invocation could delete another invocation's just-created
    documents - reproduced for real against the live API before this fix.
    """

    def test_list_existing_scoped_to_own_history(self, elevenlabs_env, requests_mock, history_scope):
        elevenlabs_env.set("NAME_PREFIX", "wurzel/")
        history_scope("SourceB")
        step = ElevenLabsKnowledgeBaseStep()
        requests_mock.get(
            KB,
            json=kb_list_payload(
                ("wurzel/SourceA/shared-name", "doc-a"),
                ("wurzel/SourceB/shared-name", "doc-b"),
            ),
        )

        existing = step._list_existing(None)

        assert existing == {"wurzel/SourceB/shared-name": "doc-b"}
        step.finalize()

    def test_prune_does_not_touch_a_different_invocations_document(self, elevenlabs_env, requests_mock, history_scope):
        elevenlabs_env.set("NAME_PREFIX", "wurzel/")
        elevenlabs_env.set("PRUNE_STALE", "true")

        # Invocation 1: source A creates its document.
        history_scope("SourceA")
        step_a = ElevenLabsKnowledgeBaseStep()
        doc_a = MarkdownDataContract(md="# A", url="https://example.com/shared-name", keywords="")
        requests_mock.get(KB, json=kb_list_payload())
        requests_mock.post(KB_TEXT, json=kb_create_payload("doc-a", "wurzel/SourceA/shared-name"))
        step_a.run([doc_a])
        step_a.finalize()

        # Invocation 2: source B, same run, different history/lineage. The listing
        # reflects source A's document now existing in the workspace.
        history_scope("SourceB")
        step_b = ElevenLabsKnowledgeBaseStep()
        doc_b = MarkdownDataContract(md="# B", url="https://example.com/shared-name", keywords="")
        requests_mock.get(KB, json=kb_list_payload(("wurzel/SourceA/shared-name", "doc-a")))
        requests_mock.post(KB_TEXT, json=kb_create_payload("doc-b", "wurzel/SourceB/shared-name"))
        delete_mock = requests_mock.delete(f"{KB}/doc-a", text="")

        step_b.run([doc_b])
        step_b.finalize()

        assert not delete_mock.called  # source A's document must survive source B's prune


# ── Create / update ────────────────────────────────────────────────────────────


class TestCreateAndUpdate:
    def test_new_document_created_and_passthrough(self, step, sample_doc, requests_mock):
        requests_mock.get(KB, json=kb_list_payload())
        requests_mock.post(KB_TEXT, json=kb_create_payload("doc-1", "docs/test-doc"))

        result = step.run([sample_doc])

        assert result == [sample_doc]
        post_request = next(r for r in requests_mock.request_history if r.method == "POST")
        assert post_request.json()["text"] == sample_doc.md
        assert post_request.json()["name"] == "docs/test-doc"

    def test_existing_document_updated_in_place(self, step, sample_doc, requests_mock):
        name = "docs/test-doc"
        requests_mock.get(KB, json=kb_list_payload((name, "doc-existing")))
        requests_mock.patch(f"{KB}/doc-existing", json={})

        result = step.run([sample_doc])

        assert result == [sample_doc]
        methods = [r.method for r in requests_mock.request_history]
        assert "PATCH" in methods
        assert "POST" not in methods
        patch_request = next(r for r in requests_mock.request_history if r.method == "PATCH")
        assert patch_request.json() == {"content": sample_doc.md}

    def test_multiple_documents_processed(self, step, two_docs, requests_mock):
        requests_mock.get(KB, json=kb_list_payload())
        requests_mock.post(
            KB_TEXT,
            [
                {"json": kb_create_payload("doc-1", "doc1")},
                {"json": kb_create_payload("doc-2", "doc2")},
            ],
        )

        result = step.run(two_docs)

        assert result == two_docs
        assert len([r for r in requests_mock.request_history if r.method == "POST"]) == 2

    def test_parent_folder_id_included_when_set(self, elevenlabs_env, sample_doc, requests_mock):
        elevenlabs_env.set("PARENT_FOLDER_ID", "folder-1")
        step = ElevenLabsKnowledgeBaseStep()
        requests_mock.get(KB, json=kb_list_payload())
        requests_mock.post(KB_TEXT, json=kb_create_payload("doc-1"))

        step.run([sample_doc])

        post_request = next(r for r in requests_mock.request_history if r.method == "POST")
        assert post_request.json()["parent_folder_id"] == "folder-1"
        step.finalize()


# ── Delete ─────────────────────────────────────────────────────────────────────


class TestDelete:
    def test_handles_empty_response_body(self, step, requests_mock):
        """The real API returns an empty (non-JSON) body for DELETE; must not raise."""
        requests_mock.delete(f"{KB}/doc-1", text="")

        step._delete("doc-1")  # should not raise JSONDecodeError

        assert requests_mock.last_request.qs.get("force") == ["false"]


# ── Listing / pagination ───────────────────────────────────────────────────────


class TestListPagination:
    def test_follows_cursor_across_pages(self, step, sample_doc, requests_mock):
        name = "docs/test-doc"
        requests_mock.get(
            KB,
            [
                {"json": kb_list_payload(("other", "other-1"), has_more=True, next_cursor="page-2")},
                {"json": kb_list_payload((name, "doc-existing"))},
            ],
        )
        requests_mock.patch(f"{KB}/doc-existing", json={})

        result = step.run([sample_doc])

        assert result == [sample_doc]
        get_requests = [r for r in requests_mock.request_history if r.method == "GET"]
        assert len(get_requests) == 2
        assert get_requests[1].qs.get("cursor") == ["page-2"]

    def test_does_not_use_search_param(self, elevenlabs_env, sample_doc, requests_mock):
        """NAME_PREFIX must be applied client-side, not via the API's `search` param.

        `search` is backed by search infrastructure that isn't guaranteed to
        return every match (observed missing a document that plainly existed,
        which caused a duplicate to be created instead of an update) - so it
        must never be relied on for correctness here.
        """
        elevenlabs_env.set("NAME_PREFIX", "wurzel/")
        step = ElevenLabsKnowledgeBaseStep()
        requests_mock.get(KB, json=kb_list_payload())
        requests_mock.post(KB_TEXT, json=kb_create_payload("doc-1"))

        step.run([sample_doc])

        get_request = next(r for r in requests_mock.request_history if r.method == "GET")
        assert "search" not in get_request.qs
        assert get_request.qs.get("types") == ["text"]
        step.finalize()

    def test_parent_folder_id_included_in_list_params(self, elevenlabs_env, sample_doc, requests_mock):
        """`_create` files new documents under PARENT_FOLDER_ID, so listing must be
        scoped to the same folder - otherwise every document created there looks
        "new" again on the next run and gets duplicated instead of updated in
        place (reproduced against a real KB: https://github.com/telekom/wurzel/pull/247).
        """
        elevenlabs_env.set("PARENT_FOLDER_ID", "folder-1")
        step = ElevenLabsKnowledgeBaseStep()
        requests_mock.get(KB, json=kb_list_payload())
        requests_mock.post(KB_TEXT, json=kb_create_payload("doc-1"))

        step.run([sample_doc])

        get_request = next(r for r in requests_mock.request_history if r.method == "GET")
        assert get_request.qs.get("parent_folder_id") == ["folder-1"]
        step.finalize()

    def test_name_prefix_filters_client_side(self, elevenlabs_env, sample_doc, requests_mock):
        """Out-of-prefix documents must never enter `existing` at all.

        Asserted with PRUNE_STALE on: if the client-side filter were missing (i.e.
        this code trusted the server to have already scoped the response by
        NAME_PREFIX via `search`), an out-of-prefix document present in a raw
        listing response - as this mock simulates - would be treated as stale
        and deleted, silently touching documents outside this step's namespace.
        """
        elevenlabs_env.set("NAME_PREFIX", "wurzel/")
        elevenlabs_env.set("PRUNE_STALE", "true")
        step = ElevenLabsKnowledgeBaseStep()
        name = "wurzel/docs/test-doc"
        requests_mock.get(KB, json=kb_list_payload((name, "doc-existing"), ("unrelated/doc", "doc-other")))
        requests_mock.patch(f"{KB}/doc-existing", json={})
        delete_mock = requests_mock.delete(f"{KB}/doc-other", text="")

        step.run([sample_doc])

        methods = [r.method for r in requests_mock.request_history]
        assert "PATCH" in methods
        assert "POST" not in methods  # matched despite no server-side search filter
        assert not delete_mock.called  # out-of-prefix doc is never a prune candidate
        step.finalize()

    def test_non_text_document_is_ignored_even_if_server_types_filter_leaks_it(self, step, sample_doc, requests_mock):
        """Defense in depth: don't trust the server-side `types=text` filter alone."""
        name = "docs/test-doc"
        requests_mock.get(
            KB,
            json={
                "documents": [
                    {"id": "doc-existing", "name": name, "type": "text"},
                    {"id": "doc-folder", "name": name, "type": "folder"},
                ],
                "has_more": False,
                "next_cursor": None,
            },
        )
        requests_mock.patch(f"{KB}/doc-existing", json={})

        result = step.run([sample_doc])

        assert result == [sample_doc]
        methods = [r.method for r in requests_mock.request_history]
        assert "PATCH" in methods
        assert "DELETE" not in methods  # the non-text "duplicate" is never touched

    def test_duplicate_name_self_heals_by_deleting_extra_copy(self, step, sample_doc, requests_mock):
        name = "docs/test-doc"
        requests_mock.get(KB, json=kb_list_payload((name, "doc-first"), (name, "doc-duplicate")))
        requests_mock.patch(f"{KB}/doc-first", json={})
        delete_mock = requests_mock.delete(f"{KB}/doc-duplicate", text="")

        result = step.run([sample_doc])

        assert result == [sample_doc]
        assert delete_mock.called_once
        methods = [r.method for r in requests_mock.request_history]
        assert "PATCH" in methods  # kept the first-seen id and updated it
        assert "POST" not in methods  # did not create a third copy

    def test_list_failure_raises_instead_of_risking_a_duplicate(self, step, sample_doc, requests_mock):
        """A failed listing must not fall back to "assume nothing exists" and create.

        That's exactly the sequence that produced duplicate documents in practice:
        a transient listing failure made an already-existing document look new.
        """
        requests_mock.get(KB, exc=requests.exceptions.ConnectionError("down"))
        create_mock = requests_mock.post(KB_TEXT, json=kb_create_payload("doc-1"))

        with pytest.raises(StepFailed, match="Could not list existing knowledge base documents"):
            step.run([sample_doc])

        assert not create_mock.called


# ── Retry ──────────────────────────────────────────────────────────────────────


class TestRetry:
    def test_transient_500_on_list_is_retried_and_succeeds(self, elevenlabs_env, sample_doc, requests_mock):
        elevenlabs_env.set("MAX_RETRIES", "2")
        step = ElevenLabsKnowledgeBaseStep()
        name = "docs/test-doc"
        requests_mock.get(
            KB,
            [
                {"status_code": 500, "text": "boom"},
                {"json": kb_list_payload((name, "doc-existing"))},
            ],
        )
        requests_mock.patch(f"{KB}/doc-existing", json={})

        result = step.run([sample_doc])

        assert result == [sample_doc]
        get_requests = [r for r in requests_mock.request_history if r.method == "GET"]
        assert len(get_requests) == 2
        step.finalize()

    def test_list_failure_raises_after_retries_exhausted(self, elevenlabs_env, sample_doc, requests_mock):
        elevenlabs_env.set("MAX_RETRIES", "2")
        step = ElevenLabsKnowledgeBaseStep()
        requests_mock.get(KB, status_code=500, text="boom")

        with pytest.raises(StepFailed, match="Could not list existing knowledge base documents"):
            step.run([sample_doc])

        get_requests = [r for r in requests_mock.request_history if r.method == "GET"]
        assert len(get_requests) == 2  # exhausted MAX_RETRIES, then gave up
        step.finalize()

    def test_create_not_retried_on_read_timeout(self, step, sample_doc, requests_mock):
        """A create must not be retried after a read timeout - the document may
        already have been created server-side; retrying risks a duplicate.
        """
        requests_mock.get(KB, json=kb_list_payload())
        requests_mock.post(KB_TEXT, exc=requests.exceptions.ReadTimeout("slow"))

        with pytest.raises(StepFailed, match="All 1 documents failed"):
            step.run([sample_doc])

        post_requests = [r for r in requests_mock.request_history if r.method == "POST"]
        assert len(post_requests) == 1  # not retried

    def test_update_retried_on_connection_error(self, elevenlabs_env, sample_doc, requests_mock):
        """Updates are idempotent (setting content to a known value) - safe to retry."""
        elevenlabs_env.set("MAX_RETRIES", "2")
        step = ElevenLabsKnowledgeBaseStep()
        name = "docs/test-doc"
        requests_mock.get(KB, json=kb_list_payload((name, "doc-existing")))
        requests_mock.patch(
            f"{KB}/doc-existing",
            [
                {"exc": requests.exceptions.ConnectionError("dropped")},
                {"json": {}},
            ],
        )

        result = step.run([sample_doc])

        assert result == [sample_doc]
        patch_requests = [r for r in requests_mock.request_history if r.method == "PATCH"]
        assert len(patch_requests) == 2
        step.finalize()


# ── Prune ──────────────────────────────────────────────────────────────────────


class TestPruneStale:
    def test_prune_disabled_by_default_keeps_stale_document(self, step, sample_doc, requests_mock):
        name = "docs/test-doc"
        requests_mock.get(KB, json=kb_list_payload((name, "doc-existing"), ("stale/doc", "doc-stale")))
        requests_mock.patch(f"{KB}/doc-existing", json={})
        delete_mock = requests_mock.delete(f"{KB}/doc-stale", text="")

        step.run([sample_doc])

        assert not delete_mock.called

    def test_prune_enabled_deletes_stale_document(self, elevenlabs_env, sample_doc, requests_mock, caplog):
        elevenlabs_env.set("NAME_PREFIX", "wurzel/")
        elevenlabs_env.set("PRUNE_STALE", "true")
        step = ElevenLabsKnowledgeBaseStep()
        name = "wurzel/docs/test-doc"
        requests_mock.get(KB, json=kb_list_payload((name, "doc-existing"), ("wurzel/stale/doc", "doc-stale")))
        requests_mock.patch(f"{KB}/doc-existing", json={})
        requests_mock.delete(f"{KB}/doc-stale", text="")

        with caplog.at_level("WARNING"):
            step.run([sample_doc])

        delete_requests = [r for r in requests_mock.request_history if r.method == "DELETE"]
        assert len(delete_requests) == 1
        assert delete_requests[0].qs.get("force") == ["false"]
        # A real (empty-body) DELETE response must not be mistaken for a failed prune.
        assert "Failed to prune" not in caplog.text
        step.finalize()

    def test_prune_force_passed_through(self, elevenlabs_env, sample_doc, requests_mock):
        elevenlabs_env.set("NAME_PREFIX", "wurzel/")
        elevenlabs_env.set("PRUNE_STALE", "true")
        elevenlabs_env.set("PRUNE_FORCE", "true")
        step = ElevenLabsKnowledgeBaseStep()
        requests_mock.get(KB, json=kb_list_payload(("wurzel/stale/doc", "doc-stale")))
        requests_mock.post(KB_TEXT, json=kb_create_payload("doc-1"))
        requests_mock.delete(f"{KB}/doc-stale", text="")

        step.run([sample_doc])

        delete_request = next(r for r in requests_mock.request_history if r.method == "DELETE")
        assert delete_request.qs.get("force") == ["true"]
        step.finalize()

    def test_prune_failure_does_not_raise(self, elevenlabs_env, sample_doc, requests_mock):
        elevenlabs_env.set("NAME_PREFIX", "wurzel/")
        elevenlabs_env.set("PRUNE_STALE", "true")
        step = ElevenLabsKnowledgeBaseStep()
        requests_mock.get(KB, json=kb_list_payload(("wurzel/stale/doc", "doc-stale")))
        requests_mock.post(KB_TEXT, json=kb_create_payload("doc-1"))
        requests_mock.delete(f"{KB}/doc-stale", exc=requests.exceptions.ConnectionError("failed"))

        result = step.run([sample_doc])

        assert result == [sample_doc]
        step.finalize()

    def test_prune_skipped_when_a_push_failed_this_run(self, elevenlabs_env, two_docs, requests_mock, caplog):
        """A systemic failure this run must never also be allowed to delete real
        content - mirrors Wonderful's own "skip prune on upload failure" behavior.
        """
        elevenlabs_env.set("NAME_PREFIX", "wurzel/")
        elevenlabs_env.set("PRUNE_STALE", "true")
        step = ElevenLabsKnowledgeBaseStep()
        requests_mock.get(KB, json=kb_list_payload(("wurzel/stale/doc", "doc-stale")))
        requests_mock.post(
            KB_TEXT,
            [
                {"json": kb_create_payload("doc-1", "doc1")},
                {"exc": requests.exceptions.ConnectionError("failed")},
            ],
        )
        delete_mock = requests_mock.delete(f"{KB}/doc-stale", text="")

        with caplog.at_level("WARNING"):
            result = step.run(two_docs)

        assert result == two_docs
        assert not delete_mock.called
        assert "Skipping prune" in caplog.text
        step.finalize()


# ── Re-running against a persistent KB ──────────────────────────────────────────


class StatefulFakeKB:
    """A minimal, stateful in-memory KB backing GET/POST/PATCH/DELETE, so a
    second `step.run()` call sees documents created by a first one - unlike the
    other tests here, which only ever mock a single request/response in
    isolation. Needed to catch bugs that only show up across repeated runs
    (https://github.com/telekom/wurzel/pull/247#issuecomment-5002614933:
    documents were never recognized as already existing, so every run just
    kept creating new copies instead of updating in place).
    """

    def __init__(self):
        self.docs: dict[str, dict] = {}
        self._next_id = 1

    def register(self, requests_mock):
        requests_mock.get(KB, json=self._list)
        requests_mock.post(KB_TEXT, json=self._create)
        requests_mock.patch(re.compile(rf"{re.escape(KB)}/(?!text)([^/?]+)"), json=self._update)
        requests_mock.delete(re.compile(rf"{re.escape(KB)}/([^/?]+)"), text=self._delete)

    def _list(self, request, context):
        parent_folder_id = request.qs.get("parent_folder_id", [None])[0]
        page_size = int(request.qs.get("page_size", ["100"])[0])
        cursor = request.qs.get("cursor", [None])[0]
        items = [(doc_id, d) for doc_id, d in self.docs.items() if d["parent_folder_id"] == parent_folder_id]
        start = int(cursor) if cursor else 0
        page = items[start : start + page_size]
        next_start = start + page_size
        has_more = next_start < len(items)
        return {
            "documents": [{"id": doc_id, "name": d["name"], "type": "text"} for doc_id, d in page],
            "has_more": has_more,
            "next_cursor": str(next_start) if has_more else None,
        }

    def _create(self, request, context):
        doc_id = f"doc-{self._next_id}"
        self._next_id += 1
        body = request.json()
        self.docs[doc_id] = {"name": body["name"], "content": body["text"], "parent_folder_id": body.get("parent_folder_id")}
        return kb_create_payload(doc_id, body["name"])

    def _update(self, request, context):
        doc_id = request.path.rsplit("/", 1)[-1]
        self.docs[doc_id]["content"] = request.json()["content"]
        return {}

    def _delete(self, request, context):
        self.docs.pop(request.path.rsplit("/", 1)[-1], None)
        return ""


class TestSecondRun:
    """Runs the step twice against a StatefulFakeKB - the scenario a Telekom
    reviewer reported as broken on PR #247: re-running the step (their
    pipeline's normal, periodic operation) didn't update existing documents in
    place, it just kept creating new ones, doubling the knowledge base every
    run. Root cause: `_list_existing` never scoped its GET by PARENT_FOLDER_ID,
    even though `_create` files new documents under it - so once a document
    was filed under a folder, every later run's listing failed to see it and
    treated it as brand new. See `test_parent_folder_id_included_in_list_params`
    for the direct regression test on that request; these exercise the
    same fix through two full `run()` calls instead of a single one.
    """

    def test_second_run_updates_in_place_and_prunes(self, elevenlabs_env, requests_mock):
        elevenlabs_env.set("NAME_PREFIX", "wurzel/")
        elevenlabs_env.set("PRUNE_STALE", "true")
        kb = StatefulFakeKB()
        kb.register(requests_mock)
        docs = [MarkdownDataContract(md=f"# Doc {i}", url=f"https://example.com/doc{i}", keywords="") for i in range(3)]

        ElevenLabsKnowledgeBaseStep().run(docs)
        assert len(kb.docs) == 3

        # Second run, unchanged input: must update in place, not duplicate.
        ElevenLabsKnowledgeBaseStep().run(docs)
        assert len(kb.docs) == 3, f"expected update-in-place, got duplicates: {kb.docs}"
        patch_count = sum(1 for r in requests_mock.request_history if r.method == "PATCH")
        assert patch_count == 3

        # Third run, one doc removed from the source: must prune it.
        ElevenLabsKnowledgeBaseStep().run(docs[:2])
        assert len(kb.docs) == 2, f"expected the removed doc to be pruned, got: {kb.docs}"

    def test_second_run_with_parent_folder_id_does_not_duplicate(self, elevenlabs_env, requests_mock):
        elevenlabs_env.set("PARENT_FOLDER_ID", "folder-1")
        kb = StatefulFakeKB()
        kb.register(requests_mock)
        docs = [MarkdownDataContract(md=f"# Doc {i}", url=f"https://example.com/doc{i}", keywords="") for i in range(5)]

        ElevenLabsKnowledgeBaseStep().run(docs)
        assert len(kb.docs) == 5

        ElevenLabsKnowledgeBaseStep().run(docs)
        assert len(kb.docs) == 5, f"expected update-in-place, got {len(kb.docs)} docs (the reported bug: docs doubled)"

    def test_second_run_at_scale_beyond_one_page(self, elevenlabs_env, requests_mock):
        """The report showed ~1600 existing documents - comfortably more than one
        PAGE_SIZE page - so listing must paginate through everything, not just
        the first page, before deciding what's already there.
        """
        elevenlabs_env.set("NAME_PREFIX", "wurzel/")
        kb = StatefulFakeKB()
        kb.register(requests_mock)
        docs = [MarkdownDataContract(md=f"# Doc {i}", url=f"https://example.com/doc{i}", keywords="") for i in range(250)]

        ElevenLabsKnowledgeBaseStep().run(docs)
        assert len(kb.docs) == 250

        ElevenLabsKnowledgeBaseStep().run(docs)
        assert len(kb.docs) == 250, f"expected update-in-place across all pages, got {len(kb.docs)} docs"


# ── Failure scenarios ──────────────────────────────────────────────────────────


class TestFailureScenarios:
    def test_all_fail_raises_step_failed(self, step, sample_doc, requests_mock):
        requests_mock.get(KB, json=kb_list_payload())
        requests_mock.post(KB_TEXT, exc=requests.exceptions.ConnectionError("failed"))

        with pytest.raises(StepFailed, match="All 1 documents failed"):
            step.run([sample_doc])

    def test_partial_failure_returns_input(self, step, two_docs, requests_mock):
        requests_mock.get(KB, json=kb_list_payload())
        requests_mock.post(
            KB_TEXT,
            [
                {"json": kb_create_payload("doc-1", "doc1")},
                {"exc": requests.exceptions.ConnectionError("failed")},
            ],
        )

        result = step.run(two_docs)

        assert result == two_docs


# ── Folder-per-source: category derivation ─────────────────────────────────────


class TestSourceCategory:
    def test_none_when_history_unset(self, step):
        assert step._source_category() is None

    def test_first_segment_of_two_step_chain(self, step, history_scope):
        history_scope("SourceA", "ElevenLabsKnowledgeBase")
        assert step._source_category() == "SourceA"

    def test_recovers_true_origin_despite_disk_fragmentation(self, step, history_scope):
        """Reproduces the on-disk filename round-trip: once an intermediate step (e.g. a
        splitter) sits between the true source and this step, base_executor.load()
        re-parses the stored filename stem as a SINGLE atomic History entry rather than
        splitting it back into per-step components - so history.get() here looks like
        ["SourceA-Splitter", "ElevenLabsKnowledgeBase"], not
        ["SourceA", "Splitter", "ElevenLabsKnowledgeBase"]. Indexing [0] would incorrectly
        return "SourceA-Splitter"; joining then re-splitting must still recover the true
        original source, "SourceA".
        """
        history_scope("SourceA-Splitter", "ElevenLabsKnowledgeBase")
        assert step._source_category() == "SourceA"

    def test_single_element_history_returns_own_name(self, step, history_scope):
        history_scope("ElevenLabsKnowledgeBase")
        assert step._source_category() == "ElevenLabsKnowledgeBase"


# ── Folder-per-source: get-or-create resolution ─────────────────────────────────


class TestResolveCategoryFolder:
    def test_creates_folder_when_missing(self, elevenlabs_env, requests_mock):
        elevenlabs_env.set("PARENT_FOLDER_ID", "root-1")
        step = ElevenLabsKnowledgeBaseStep()
        register_kb_listing(requests_mock, folders=())
        create_mock = requests_mock.post(KB_FOLDER, json=kb_create_payload("folder-1", "SourceA"))

        folder_id = step._resolve_category_folder_id("SourceA")

        assert folder_id == "folder-1"
        assert create_mock.called_once
        assert create_mock.last_request.json() == {"name": "SourceA", "parent_folder_id": "root-1"}
        step.finalize()

    def test_reuses_existing_folder(self, elevenlabs_env, requests_mock):
        elevenlabs_env.set("PARENT_FOLDER_ID", "root-1")
        step = ElevenLabsKnowledgeBaseStep()
        register_kb_listing(requests_mock, folders=[("SourceA", "folder-existing")])
        create_mock = requests_mock.post(KB_FOLDER, json=kb_create_payload("folder-new"))

        folder_id = step._resolve_category_folder_id("SourceA")

        assert folder_id == "folder-existing"
        assert not create_mock.called
        step.finalize()

    def test_caches_across_calls(self, elevenlabs_env, requests_mock):
        elevenlabs_env.set("PARENT_FOLDER_ID", "root-1")
        step = ElevenLabsKnowledgeBaseStep()
        register_kb_listing(requests_mock, folders=())
        requests_mock.post(KB_FOLDER, json=kb_create_payload("folder-1", "SourceA"))

        first = step._resolve_category_folder_id("SourceA")
        second = step._resolve_category_folder_id("SourceA")

        assert first == second == "folder-1"
        get_requests = [r for r in requests_mock.request_history if r.method == "GET"]
        assert len(get_requests) == 1  # second call served from cache, no re-list
        post_requests = [r for r in requests_mock.request_history if r.method == "POST"]
        assert len(post_requests) == 1  # and no second create
        step.finalize()

    def test_multiple_matches_logs_warning_and_never_deletes(self, elevenlabs_env, requests_mock, caplog):
        """The API enforces no uniqueness on folder names (confirmed against the real API),
        so duplicates can happen. Unlike duplicate text documents, a duplicate folder is
        never auto-deleted - it might hold real nested content - just deterministically
        resolved (lowest id) with a warning logged.
        """
        elevenlabs_env.set("PARENT_FOLDER_ID", "root-1")
        step = ElevenLabsKnowledgeBaseStep()
        register_kb_listing(requests_mock, folders=[("SourceA", "folder-b"), ("SourceA", "folder-a")])
        delete_mock = requests_mock.delete(re.compile(rf"{re.escape(KB)}/folder-"), text="")

        with caplog.at_level("WARNING"):
            folder_id = step._resolve_category_folder_id("SourceA")

        assert folder_id == "folder-a"  # lowest id, deterministic
        assert not delete_mock.called
        assert "Multiple folders named" in caplog.text
        step.finalize()

    def test_folder_create_not_retried_on_read_timeout(self, elevenlabs_env, requests_mock):
        """Mirrors the text-document create: the folder may already exist server-side
        after a read timeout, and since folder names aren't deduped, retrying risks a
        second folder with the same name.
        """
        elevenlabs_env.set("PARENT_FOLDER_ID", "root-1")
        step = ElevenLabsKnowledgeBaseStep()
        register_kb_listing(requests_mock, folders=())
        requests_mock.post(KB_FOLDER, exc=requests.exceptions.ReadTimeout("slow"))

        with pytest.raises(requests.exceptions.ReadTimeout):
            step._resolve_category_folder_id("SourceA")

        post_requests = [r for r in requests_mock.request_history if r.method == "POST"]
        assert len(post_requests) == 1  # not retried
        step.finalize()


# ── Folder-per-source: end-to-end via run() ──────────────────────────────────────


class TestFolderPerSource:
    def test_disabled_by_default_matches_prior_behavior(self, elevenlabs_env, sample_doc, requests_mock, history_scope):
        elevenlabs_env.set("PARENT_FOLDER_ID", "root-1")
        history_scope("SourceA")
        step = ElevenLabsKnowledgeBaseStep()
        requests_mock.get(KB, json=kb_list_payload())
        requests_mock.post(KB_TEXT, json=kb_create_payload("doc-1"))

        step.run([sample_doc])

        assert not [r for r in requests_mock.request_history if r.url == KB_FOLDER]
        post_request = next(r for r in requests_mock.request_history if r.method == "POST")
        assert post_request.json()["parent_folder_id"] == "root-1"
        step.finalize()

    def test_validator_requires_parent_folder_id(self, elevenlabs_env):
        elevenlabs_env.set("FOLDER_PER_SOURCE", "true")
        with pytest.raises(ValueError, match="PARENT_FOLDER_ID is required"):
            ElevenLabsKnowledgeBaseStep()

    def test_files_documents_into_resolved_category_folder(self, elevenlabs_env, sample_doc, requests_mock, history_scope):
        elevenlabs_env.set("PARENT_FOLDER_ID", "root-1")
        elevenlabs_env.set("FOLDER_PER_SOURCE", "true")
        history_scope("SourceA")
        step = ElevenLabsKnowledgeBaseStep()
        register_kb_listing(requests_mock, folders=(), texts=())
        requests_mock.post(KB_FOLDER, json=kb_create_payload("folder-a", "SourceA"))
        requests_mock.post(KB_TEXT, json=kb_create_payload("doc-1"))

        step.run([sample_doc])

        folder_create = next(r for r in requests_mock.request_history if r.method == "POST" and r.url == KB_FOLDER)
        assert folder_create.json() == {"name": "SourceA", "parent_folder_id": "root-1"}
        doc_create = next(r for r in requests_mock.request_history if r.method == "POST" and r.url == KB_TEXT)
        assert doc_create.json()["parent_folder_id"] == "folder-a"
        # The text listing must be scoped to the *resolved* category folder, not the raw
        # PARENT_FOLDER_ID - otherwise a document filed under it on a prior run would look
        # "new" every time (the same class of bug fixed for PARENT_FOLDER_ID itself in
        # https://github.com/telekom/wurzel/pull/247, reproduced here for category folders).
        text_list_get = next(r for r in requests_mock.request_history if r.method == "GET" and r.qs.get("types") == ["text"])
        assert text_list_get.qs.get("parent_folder_id") == ["folder-a"]
        step.finalize()

    def test_reuses_existing_category_folder(self, elevenlabs_env, sample_doc, requests_mock, history_scope):
        elevenlabs_env.set("PARENT_FOLDER_ID", "root-1")
        elevenlabs_env.set("FOLDER_PER_SOURCE", "true")
        history_scope("SourceA")
        step = ElevenLabsKnowledgeBaseStep()
        register_kb_listing(requests_mock, folders=[("SourceA", "folder-existing")])
        folder_create = requests_mock.post(KB_FOLDER, json=kb_create_payload("folder-new"))
        requests_mock.post(KB_TEXT, json=kb_create_payload("doc-1"))

        step.run([sample_doc])

        assert not folder_create.called
        doc_create = next(r for r in requests_mock.request_history if r.method == "POST" and r.url == KB_TEXT)
        assert doc_create.json()["parent_folder_id"] == "folder-existing"
        step.finalize()

    def test_falls_back_without_history(self, elevenlabs_env, sample_doc, requests_mock, caplog):
        """No step_history (e.g. the step run directly, outside the wurzel Executor) means
        categorization can't be derived - this must fall back to filing directly under
        PARENT_FOLDER_ID rather than raising, or silently filing at the KB root.
        """
        elevenlabs_env.set("PARENT_FOLDER_ID", "root-1")
        elevenlabs_env.set("FOLDER_PER_SOURCE", "true")
        step = ElevenLabsKnowledgeBaseStep()
        requests_mock.get(KB, json=kb_list_payload())
        requests_mock.post(KB_TEXT, json=kb_create_payload("doc-1"))

        with caplog.at_level("WARNING"):
            step.run([sample_doc])

        assert not [r for r in requests_mock.request_history if r.url == KB_FOLDER]
        doc_create = next(r for r in requests_mock.request_history if r.method == "POST" and r.url == KB_TEXT)
        assert doc_create.json()["parent_folder_id"] == "root-1"
        assert "no step_history is set" in caplog.text
        step.finalize()

    def test_caches_across_multiple_run_calls_on_same_instance(self, elevenlabs_env, requests_mock, history_scope):
        """A single step instance's run() may be invoked many times per execution - once per
        upstream file/shard, per the class docstring - so the category folder should only
        be resolved (listed, and created if missing) once across those calls, not on every
        invocation.
        """
        elevenlabs_env.set("PARENT_FOLDER_ID", "root-1")
        elevenlabs_env.set("FOLDER_PER_SOURCE", "true")
        history_scope("SourceA")
        step = ElevenLabsKnowledgeBaseStep()
        register_kb_listing(requests_mock, folders=())
        requests_mock.post(KB_FOLDER, json=kb_create_payload("folder-a", "SourceA"))
        requests_mock.post(KB_TEXT, [{"json": kb_create_payload("doc-1")}, {"json": kb_create_payload("doc-2")}])
        doc_a = MarkdownDataContract(md="# A", url="https://example.com/a", keywords="")
        doc_b = MarkdownDataContract(md="# B", url="https://example.com/b", keywords="")

        step.run([doc_a])
        step.run([doc_b])

        folder_creates = [r for r in requests_mock.request_history if r.method == "POST" and r.url == KB_FOLDER]
        assert len(folder_creates) == 1  # second run() reused the cached folder id
        step.finalize()


# ── Push disabled ──────────────────────────────────────────────────────────────


class TestPushDisabled:
    def test_push_disabled_returns_input_without_api_calls(self, env, sample_doc, requests_mock):
        env.set("PUSH_ENABLED", "false")
        step = ElevenLabsKnowledgeBaseStep()

        result = step.run([sample_doc])

        assert result == [sample_doc]
        assert requests_mock.request_history == []
        step.finalize()

    def test_push_disabled_with_empty_input(self, env):
        env.set("PUSH_ENABLED", "false")
        step = ElevenLabsKnowledgeBaseStep()

        assert step.run([]) == []
        step.finalize()


# ── Finalize ───────────────────────────────────────────────────────────────────


class TestFinalize:
    def test_finalize_closes_session(self, elevenlabs_env):
        with patch("wurzel.steps.elevenlabs.step.requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session

            step = ElevenLabsKnowledgeBaseStep()
            step.finalize()

            mock_session.close.assert_called_once()

    def test_finalize_no_session_when_push_disabled(self, env):
        env.set("PUSH_ENABLED", "false")
        with patch("wurzel.steps.elevenlabs.step.requests.Session") as mock_session_cls:
            step = ElevenLabsKnowledgeBaseStep()
            step.finalize()  # should not raise
            mock_session_cls.assert_not_called()
