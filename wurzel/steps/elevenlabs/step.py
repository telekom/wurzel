# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""ElevenLabs Knowledge Base connector step for pushing markdown documents."""

# pylint: disable=duplicate-code
# Each connector step in wurzel/steps/ is an intentionally independent module
# rather than sharing a base class, so the retry/back-off logic, error
# formatting, and session-init pattern are duplicated by design.

import random
import time
from collections.abc import Iterator
from logging import getLogger
from typing import Any
from urllib.parse import urlparse

import requests

from wurzel.core import TypedStep, step_history
from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed

from .settings import ElevenLabsKnowledgeBaseSettings

log = getLogger(__name__)

KNOWLEDGE_BASE_PATH = "/v1/convai/knowledge-base"
KNOWLEDGE_BASE_FOLDER_PATH = f"{KNOWLEDGE_BASE_PATH}/folder"


class ElevenLabsKnowledgeBaseStep(TypedStep[ElevenLabsKnowledgeBaseSettings, list[MarkdownDataContract], list[MarkdownDataContract]]):
    """ElevenLabs Agents Knowledge Base connector step.

    Takes MarkdownDataContract documents and creates or updates a text document
    per input in the ElevenLabs Knowledge Base, then returns the original input
    documents unchanged.

    Document names are derived deterministically from each document's URL (mirroring
    its path), so re-running the step against the same input updates existing
    documents in place instead of creating duplicates. Names are additionally scoped
    by NAME_PREFIX and a tag derived from ``wurzel.core.step_history`` identifying the
    current invocation's upstream lineage - stable across successive runs of the same
    pipeline, but distinct across different upstream sources. This matters because
    wurzel calls ``run()`` once per upstream file, not once per pipeline run: a step
    with more than one ``dependsOn``, or a single upstream step that shards its output
    across files, causes multiple separate invocations within one run, each seeing only
    its own slice of the data. The history tag ensures each invocation only ever sees
    and manages its own lineage's documents, never another invocation's.

    When PUSH_ENABLED is False the step returns the input data immediately
    without making any API calls.

    Prune (optional, gated by PRUNE_STALE): after processing, delete documents that
    are in the knowledge base but not in the input, so the knowledge base mirrors
    the input. Requires NAME_PREFIX (the knowledge base is a single flat namespace
    shared by every integration in the workspace) and is skipped on any push failure.
    Scoped by the history tag described above, so pruning one invocation's stale
    documents never touches a different invocation's documents within the same run.

    Folder-per-source (optional, gated by FOLDER_PER_SOURCE): rather than filing every
    document directly under PARENT_FOLDER_ID, resolve (creating if missing) a subfolder
    named after this invocation's originating source step - see ``_source_category`` -
    and file into that instead. Intended for pipelines where PARENT_FOLDER_ID accumulates
    documents from many distinct sources (e.g. FAQ, Sales Catalog): each source gets its
    own subfolder instead of thousands of documents sharing one flat namespace. Folder ids
    are cached per category for the lifetime of the step instance (see ``_resolve_category_folder_id``),
    since a single instance's run() may be invoked many times per execution (once per
    upstream file, as above). Requires PARENT_FOLDER_ID (enforced by a settings validator):
    without it, category folders would be created at the knowledge base root, where an
    unprefixed, server-side-undeduplicated folder name could collide with unrelated content.

    Environment Variables:
        ELEVENLABSKNOWLEDGEBASESTEP__API_KEY:           API key for authentication (required when PUSH_ENABLED is True)
        ELEVENLABSKNOWLEDGEBASESTEP__BASE_URL:          ElevenLabs API base URL (default: https://api.elevenlabs.io)
        ELEVENLABSKNOWLEDGEBASESTEP__NAME_PREFIX:       Prefix for generated document names (default: "", required when PRUNE_STALE is True)
        ELEVENLABSKNOWLEDGEBASESTEP__PARENT_FOLDER_ID:  Knowledge base folder id for new documents
        ELEVENLABSKNOWLEDGEBASESTEP__FOLDER_PER_SOURCE: Per-source-step subfolder (default: False, requires PARENT_FOLDER_ID)
        ELEVENLABSKNOWLEDGEBASESTEP__TIMEOUT:           Request timeout in seconds (default: 120)
        ELEVENLABSKNOWLEDGEBASESTEP__PUSH_ENABLED:      Whether to push to ElevenLabs (default: True)
        ELEVENLABSKNOWLEDGEBASESTEP__PRUNE_STALE:       Delete documents absent from input, mirroring it (default: False)
        ELEVENLABSKNOWLEDGEBASESTEP__PRUNE_FORCE:       Force-delete documents attached to agents (default: False)
        ELEVENLABSKNOWLEDGEBASESTEP__PAGE_SIZE:         Page size when listing existing documents (default: 100)
        ELEVENLABSKNOWLEDGEBASESTEP__MAX_RETRIES:       Max attempts per HTTP call (default: 3)
        ELEVENLABSKNOWLEDGEBASESTEP__RETRY_BACKOFF:     Base back-off seconds - 0.5s, 1s, 2s, ... (default: 0.5)
    """

    def __init__(self) -> None:
        super().__init__()
        self._session: requests.Session | None = None
        self._category_folder_cache: dict[str, str] = {}
        if self.settings.PUSH_ENABLED:
            self._session = requests.Session()
            self._session.headers.update({"xi-api-key": self.settings.API_KEY.get_secret_value()})  # ty: ignore[unresolved-attribute]

    def _request(self, method: str, endpoint: str, idempotent: bool = True, **kwargs: Any) -> dict[str, Any]:
        """Make a request to the ElevenLabs API, retrying transient failures.

        Some endpoints (e.g. DELETE) return an empty body rather than JSON;
        treat that as an empty result instead of failing to parse it.
        """

        def _do_request() -> dict[str, Any]:
            if self._session is None:
                raise StepFailed("ElevenLabs session is not initialized")
            response = self._session.request(
                method,
                f"{self.settings.BASE_URL}{endpoint}",
                timeout=self.settings.TIMEOUT,
                **kwargs,
            )
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()

        return self._with_retry(_do_request, idempotent=idempotent)

    @staticmethod
    def _should_retry(exc: requests.exceptions.RequestException, idempotent: bool) -> bool:
        """Whether ``exc`` is a transient error worth retrying.

        - Read timeout: the server may already have processed the request, so only
          retry idempotent calls - re-sending a create would duplicate the document.
        - Connect timeout / connection error: the request never reached the server,
          so it is always safe to retry.
        - HTTP 429 / 5xx: transient server-side, safe to retry.
        - Other 4xx: permanent client error, never retry.
        """
        if isinstance(exc, requests.exceptions.ReadTimeout):
            return idempotent
        if isinstance(exc, requests.exceptions.ConnectTimeout | requests.exceptions.ConnectionError):
            return True
        if isinstance(exc, requests.exceptions.Timeout):
            return idempotent
        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            return exc.response.status_code == 429 or exc.response.status_code >= 500
        return False

    def _with_retry(self, fn: Any, *, idempotent: bool) -> Any:
        """Call fn() with full-jitter exponential back-off retry.

        Only transient request errors are retried (see ``_should_retry``); permanent
        errors propagate immediately. ``idempotent=False`` is used for calls that
        must not be re-sent after a read timeout (e.g. document creation).
        """
        for attempt in range(self.settings.MAX_RETRIES):
            try:
                return fn()
            except requests.exceptions.RequestException as exc:
                is_last = attempt == self.settings.MAX_RETRIES - 1
                if is_last or not self._should_retry(exc, idempotent):
                    raise
                delay = random.uniform(0, self.settings.RETRY_BACKOFF * (2**attempt))
                log.warning(f"Attempt {attempt + 1}/{self.settings.MAX_RETRIES} failed: {exc}; retrying in {delay:.2f}s")
                time.sleep(delay)
        raise RuntimeError("unreachable: retry loop exited without returning or raising")

    def _history_tag(self) -> str:
        """Scope tag derived from ``step_history``, identifying this invocation's upstream lineage.

        Set by the wurzel Executor (via a ContextVar) right before ``run()`` is called,
        encoding the chain of upstream steps/files that produced this invocation's
        input. It is stable across successive runs of the same pipeline (built only
        from step class names, never a run id or timestamp) but differs across
        distinct upstream sources - so if this step is fed by more than one source in
        a single run (multiple ``dependsOn``, or one upstream step sharding its output
        across files), each invocation gets a different tag. Used by both
        ``_generate_name`` and ``_list_existing`` so one invocation's create/update/
        prune decisions never consider a different invocation's documents.

        Falls back to "" (no extra scoping, matching behavior with no history) when
        unset - e.g. when the step is instantiated directly instead of run through
        the wurzel Executor.
        """
        history = step_history.get()
        if history is None:
            return ""
        tag = "-".join(history.get())
        return f"{tag}/" if tag else ""

    def _iter_documents(self, doc_type: str, parent_folder_id: str | None) -> Iterator[dict[str, Any]]:
        """Yield every document of ``doc_type`` scoped to ``parent_folder_id``, across all pages.

        Scoped to ``types=[doc_type]`` server-side, plus a defensive client-side check
        (`type` is the discriminator between text/url/file/folder documents - a leaked
        document of a different type must never be treated as one of ours). Shared by
        ``_list_existing`` (``doc_type="text"``) and ``_find_folder`` (``doc_type="folder"``).

        Raises StepFailed (rather than falling back to an empty/partial result) if a page
        can't be fetched even after retries: proceeding with an incomplete listing is what
        causes duplicates in the first place - a document on an unfetched page would look
        "new" and get created a second time.
        """
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": self.settings.PAGE_SIZE, "types": [doc_type]}
            if parent_folder_id:
                params["parent_folder_id"] = parent_folder_id
            if cursor:
                params["cursor"] = cursor
            try:
                result = self._request("GET", KNOWLEDGE_BASE_PATH, params=params)
            except requests.exceptions.RequestException as e:
                raise StepFailed(f"Could not list existing knowledge base documents: {self._format_error(e)}") from e
            for doc in result.get("documents", []):
                if doc.get("type") != doc_type:
                    continue
                yield doc
            cursor = result.get("next_cursor")
            if not result.get("has_more") or not cursor:
                break

    def _list_existing(self, parent_folder_id: str | None) -> dict[str, str]:
        """Return {name: document_id} for existing text documents in our namespace.

        NAME_PREFIX + history-tag filtering (see ``_history_tag``) is done client-side
        instead of via the API's ``search`` parameter: that is backed by search
        infrastructure which is not guaranteed to return every matching document
        (observed in practice missing a document that plainly existed), which would
        cause us to create a duplicate instead of updating it. Every text document is
        paginated through and matched by prefix here instead.

        The history tag additionally scopes this to the current invocation's own
        upstream lineage, so if this step is invoked more than once within a single
        run, one invocation's view of "existing" - and therefore its prune
        decisions - never includes documents belonging to a different invocation.

        ``parent_folder_id`` must be the same folder ``_create`` files new documents
        under (the resolved category folder when FOLDER_PER_SOURCE is enabled,
        otherwise PARENT_FOLDER_ID directly) - otherwise every previously-created
        document would look "new" on the next run and get duplicated instead of
        updated in place.

        If two documents share the same name - e.g. a duplicate left over from
        exactly that kind of missed match - the extra copy is deleted so
        duplicates self-heal instead of accumulating silently across runs.
        """
        scope = f"{self.settings.NAME_PREFIX}{self._history_tag()}"
        existing: dict[str, str] = {}
        for doc in self._iter_documents("text", parent_folder_id):
            name = doc["name"]
            if scope and not name.startswith(scope):
                continue
            if name in existing:
                log.warning(f"Duplicate document name {name!r}: keeping {existing[name]}, deleting {doc['id']}")
                try:
                    self._delete(doc["id"])
                except requests.exceptions.RequestException as e:
                    log.warning(f"Failed to delete duplicate {doc['id']} for {name!r}: {self._format_error(e)}")
                continue
            existing[name] = doc["id"]
        return existing

    def _find_folder(self, name: str, parent_folder_id: str | None) -> str | None:
        """Return the id of an existing folder named ``name`` directly under ``parent_folder_id``, or None.

        The ElevenLabs API enforces no uniqueness on folder names - creating a folder
        with a name/parent that already exists succeeds and produces a second, distinct
        folder rather than an error or the existing one. If more than one match turns up
        here (e.g. left over from a previous run that crashed after creating a folder but
        before caching its id), the lowest id is kept deterministically and a warning is
        logged. Unlike duplicate text documents, extras are never auto-deleted: a folder
        may hold real nested content, so deleting the "wrong" one risks losing it.
        """
        matches = {doc["id"] for doc in self._iter_documents("folder", parent_folder_id) if doc["name"] == name}
        if not matches:
            return None
        if len(matches) > 1:
            log.warning(f"Multiple folders named {name!r} under parent {parent_folder_id!r}: {sorted(matches)}")
        return sorted(matches)[0]

    def _create_folder(self, name: str, parent_folder_id: str | None) -> str:
        """POST /knowledge-base/folder - create a new folder, returns its id.

        Not retried on a read timeout: the server may already have created it, and
        since the API doesn't dedupe folder names (see ``_find_folder``), blindly
        retrying risks creating a second folder with the same name.
        """
        payload: dict[str, Any] = {"name": name}
        if parent_folder_id:
            payload["parent_folder_id"] = parent_folder_id
        result = self._request("POST", KNOWLEDGE_BASE_FOLDER_PATH, idempotent=False, json=payload)
        return result["id"]

    def _resolve_category_folder_id(self, category: str) -> str:
        """Get-or-create the subfolder for ``category``, cached for the life of this step instance.

        A single step instance's run() may be invoked many times within one execution -
        once per upstream file, per the class docstring - so every invocation for the same
        category would otherwise repeat the same folder lookup, and risk an unnecessary
        extra folder being created, since the API doesn't dedupe folder names itself.
        """
        cached = self._category_folder_cache.get(category)
        if cached is not None:
            return cached
        folder_id = self._find_folder(category, self.settings.PARENT_FOLDER_ID)
        if folder_id is None:
            folder_id = self._create_folder(category, self.settings.PARENT_FOLDER_ID)
            log.info(f"Created category folder {category!r}: {folder_id}")
        self._category_folder_cache[category] = folder_id
        return folder_id

    def _source_category(self) -> str | None:
        """The originating source step's name, derived from step_history, for FOLDER_PER_SOURCE.

        Reads the full flattened chain (``"-".join(history.get())``) rather than indexing
        ``history.get()[0]`` directly: once this invocation's history has round-tripped
        through disk (i.e. any step sits between the true source and this one), the wurzel
        Executor's on-disk filename encoding collapses everything upstream into a single
        compound entry - e.g. ``["SourceA-Splitter", "ElevenLabsKnowledgeBase"]`` instead of
        ``["SourceA", "Splitter", "ElevenLabsKnowledgeBase"]`` - so ``[0]`` would return
        "SourceA-Splitter", not the true origin "SourceA". Joining first and then splitting
        on the same separator recovers the original ordering losslessly regardless of that
        fragmentation (step names come from Python class names, which can never themselves
        contain "-", so splitting on it is unambiguous), and always yields the very first
        step in the lineage - the same source step ``_history_tag`` already treats the
        joined string as authoritative for.

        Falls back to None (no categorization for this invocation) when step_history is
        unset - e.g. when the step is instantiated directly instead of run through the
        wurzel Executor.
        """
        history = step_history.get()
        if history is None:
            return None
        chain = "-".join(history.get())
        return chain.split("-")[0] if chain else None

    def _generate_name(self, doc: MarkdownDataContract, idx: int) -> str:
        """Mirror the URL path as the document name so the same URL always maps to the same document.

        e.g. https://example.com/tmcz/baze/magenta-wi-fi -> tmcz/baze/magenta-wi-fi

        Prefixed with NAME_PREFIX and a history-derived scope tag (see
        ``_history_tag``), so distinct upstream sources feeding this step within
        one run never collide in the name-matching namespace used for
        update-in-place and pruning.
        """
        name = f"document_{idx:04d}"
        if doc.url:
            path = urlparse(doc.url).path.strip("/")
            if path:
                name = path
        return f"{self.settings.NAME_PREFIX}{self._history_tag()}{name}"

    def _create(self, name: str, content: str, parent_folder_id: str | None) -> str:
        """POST /knowledge-base/text - create a new text document, returns its id."""
        payload: dict[str, Any] = {"text": content, "name": name}
        if parent_folder_id:
            payload["parent_folder_id"] = parent_folder_id
        # Not retried on a read timeout: the server may already have created it,
        # and re-sending would create a duplicate.
        result = self._request("POST", f"{KNOWLEDGE_BASE_PATH}/text", idempotent=False, json=payload)
        return result["id"]

    def _update(self, document_id: str, content: str) -> None:
        """PATCH /knowledge-base/{id} - overwrite the content of an existing text document."""
        self._request("PATCH", f"{KNOWLEDGE_BASE_PATH}/{document_id}", json={"content": content})

    def _delete(self, document_id: str) -> None:
        """DELETE /knowledge-base/{id} - remove a document."""
        self._request(
            "DELETE",
            f"{KNOWLEDGE_BASE_PATH}/{document_id}",
            params={"force": str(self.settings.PRUNE_FORCE).lower()},
        )

    def _format_error(self, e: requests.exceptions.RequestException) -> str:
        """Format a request exception into a readable error message."""
        if hasattr(e, "response") and e.response is not None:
            try:
                detail = e.response.json().get("detail", str(e))
                return f"{e.response.status_code}: {detail}"
            except (ValueError, KeyError):
                return f"{e.response.status_code}: {e.response.text or str(e)}"
        return str(e)

    def _prune_stale(self, existing: dict[str, str], processed_names: set[str]) -> int:
        """Delete documents that are in the knowledge base but not in the input.

        Only ever considers documents returned by ``_list_existing`` - i.e. within
        our ``types=text`` + NAME_PREFIX + history-tag namespace - so it never
        touches documents created outside this step, nor documents belonging to a
        different invocation within the same run. Best-effort: per-document
        failures are logged, not raised. Returns the number of documents actually
        pruned.
        """
        stale = {name: doc_id for name, doc_id in existing.items() if name not in processed_names}
        if not stale:
            return 0
        log.info(f"Pruning {len(stale)} stale document(s) not in input: {sorted(stale)[:10]}{' ...' if len(stale) > 10 else ''}")
        pruned = 0
        for name, doc_id in stale.items():
            try:
                self._delete(doc_id)
                pruned += 1
            except requests.exceptions.RequestException as e:
                log.warning(f"Failed to prune {name}: {self._format_error(e)}")
        return pruned

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Push markdown documents to the ElevenLabs Knowledge Base and return them unchanged."""
        if not self.settings.PUSH_ENABLED:
            log.info("Push disabled, returning input data without pushing to ElevenLabs")
            return inpt

        if not inpt:
            log.warning("No documents to process")
            return inpt

        parent_folder_id = self.settings.PARENT_FOLDER_ID
        if self.settings.FOLDER_PER_SOURCE:
            category = self._source_category()
            if category:
                parent_folder_id = self._resolve_category_folder_id(category)
            else:
                log.warning("FOLDER_PER_SOURCE is enabled but no step_history is set; filing documents without a category folder")

        existing = self._list_existing(parent_folder_id)
        log.info(f"Processing {len(inpt)} documents for ElevenLabs Knowledge Base")

        success_count = 0
        failed_count = 0
        processed_names: set[str] = set()

        for idx, doc in enumerate(inpt):
            name = self._generate_name(doc, idx)
            processed_names.add(name)
            try:
                existing_id = existing.get(name)
                if existing_id:
                    self._update(existing_id, doc.md)
                    log.info(f"Updated: {name}")
                else:
                    existing[name] = self._create(name, doc.md, parent_folder_id)
                    log.info(f"Created: {name}")
                success_count += 1
            except requests.exceptions.RequestException as e:
                log.error(f"Failed to push {name}: {self._format_error(e)}")
                failed_count += 1

        pruned = 0
        if self.settings.PRUNE_STALE:
            if failed_count > 0:
                log.warning(f"Skipping prune: {failed_count} document(s) failed to push this run")
            else:
                pruned = self._prune_stale(existing, processed_names)

        log.info(f"Completed: {success_count} succeeded, {failed_count} failed, {pruned} pruned")

        if failed_count > 0 and success_count == 0:
            raise StepFailed(f"All {failed_count} documents failed to push to ElevenLabs")

        return inpt

    def finalize(self) -> None:
        """Cleanup after step execution."""
        if self._session is not None:
            self._session.close()
        super().finalize()
