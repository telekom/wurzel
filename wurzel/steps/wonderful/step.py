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

    Documents are processed in two phases:
      Phase 1 (concurrent): upload or update each file's content
        New file:      POST /knowledgebases/{kb_id}/files  → PUT <presigned-url>
        Existing file: POST /storage/upload (multipart, file_id=<id>)
      Prune (optional, gated by PRUNE_STALE): before sync, delete files that are in the
        KB but not in the input so the KB mirrors the input. Skipped on any upload failure.
      Phase 2 (fire-and-forget): POST /kb/sync once to re-index the whole KB. This
        server op is slow and routinely exceeds the gateway timeout (~100s → HTTP 524);
        the server keeps indexing after the connection drops, so the trigger is
        fire-and-forget — a timeout/524 is logged, never raised.

    Upload HTTP calls are retried with full-jitter exponential back-off on transient
    errors (connection errors, timeouts, HTTP 429/5xx). File creation is not retried
    on read timeouts because it is not idempotent — a re-sent create after the server
    already processed it would produce a duplicate record. If a record is created but
    its content upload then fails, the orphan record is rolled back via DELETE. The
    sync trigger is not retried (fire-and-forget).

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
        WONDERFULRAGSTEP__BASE_URL:         Wonderful API base URL, e.g. https://<tenant>.api.sb.wonderful.ai (required when not SKIP)
        WONDERFULRAGSTEP__API_KEY:          API key (required when not SKIP)
        WONDERFULRAGSTEP__KNOWLEDGEBASE_ID: Knowledge base ID (required when not SKIP)
        WONDERFULRAGSTEP__TIMEOUT:          Request timeout in seconds (default: 120)
        WONDERFULRAGSTEP__SYNC_TIMEOUT:     Fire-and-forget sync trigger timeout in seconds (default: 30)
        WONDERFULRAGSTEP__MAX_WORKERS:      Concurrent upload workers in phase 1 (default: 10)
        WONDERFULRAGSTEP__PRUNE_STALE:      Delete KB files absent from input, mirroring it (default: false)
        WONDERFULRAGSTEP__MAX_RETRIES:      Max attempts per HTTP call (default: 3)
        WONDERFULRAGSTEP__RETRY_BACKOFF:    Base back-off seconds — 0.5s, 1s, 2s, ... (default: 0.5)
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

    def _trigger_sync(self, session: requests.Session) -> None:
        """POST /kb/sync — fire-and-forget trigger of whole-KB re-indexing.

        A single whole-KB sync is used rather than the per-file sync endpoint: each
        sync (per-file or whole-KB) does heavy work and is slow regardless, so one call
        is cheaper than one per file. The work is synchronous server-side and routinely
        exceeds the gateway timeout (~100s → HTTP 524) and the client read timeout. The
        server keeps indexing after the connection drops, so we only need to *trigger*
        it: a timeout or 524 is logged as "started", never raised. Other errors are
        logged but also do not fail the step (uploads are already persisted; re-running
        re-triggers sync).
        """
        url = f"{self.settings.BASE_URL}/api/v1/knowledgebases/{self._kb_id}/sync"
        try:
            response = session.post(url, timeout=self.settings.SYNC_TIMEOUT)
            if response.status_code in (502, 503, 504, 524):
                log.info(f"KB sync triggered (gateway {response.status_code}); indexing continues server-side")
            elif response.ok:
                log.info(f"KB sync triggered ({response.status_code})")
            else:
                log.warning(f"KB sync trigger returned {response.status_code}: {response.text[:200]}")
        except requests.exceptions.Timeout:
            log.info("KB sync triggered (client timeout); indexing continues server-side")
        except requests.exceptions.RequestException as e:
            log.warning(f"KB sync trigger could not be sent: {e}")

    def _delete_kb_files(self, session: requests.Session, file_ids: list[str]) -> None:
        """DELETE /kb/files — remove file records by id (batch endpoint, ids in the body)."""
        self._api_request(session, "DELETE", f"/knowledgebases/{self._kb_id}/files", {"file_ids": file_ids})

    def _delete_kb_file_safe(self, session: requests.Session, file_id: str, filename: str) -> None:
        """Best-effort rollback of a created-but-not-uploaded record. Never raises."""
        try:
            self._delete_kb_files(session, [file_id])
            log.info(f"Rolled back orphaned record for {filename}")
        except requests.exceptions.RequestException as e:
            log.warning(f"Could not roll back orphaned record {file_id} for {filename}: {e}")

    def _prune_one(self, file_id: str, filename: str) -> bool:
        """Delete a single stale file (own session per worker). Returns True on success.

        Not retried: the DELETE is slow, and a read timeout almost always means the server
        is still completing the delete — retrying only piles more load on the endpoint. So a
        read timeout is treated as "assume deleted"; other errors count as failures.
        """
        with self._build_session() as session:
            try:
                self._delete_kb_files(session, [file_id])
                return True
            except requests.exceptions.ReadTimeout:
                log.info(f"Prune of {filename} timed out (read); assuming the server completes it")
                return True
            except requests.exceptions.RequestException as e:
                log.warning(f"Failed to prune {filename} ({file_id}): {e}")
                return False

    def _prune_stale(self, existing: dict[str, str], keep_filenames: set[str]) -> int:
        """Delete files in the KB that are not in the input, so the KB mirrors the input.

        ``existing`` is the pre-upload {filename: file_id} snapshot, so this only removes
        files that were already in the KB and are absent from the input (KB − input) —
        never anything created this run. Reading the snapshot before uploading also avoids
        read-after-write lag.

        Deletes run concurrently, one file per worker — same pool model as the upload
        phase. A single batch DELETE with the whole id list does not scale (the endpoint
        404s on large lists); per-file calls do. Best-effort: per-file failures are logged,
        not raised. Returns the number of files actually pruned.
        """
        stale = {fid: name for name, fid in existing.items() if name not in keep_filenames}
        if not stale:
            return 0
        sample = sorted(stale.values())
        log.info(f"Pruning {len(stale)} stale file(s) not in input: {sample[:10]}{' ...' if len(sample) > 10 else ''}")
        with ThreadPoolExecutor(max_workers=self.settings.MAX_WORKERS) as executor:
            futures = [executor.submit(self._prune_one, fid, name) for fid, name in stale.items()]
            pruned = sum(1 for f in as_completed(futures) if f.result())
        if pruned < len(stale):
            log.warning(f"Pruned {pruned}/{len(stale)} stale file(s); {len(stale) - pruned} could not be deleted")
        return pruned

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

    @staticmethod
    def _should_retry(exc: requests.exceptions.RequestException, idempotent: bool) -> bool:
        """Whether ``exc`` is a transient error worth retrying.

        - Read timeout: the server may already have processed the request, so only
          retry idempotent calls — re-sending a create would duplicate the record.
        - Connect timeout / connection error: the request never completed at the
          server, so it is always safe to retry.
        - HTTP 429 / 5xx: transient server-side, safe to retry.
        - Other 4xx: permanent client error, never retry.
        """
        if isinstance(exc, requests.exceptions.ReadTimeout):
            return idempotent
        if isinstance(exc, (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError)):
            return True
        if isinstance(exc, requests.exceptions.Timeout):
            return idempotent
        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            return exc.response.status_code == 429 or exc.response.status_code >= 500
        return False

    def _with_retry(self, fn: Callable, *args, idempotent: bool = True, **kwargs) -> Any:
        """Call fn(*args, **kwargs) with full-jitter exponential back-off retry.

        Only transient request errors are retried (see ``_should_retry``); permanent
        errors propagate immediately. Pass ``idempotent=False`` for calls that must
        not be re-sent after a read timeout (e.g. record creation).
        """
        for attempt in range(self.settings.MAX_RETRIES):
            try:
                return fn(*args, **kwargs)
            except requests.exceptions.RequestException as exc:
                is_last = attempt == self.settings.MAX_RETRIES - 1
                if is_last or not self._should_retry(exc, idempotent):
                    raise
                delay = random.uniform(0, self.settings.RETRY_BACKOFF * (2**attempt))
                log.warning(f"Attempt {attempt + 1}/{self.settings.MAX_RETRIES} failed: {exc}; retrying in {delay:.2f}s")
                time.sleep(delay)
        raise RuntimeError("unreachable: retry loop exited without returning or raising")

    # ── Per-document upload (phase 1) ─────────────────────────────────────────

    def _upload_doc(self, idx: int, doc: MarkdownDataContract, existing: dict[str, str]) -> str | None:
        """Upload (or update) a single document. Returns file_id on success, None on failure.

        Each worker uses its own ``requests.Session`` because Session is not
        thread-safe for concurrent use. Sync is intentionally excluded here — a single
        whole-KB sync is triggered once in phase 2 after all uploads.
        """
        filename = self._generate_filename(doc, idx)
        existing_id = existing.get(filename)
        with self._build_session() as session:
            try:
                if existing_id:
                    self._with_retry(self._update_existing_file, session, existing_id, filename, doc.md.encode("utf-8"))
                    log.info(f"Updated: {filename}")
                    return existing_id
                # Create is not idempotent — don't re-send it on a read timeout.
                kb_file = self._with_retry(self._create_kb_file, session, filename, idempotent=False)
                file_id = kb_file["id"]
                try:
                    self._with_retry(self._upload_to_presigned_url, kb_file["url"], doc.md.encode("utf-8"))
                except (requests.exceptions.RequestException, KeyError):
                    # Record exists but has no content — roll it back to avoid an orphan.
                    self._delete_kb_file_safe(session, file_id, filename)
                    raise
                log.info(f"Uploaded: {filename}")
                return file_id
            except (requests.exceptions.RequestException, KeyError) as e:
                log.error(f"Failed to upload {filename}: {e}")
                return None

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Upload and sync markdown documents to the Wonderful RAG knowledge base."""
        if not inpt:
            log.warning("No documents to process")
            return []

        # Filter before the SKIP check so a dry run reflects the real upload set.
        # "neverejn" matches both Czech genders: neverejny (masc.) and neverejna (fem.)
        # .casefold() ensures case-insensitive matching (e.g. Neverejny, NEVEREJNY).
        to_upload = [doc for doc in inpt if "neverejn" not in doc.url.casefold()]
        excluded = len(inpt) - len(to_upload)
        if excluded:
            log.info(f"Excluded {excluded} document(s) with 'neverejn' in URL")

        if self.settings.SKIP:
            log.info(f"WonderfulRAGStep skipped — would upload {len(to_upload)} of {len(inpt)} document(s), no API calls")
            return inpt
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
            log.warning(f"Upload phase: {upload_failed} of {len(deduped)} document(s) failed")
        if not uploaded:
            raise StepFailed(f"All {len(deduped)} documents failed to upload")

        # Optional prune (before sync): make the KB mirror the input by deleting stale
        # files (KB − input). Gated behind PRUNE_STALE and skipped on any upload failure,
        # so we never delete real content to match an incomplete input.
        pruned = 0
        if self.settings.PRUNE_STALE:
            if upload_failed:
                log.warning(f"Skipping prune: {upload_failed} upload(s) failed this run")
            else:
                pruned = self._prune_stale(existing, set(unique.keys()))

        # Phase 2: trigger a single whole-KB re-index (fire-and-forget). The sync is a
        # slow server-side op that exceeds the gateway timeout; we trigger it and let the
        # server finish indexing in the background rather than blocking/failing on it.
        with self._build_session() as session:
            self._trigger_sync(session)

        log.info(f"Completed: {len(uploaded)} file(s) uploaded, {pruned} pruned, KB sync triggered, {upload_failed} upload failure(s)")

        # Passthrough preserves the original input length and order.
        return inpt
