# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Standalone, offline walkthrough of ElevenLabsKnowledgeBaseStep's FOLDER_PER_SOURCE feature.

Run directly:

    python tests/steps/elevenlabs/folder_per_source_demo.py

This is deliberately NOT a pytest test (its name doesn't match test_*.py/*_test.py, so
pytest's default collection skips it) - it's a human-readable narrative that exercises
the feature end-to-end and prints a pass/fail report, complementing the focused unit
tests in step_test.py. No network calls are made and no credentials are required: the
ElevenLabs Knowledge Base is simulated entirely in memory via requests_mock, modeling
exactly the API behavior this feature depends on (folders and documents share one
paginated list endpoint, distinguished by `type`; folder names are NOT deduplicated
server-side - see SimulatedKnowledgeBase below).

Scenarios covered:
  1. Two distinct sources land their documents in their own, distinctly-named folders.
  2. A second run (fresh step instance, e.g. the next scheduled run) updates documents
     in place and reuses the existing folders rather than duplicating either.
  3. Pruning a document from one source only ever touches that source's own folder.
  4. Folder lookup paginates correctly through many pre-existing folders at PAGE_SIZE
     granularity, rather than only inspecting the first page.
  5. Category resolution recovers the true originating step even when this invocation's
     step_history has already round-tripped through an intermediate step (e.g. a
     splitter) - the disk-fragmentation edge case described in _source_category's
     docstring.
  6. Pre-existing duplicate folders (the API enforces no uniqueness on folder names) are
     resolved deterministically and never auto-deleted.
  7. With no step_history set (the step run directly, outside the wurzel Executor),
     FOLDER_PER_SOURCE falls back to filing directly under PARENT_FOLDER_ID.
  8. With FOLDER_PER_SOURCE left at its default (False), behavior is unchanged from
     before this feature existed.
"""

import itertools
import os
import re
import sys
from contextlib import contextmanager

import requests_mock

from wurzel.core import step_history
from wurzel.core.history import History
from wurzel.datacontract import MarkdownDataContract
from wurzel.steps.elevenlabs import ElevenLabsKnowledgeBaseStep

# Line-buffer stdout so `print()` output interleaves in chronological order with the
# `logging` module's warnings (which flush to stderr immediately) when output is piped
# rather than attached to a terminal.
sys.stdout.reconfigure(line_buffering=True)  # ty: ignore[unresolved-attribute]

BASE_URL = "https://api.elevenlabs.io"
KB = f"{BASE_URL}/v1/convai/knowledge-base"
KB_TEXT = f"{KB}/text"
KB_FOLDER = f"{KB}/folder"

_FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    """Record a pass/fail line for `message`; failures are collected for the final summary."""
    if condition:
        print(f"  [ok]   {message}")  # noqa: T201
    else:
        print(f"  [FAIL] {message}")  # noqa: T201
        _FAILURES.append(message)


@contextmanager
def scoped_env(**env: str):
    """Set env vars for the duration of the block, restoring whatever was there before.

    Mirrors tests/conftest.py's SetEnv fixture, but usable outside pytest. Step settings
    read bare field names (e.g. "API_KEY", not "ELEVENLABSKNOWLEDGEBASESTEP__API_KEY") -
    confirmed against tests/steps/elevenlabs/step_test.py's elevenlabs_env fixture, since
    TypedStep.__init__ instantiates settings_class() with no env_prefix applied.
    """
    previous = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        yield
    finally:
        for k, v in previous.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@contextmanager
def as_invocation(*chain: str):
    """Set step_history for the duration of the block, as the wurzel Executor would before run()."""
    token = step_history.set(History(*chain))
    try:
        yield
    finally:
        step_history.reset(token)


def make_doc(source: str, i: int) -> MarkdownDataContract:
    return MarkdownDataContract(
        md=f"# {source} document {i}\n\nContent for {source} article #{i}.",
        url=f"https://example.com/{source.lower()}/article-{i}",
        keywords="",
    )


class SimulatedKnowledgeBase:
    """In-memory stand-in for the real ElevenLabs Knowledge Base, wired into requests_mock.

    Mirrors the behavior this feature actually depends on (confirmed against the real
    API/docs, not guessed):
      - documents and folders share one id-space and one paginated list endpoint,
        distinguished by a `type` field ("text" or "folder")
      - GET .../knowledge-base paginates via page_size/cursor and filters by types +
        parent_folder_id
      - POST .../folder enforces NO uniqueness: creating a folder with a name/parent
        that already exists succeeds and produces a second, distinct folder. step.py's
        own get-or-create logic (_find_folder/_resolve_category_folder_id) is what
        prevents this from causing duplicates in practice - this simulator deliberately
        does NOT paper over that by deduplicating for it.
    """

    def __init__(self) -> None:
        self._next_id = itertools.count(1)
        self.documents: dict[str, dict] = {}  # id -> {"name", "type", "parent_folder_id", "content"}

    def register(self, mocker: requests_mock.Mocker) -> None:
        mocker.get(KB, json=self._list)
        mocker.post(KB_TEXT, json=self._create_text)
        mocker.post(KB_FOLDER, json=self._create_folder)
        mocker.patch(re.compile(rf"{re.escape(KB)}/(?!text|folder)([^/?]+)"), json=self._update)
        mocker.delete(re.compile(rf"{re.escape(KB)}/([^/?]+)"), text=self._delete)

    # -- helpers used by scenarios to seed state / inspect results -----------------

    def seed_folder(self, name: str, parent_folder_id: str | None) -> str:
        folder_id = self._new_id("folder")
        self.documents[folder_id] = {"name": name, "type": "folder", "content": None, "parent_folder_id": parent_folder_id}
        return folder_id

    def folder_id_for(self, name: str, parent_folder_id: str | None) -> str | None:
        for doc_id, d in self.documents.items():
            if d["type"] == "folder" and d["name"] == name and d["parent_folder_id"] == parent_folder_id:
                return doc_id
        return None

    def folders(self) -> dict[str, dict]:
        return {doc_id: d for doc_id, d in self.documents.items() if d["type"] == "folder"}

    def documents_in(self, parent_folder_id: str | None) -> dict[str, dict]:
        return {doc_id: d for doc_id, d in self.documents.items() if d["type"] == "text" and d["parent_folder_id"] == parent_folder_id}

    # -- mocked endpoint handlers ----------------------------------------------------

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}-{next(self._next_id)}"

    def _list(self, request, _context):
        types = request.qs.get("types", [])
        parent_folder_id = request.qs.get("parent_folder_id", [None])[0]
        page_size = int(request.qs.get("page_size", ["100"])[0])
        cursor = request.qs.get("cursor", [None])[0]

        def _matches(d: dict) -> bool:
            return (not types or d["type"] in types) and d["parent_folder_id"] == parent_folder_id

        items = sorted(((doc_id, d) for doc_id, d in self.documents.items() if _matches(d)), key=lambda kv: kv[0])
        start = int(cursor) if cursor else 0
        page = items[start : start + page_size]
        next_start = start + page_size
        has_more = next_start < len(items)
        return {
            "documents": [{"id": doc_id, "name": d["name"], "type": d["type"]} for doc_id, d in page],
            "has_more": has_more,
            "next_cursor": str(next_start) if has_more else None,
        }

    def _create_text(self, request, _context):
        body = request.json()
        doc_id = self._new_id("doc")
        self.documents[doc_id] = {
            "name": body["name"],
            "type": "text",
            "content": body["text"],
            "parent_folder_id": body.get("parent_folder_id"),
        }
        return {"id": doc_id, "name": body["name"], "folder_path": []}

    def _create_folder(self, request, _context):
        body = request.json()
        folder_id = self._new_id("folder")
        self.documents[folder_id] = {
            "name": body["name"],
            "type": "folder",
            "content": None,
            "parent_folder_id": body.get("parent_folder_id"),
        }
        return {"id": folder_id, "name": body["name"], "folder_path": []}

    def _update(self, request, _context):
        doc_id = request.path.rsplit("/", 1)[-1]
        self.documents[doc_id]["content"] = request.json()["content"]
        return {}

    def _delete(self, request, _context):
        self.documents.pop(request.path.rsplit("/", 1)[-1], None)
        return ""


# ── Scenarios ─────────────────────────────────────────────────────────────────────


def scenario_two_sources_and_lifecycle() -> None:
    print("\n=== Scenario: two sources get their own folders, survive re-runs and pruning ===")  # noqa: T201
    with requests_mock.Mocker() as m:
        kb = SimulatedKnowledgeBase()
        kb.register(m)

        env = {
            "API_KEY": "k",
            "MAX_RETRIES": "1",
            "RETRY_BACKOFF": "0",
            "PARENT_FOLDER_ID": "root",
            "FOLDER_PER_SOURCE": "true",
            "NAME_PREFIX": "wurzel/",
        }
        with scoped_env(**env):
            faq_docs = [make_doc("FAQ", i) for i in range(500)]
            sales_docs = [make_doc("SalesCatalog", i) for i in range(500)]

            step = ElevenLabsKnowledgeBaseStep()
            with as_invocation("FAQStep"):
                step.run(faq_docs)
            with as_invocation("SalesCatalogStep"):
                step.run(sales_docs)

            faq_folder = kb.folder_id_for("FAQ", "root")
            sales_folder = kb.folder_id_for("SalesCatalog", "root")
            check(faq_folder is not None, "FAQ category folder created under PARENT_FOLDER_ID")
            check(sales_folder is not None, "SalesCatalog category folder created under PARENT_FOLDER_ID")
            check(faq_folder != sales_folder, "the two sources got distinct folders")
            check(len(kb.documents_in(faq_folder)) == 500, "all 500 FAQ documents landed in the FAQ folder")
            check(len(kb.documents_in(sales_folder)) == 500, "all 500 SalesCatalog documents landed in the SalesCatalog folder")
            check(len(kb.documents_in("root")) == 0, "PARENT_FOLDER_ID itself holds no stray documents")
            step.finalize()

            # Second run: a *fresh* step instance (simulating a new scheduled run/process,
            # not the local per-instance cache) with unchanged input - must update in
            # place, not duplicate, and must not create a second folder for either source.
            step2 = ElevenLabsKnowledgeBaseStep()
            with as_invocation("FAQStep"):
                step2.run(faq_docs)
            with as_invocation("SalesCatalogStep"):
                step2.run(sales_docs)

            check(kb.folder_id_for("FAQ", "root") == faq_folder, "second run reused the existing FAQ folder rather than creating another")
            check(kb.folder_id_for("SalesCatalog", "root") == sales_folder, "second run reused the existing SalesCatalog folder")
            check(len(kb.documents_in(faq_folder)) == 500, "second run updated FAQ documents in place, no duplicates")
            check(len(kb.documents_in(sales_folder)) == 500, "second run updated SalesCatalog documents in place, no duplicates")
            step2.finalize()

            # Third run: FAQ drops 100 documents with PRUNE_STALE on - must remove them
            # from ITS folder only; SalesCatalog's folder/documents must be untouched.
            with scoped_env(PRUNE_STALE="true"):
                step3 = ElevenLabsKnowledgeBaseStep()
                with as_invocation("FAQStep"):
                    step3.run(faq_docs[:400])
                step3.finalize()

            check(len(kb.documents_in(faq_folder)) == 400, "pruning removed the 100 dropped FAQ documents from the FAQ folder")
            check(len(kb.documents_in(sales_folder)) == 500, "SalesCatalog's documents were untouched by FAQ's prune")


def scenario_pagination_at_scale() -> None:
    print("\n=== Scenario: folder lookup paginates through many pre-existing folders ===")  # noqa: T201
    with requests_mock.Mocker() as m:
        kb = SimulatedKnowledgeBase()
        kb.register(m)

        env = {
            "API_KEY": "k",
            "MAX_RETRIES": "1",
            "RETRY_BACKOFF": "0",
            "PARENT_FOLDER_ID": "root",
            "FOLDER_PER_SOURCE": "true",
            "NAME_PREFIX": "wurzel/",
            "PAGE_SIZE": "5",
        }
        with scoped_env(**env):
            # 23 unrelated category folders (other sources / prior runs) plus the one
            # this run is actually looking for - forces _find_folder past several pages.
            for i in range(23):
                kb.seed_folder(f"OtherSource{i}", parent_folder_id="root")
            target_folder = kb.seed_folder("FAQ", parent_folder_id="root")

            step = ElevenLabsKnowledgeBaseStep()
            with as_invocation("FAQStep"):
                step.run([make_doc("FAQ", 0)])

            folder_list_requests = [r for r in m.request_history if r.method == "GET" and r.qs.get("types") == ["folder"]]
            page_count = len(folder_list_requests)
            check(page_count > 1, f"folder lookup paginated across {page_count} requests rather than stopping at page one")
            check(kb.folder_id_for("FAQ", "root") == target_folder, "found the pre-existing FAQ folder rather than creating a duplicate")
            faq_named = [d for d in kb.folders().values() if d["name"] == "FAQ"]
            check(len(faq_named) == 1, "still exactly one FAQ folder after the run - no duplicate created")
            step.finalize()


def scenario_multi_hop_history_fragmentation() -> None:
    print("\n=== Scenario: category resolves to the true source despite an intermediate step ===")  # noqa: T201
    with requests_mock.Mocker() as m:
        kb = SimulatedKnowledgeBase()
        kb.register(m)

        with scoped_env(API_KEY="k", MAX_RETRIES="1", RETRY_BACKOFF="0", PARENT_FOLDER_ID="root", FOLDER_PER_SOURCE="true"):
            step = ElevenLabsKnowledgeBaseStep()
            # Reproduces what step_history actually looks like once this invocation's
            # data has round-tripped through disk with one intermediate step (e.g. a
            # splitter) in between - see base_executor.py's store()/load(): the on-disk
            # filename encodes the joined upstream chain, and reloading it re-parses
            # that join as a single atomic entry ("FAQ-Splitter") rather than splitting
            # it back into "FAQ" + "Splitter". Naively indexing history.get()[0] would
            # return "FAQ-Splitter"; _source_category must still recover "FAQ".
            with as_invocation("FAQ-Splitter", "ElevenLabsKnowledgeBase"):
                step.run([make_doc("FAQ", 0)])

            check(kb.folder_id_for("FAQ", "root") is not None, 'category resolved to the true origin "FAQ"')
            check(kb.folder_id_for("FAQ-Splitter", "root") is None, 'no folder named "FAQ-Splitter" was created')
            step.finalize()


def scenario_duplicate_folder_collision() -> None:
    print("\n=== Scenario: pre-existing duplicate folders are resolved deterministically, never deleted ===")  # noqa: T201
    with requests_mock.Mocker() as m:
        kb = SimulatedKnowledgeBase()
        kb.register(m)

        with scoped_env(API_KEY="k", MAX_RETRIES="1", RETRY_BACKOFF="0", PARENT_FOLDER_ID="root", FOLDER_PER_SOURCE="true"):
            folder_a = kb.seed_folder("FAQ", parent_folder_id="root")
            folder_b = kb.seed_folder("FAQ", parent_folder_id="root")
            expected = sorted([folder_a, folder_b])[0]

            step = ElevenLabsKnowledgeBaseStep()
            with as_invocation("FAQStep"):
                step.run([make_doc("FAQ", 0)])

            check(folder_a in kb.documents and folder_b in kb.documents, "both duplicate folders still exist - neither was auto-deleted")
            check(len(kb.documents_in(expected)) == 1, f"the new document was filed into the deterministically-chosen folder ({expected})")
            step.finalize()


def scenario_fallback_without_history() -> None:
    print("\n=== Scenario: FOLDER_PER_SOURCE falls back to the flat folder when step_history is unset ===")  # noqa: T201
    with requests_mock.Mocker() as m:
        kb = SimulatedKnowledgeBase()
        kb.register(m)

        with scoped_env(API_KEY="k", MAX_RETRIES="1", RETRY_BACKOFF="0", PARENT_FOLDER_ID="root", FOLDER_PER_SOURCE="true"):
            step = ElevenLabsKnowledgeBaseStep()
            step.run([make_doc("Direct", 0)])  # no as_invocation() - step_history stays unset

            check(len(kb.folders()) == 0, "no category folder was created")
            check(len(kb.documents_in("root")) == 1, "the document was filed directly under PARENT_FOLDER_ID instead")
            step.finalize()


def scenario_disabled_matches_prior_behavior() -> None:
    print("\n=== Scenario: FOLDER_PER_SOURCE left at its default (False) is unchanged from before ===")  # noqa: T201
    with requests_mock.Mocker() as m:
        kb = SimulatedKnowledgeBase()
        kb.register(m)

        with scoped_env(API_KEY="k", MAX_RETRIES="1", RETRY_BACKOFF="0", PARENT_FOLDER_ID="root"):
            step = ElevenLabsKnowledgeBaseStep()
            with as_invocation("FAQStep"):
                step.run([make_doc("FAQ", 0)])

            check(len(kb.folders()) == 0, "no category folders created when the feature is off")
            check(len(kb.documents_in("root")) == 1, "the document was filed under PARENT_FOLDER_ID, as before this feature existed")
            step.finalize()


def main() -> int:
    scenario_two_sources_and_lifecycle()
    scenario_pagination_at_scale()
    scenario_multi_hop_history_fragmentation()
    scenario_duplicate_folder_collision()
    scenario_fallback_without_history()
    scenario_disabled_matches_prior_behavior()

    print("\n" + "=" * 70)  # noqa: T201
    if _FAILURES:
        print(f"{len(_FAILURES)} check(s) FAILED:")  # noqa: T201
        for f in _FAILURES:
            print(f"  - {f}")  # noqa: T201
        return 1
    print("All checks passed.")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
