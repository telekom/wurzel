# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Wonderful RAG connector step for pushing markdown documents to a knowledge base."""

import random
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from logging import getLogger
from typing import Any
from urllib.parse import urlparse

import requests

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed
from wurzel.step import TypedStep

from .settings import WonderfulRAGSettings

log = getLogger(__name__)


class WonderfulRAGStep(TypedStep[WonderfulRAGSettings, list[MarkdownDataContract], list[MarkdownDataContract]]):
    """Wonderful RAG connector step.

    Each document runs fully concurrently (upload + sync in the same worker thread):
      New file:      POST /knowledgebases/{kb_id}/files  → PUT <presigned-url>  → POST /kb/files/sync
      Existing file: POST /storage/upload (multipart, file_id=<id>)             → POST /kb/files/sync

    Returns the input documents unchanged (passthrough sink) so the step can chain.
    Per-doc failures are logged but do not affect the output. If every document fails,
    raises ``StepFailed``.

    When ``WONDERFULRAGSTEP__SKIP=true`` the step is a no-op: it skips all API calls,
    requires no credentials, and returns its input unchanged. Used to avoid concurrency
    in lower DT environments where dev and staging share a cron schedule (both run at
    6:30 CET on Mon/Wed) and would otherwise hit Wonderful staging twice in the same
    minute.

    Environment Variables:
        WONDERFULRAGSTEP__SKIP:             When true, skip processing (default: false)
        WONDERFULRAGSTEP__BASE_URL:         Wonderful API base URL (required when not SKIP)
        WONDERFULRAGSTEP__API_KEY:          API key (required when not SKIP)
        WONDERFULRAGSTEP__KNOWLEDGEBASE_ID: Knowledge base ID (required when not SKIP)
        WONDERFULRAGSTEP__TIMEOUT:          Request timeout in seconds (default: 120)
        WONDERFULRAGSTEP__MAX_WORKERS:      Concurrent workers — each handles upload + sync (default: 10)
    """

    def __init__(self) -> None:
        super().__init__()
        self._kb_id: str = ""
        if self.settings.SKIP:
            log.info("WonderfulRAGStep skipped — running in no-op (passthrough) mode")
            return
        self._kb_id = self.settings.KNOWLEDGEBASE_ID

    # ── Session factory ───────────────────────────────────────────────────────

    def _build_session(self) -> requests.Session:
        """Build a fresh `requests.Session`. Used per worker — `requests.Session` is
        not safe for concurrent mutation across threads.
        """
        s = requests.Session()
        s.headers.update({"x-api-key": self.settings.API_KEY.get_secret_value()})  # pylint: disable=no-member
        return s

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _api_request(self, session: requests.Session, method: str, endpoint: str, payload: dict | None = None) -> dict[str, Any]:
        req_headers = {"Content-Type": "application/json", "Accept": "application/json"} if payload is not None else {}
        response = session.request(
            method,
            f"{self.settings.BASE_URL}/api/v1{endpoint}",
            json=payload,
            headers=req_headers,
            timeout=self.settings.TIMEOUT,
        )
        if not response.ok:
            log.debug(f"Response body ({response.status_code}): {response.text}")
        response.raise_for_status()
        return response.json()

    # ── KB file operations ────────────────────────────────────────────────────

    def _fetch_existing_filenames(self, session: requests.Session) -> dict[str, str]:
        """Returns {filename: file_id} for all enabled files currently in the KB."""
        try:
            result = self._api_request(session, "GET", f"/knowledgebases/{self._kb_id}/files")
            files = result.get("data", result)
            if isinstance(files, list):
                return {f["name"]: f["id"] for f in files}
        except requests.exceptions.RequestException as e:
            log.warning(f"Could not fetch existing KB files, duplicates may occur: {e}")
        return {}

    def _create_kb_file(self, session: requests.Session, filename: str) -> dict[str, Any]:
        """POST /kb/files — create a new file record, returns {id, url} where url is a presigned S3 URL."""
        result = self._api_request(
            session,
            "POST",
            f"/knowledgebases/{self._kb_id}/files",
            {"filename": filename, "contentType": "text/markdown"},
        )
        return result.get("data", result)

    def _upload_to_presigned_url(self, presigned_url: str, content: bytes) -> None:
        """PUT file content directly to S3 via a presigned URL."""
        # Bare requests.put: presigned URL must not carry the x-api-key header.
        response = requests.put(
            presigned_url,
            data=content,
            headers={"Content-Type": "text/markdown"},
            timeout=self.settings.TIMEOUT,
        )
        response.raise_for_status()

    def _update_existing_file(self, session: requests.Session, file_id: str, filename: str, content: bytes) -> None:
        """POST /storage/upload — overwrite S3 content of an existing file record in-place."""
        response = session.request(
            "POST",
            f"{self.settings.BASE_URL}/api/v1/storage/upload",
            files={"file": (filename, content, "text/markdown")},
            data={"file_id": file_id},
            timeout=self.settings.TIMEOUT,
        )
        if not response.ok:
            log.debug(f"Response body ({response.status_code}): {response.text}")
        response.raise_for_status()

    def _sync_kb_file(self, session: requests.Session, file_id: str) -> None:
        """POST /kb/files/sync — trigger provider re-indexing for a single file."""
        self._api_request(session, "POST", f"/knowledgebases/{self._kb_id}/files/sync", {"file_id": file_id})

    # ── Filename generation ───────────────────────────────────────────────────

    def _generate_filename(self, doc: MarkdownDataContract, idx: int) -> str:
        """Mirror the URL path as filename so the same URL always maps to the same file.

        e.g. https://example.com/tmcz/baze/magenta-wi-fi → tmcz/baze/magenta-wi-fi.md
        """
        if doc.url:
            path = urlparse(doc.url).path.strip("/")
            if path:
                return path if path.endswith(".md") else path + ".md"
        return f"document_{idx:04d}.md"

    # ── Retry helper ──────────────────────────────────────────────────────────

    def _with_retry(self, fn: Callable, *args, **kwargs) -> Any:
        """Call fn(*args, **kwargs) with exponential back-off retry on request errors.

        Only ``requests.exceptions.RequestException`` is retried; all other
        exceptions propagate immediately.
        """
        last_exc: Exception = RuntimeError("unreachable")
        for attempt in range(self.settings.MAX_RETRIES):
            try:
                return fn(*args, **kwargs)
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                if attempt < self.settings.MAX_RETRIES - 1:
                    delay = random.uniform(0, self.settings.RETRY_BACKOFF * (2**attempt))
                    log.warning(f"Attempt {attempt + 1}/{self.settings.MAX_RETRIES} failed: {exc}; retrying in {delay:.2f}s")
                    time.sleep(delay)
        raise last_exc

    # ── Per-document upload (phase 1) ─────────────────────────────────────────

    def _upload_doc(self, idx: int, doc: MarkdownDataContract, existing: dict[str, str]) -> str | None:
        """Upload (or update) a single document. Returns file_id on success, None on failure.

        Each worker uses its own ``requests.Session`` because Session is not
        thread-safe for concurrent use. Sync is intentionally excluded here and
        handled sequentially in phase 2 to avoid overloading the re-indexing endpoint.
        """
        filename = self._generate_filename(doc, idx)
        existing_id = existing.get(filename)
        with self._build_session() as session:
            try:
                if existing_id:
                    self._with_retry(self._update_existing_file, session, existing_id, filename, doc.md.encode("utf-8"))
                    log.info(f"Updated: {filename}")
                    return existing_id
                kb_file = self._with_retry(self._create_kb_file, session, filename)
                self._with_retry(self._upload_to_presigned_url, kb_file["url"], doc.md.encode("utf-8"))
                log.info(f"Uploaded: {filename}")
                return kb_file["id"]
            except (requests.exceptions.RequestException, KeyError) as e:
                log.error(f"Failed to upload {filename}: {e}")
                return None

    # ── Phase 2: sequential sync ──────────────────────────────────────────────

    def _sync_all(self, file_ids: list[str]) -> int:
        """Sync each file sequentially. Returns the number of failures."""
        failed = 0
        with self._build_session() as session:
            for file_id in file_ids:
                try:
                    self._with_retry(self._sync_kb_file, session, file_id)
                except requests.exceptions.RequestException as e:
                    log.error(f"Failed to sync file {file_id}: {e}")
                    failed += 1
        return failed

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Upload and sync markdown documents to the Wonderful RAG knowledge base."""
        if self.settings.SKIP:
            log.info(f"WonderfulRAGStep skipped — passing through {len(inpt)} documents unchanged")
            return inpt
        if not inpt:
            log.warning("No documents to process")
            return []

        # "neverejn" matches both Czech genders: neverejny (masc.) and neverejna (fem.)
        # .casefold() ensures case-insensitive matching (e.g. Neverejny, NEVEREJNY).
        to_upload = [doc for doc in inpt if "neverejn" not in doc.url.casefold()]
        excluded = len(inpt) - len(to_upload)
        if excluded:
            log.info(f"Excluded {excluded} document(s) with 'neverejn' in URL")
        if not to_upload:
            return inpt

        # Pre-dedup by generated filename so two input docs with the same KB
        # filename don't race in the worker pool and create duplicate KB records.
        # When two docs map to the same filename, the later occurrence wins.
        unique: dict[str, tuple[int, MarkdownDataContract]] = {}
        for idx, doc in enumerate(to_upload):
            unique[self._generate_filename(doc, idx)] = (idx, doc)
        deduped = list(unique.values())
        if len(deduped) < len(to_upload):
            log.info(f"Deduped input: {len(to_upload)} → {len(deduped)} unique filenames")

        log.info(f"Processing {len(deduped)} documents for Wonderful KB {self._kb_id}")
        with self._build_session() as session:
            existing = self._fetch_existing_filenames(session)

        # Phase 1: upload files concurrently — pure I/O, benefits from parallelism.
        with ThreadPoolExecutor(max_workers=self.settings.MAX_WORKERS) as executor:
            futures = [executor.submit(self._upload_doc, idx, doc, existing) for idx, doc in deduped]
            file_ids = [f.result() for f in as_completed(futures)]

        uploaded = [fid for fid in file_ids if fid is not None]
        upload_failed = len(deduped) - len(uploaded)
        if upload_failed:
            log.warning(f"Upload phase: {upload_failed} document(s) failed")

        # Phase 2: sync uploaded files sequentially — avoids hammering the
        # re-indexing endpoint with concurrent requests that cause timeouts.
        sync_failed = self._sync_all(uploaded)

        failed = upload_failed + sync_failed
        log.info(f"Completed: {len(deduped) - failed} succeeded, {failed} failed")

        if failed == len(deduped):
            raise StepFailed(f"All {failed} documents failed to process")

        # Passthrough preserves the original input length and order.
        return inpt
