# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Wonderful RAG connector step for pushing markdown documents to a knowledge base."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from logging import getLogger
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests
from pandera.typing import DataFrame

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed
from wurzel.step import TypedStep

from .data import FileUploadInfo, WonderfulRAGResult
from .settings import WonderfulRAGSettings

log = getLogger(__name__)


class WonderfulRAGStep(TypedStep[WonderfulRAGSettings, list[MarkdownDataContract], DataFrame[WonderfulRAGResult]]):
    """Wonderful RAG connector step.

    Each document runs fully concurrently (upload + sync in the same worker thread):
      New file:      POST /knowledgebases/{kb_id}/files  → PUT <presigned-url>  → POST /kb/files/sync
      Existing file: POST /storage/upload (multipart, file_id=<id>)             → POST /kb/files/sync

    Environment Variables:
        WONDERFULRAGSTEP__BASE_URL:         Wonderful API base URL (required)
        WONDERFULRAGSTEP__API_KEY:          API key (required)
        WONDERFULRAGSTEP__KNOWLEDGEBASE_ID: Knowledge base ID (required)
        WONDERFULRAGSTEP__TIMEOUT:          Request timeout in seconds (default: 120)
        WONDERFULRAGSTEP__MAX_WORKERS:      Concurrent workers — each handles upload + sync (default: 10)
    """

    def __init__(self) -> None:
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update({"x-api-key": self.settings.API_KEY.get_secret_value()})
        self._kb_id: str = self.settings.KNOWLEDGEBASE_ID

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _api_request(self, method: str, endpoint: str, payload: dict | None = None) -> dict[str, Any]:
        req_headers = {"Content-Type": "application/json", "Accept": "application/json"} if payload is not None else {}
        response = self._session.request(
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

    def _fetch_existing_filenames(self) -> dict[str, str]:
        """Returns {filename: file_id} for all enabled files currently in the KB."""
        try:
            result = self._api_request("GET", f"/knowledgebases/{self._kb_id}/files")
            files = result.get("data", result)
            if isinstance(files, list):
                return {f["name"]: f["id"] for f in files}
        except requests.exceptions.RequestException as e:
            log.warning(f"Could not fetch existing KB files, duplicates may occur: {e}")
        return {}

    def _create_kb_file(self, filename: str) -> dict[str, Any]:
        """POST /kb/files — create a new file record, returns {id, url} where url is a presigned S3 URL."""
        result = self._api_request(
            "POST",
            f"/knowledgebases/{self._kb_id}/files",
            {"filename": filename, "contentType": "text/markdown"},
        )
        return result.get("data", result)

    def _upload_to_presigned_url(self, presigned_url: str, content: bytes) -> None:
        """PUT file content directly to S3 via a presigned URL."""
        response = requests.put(
            presigned_url,
            data=content,
            headers={"Content-Type": "text/markdown"},
            timeout=self.settings.TIMEOUT,
        )
        response.raise_for_status()

    def _update_existing_file(self, file_id: str, filename: str, content: bytes) -> None:
        """POST /storage/upload — overwrite S3 content of an existing file record in-place."""
        response = self._session.request(
            "POST",
            f"{self.settings.BASE_URL}/api/v1/storage/upload",
            files={"file": (filename, content, "text/markdown")},
            data={"file_id": file_id},
            timeout=self.settings.TIMEOUT,
        )
        if not response.ok:
            log.debug(f"Response body ({response.status_code}): {response.text}")
        response.raise_for_status()

    def _sync_kb_file(self, file_id: str) -> None:
        """POST /kb/files/sync — trigger provider re-indexing for a single file."""
        self._api_request("POST", f"/knowledgebases/{self._kb_id}/files/sync", {"file_id": file_id})

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

    # ── Result builder ────────────────────────────────────────────────────────

    def _format_error(self, e: requests.exceptions.RequestException) -> str:
        if hasattr(e, "response") and e.response is not None:
            try:
                detail = e.response.json().get("detail", str(e))
                return f"{e.response.status_code}: {detail}"
            except (ValueError, KeyError):
                return f"{e.response.status_code}: {e.response.text or str(e)}"
        return str(e)

    def _build_result(self, doc: MarkdownDataContract, filename: str, info: FileUploadInfo) -> dict[str, Any]:
        content = doc.md
        return {
            "file_id": info.file_id,
            "url": doc.url or "",
            "filename": filename,
            "content": content[:500] + "..." if len(content) > 500 else content,
            "status": info.status,
            "error": info.error,
        }

    # ── Per-document: upload + sync in one worker ─────────────────────────────

    def _process_doc(self, idx: int, doc: MarkdownDataContract, existing: dict[str, str]) -> dict[str, Any]:
        """Upload (or update) a single document and sync it. Runs fully in one worker thread."""
        filename = self._generate_filename(doc, idx)
        existing_id = existing.get(filename)
        try:
            if existing_id:
                self._update_existing_file(existing_id, filename, doc.md.encode("utf-8"))
                file_id = existing_id
                log.info(f"Updating: {filename}")
            else:
                kb_file = self._create_kb_file(filename)
                self._upload_to_presigned_url(kb_file["url"], doc.md.encode("utf-8"))
                file_id = kb_file["id"]
                log.info(f"Uploading: {filename}")

            self._sync_kb_file(file_id)
            return self._build_result(doc, filename, FileUploadInfo(file_id, "success", None))

        except (requests.exceptions.RequestException, KeyError) as e:
            error_msg = self._format_error(e) if isinstance(e, requests.exceptions.RequestException) else str(e)
            log.error(f"Failed to process {filename}: {error_msg}")
            return self._build_result(doc, filename, FileUploadInfo(None, "failed", error_msg))

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(self, inpt: list[MarkdownDataContract]) -> DataFrame[WonderfulRAGResult]:
        """Upload and sync markdown documents to the Wonderful RAG knowledge base."""
        if not inpt:
            log.warning("No documents to process")
            return DataFrame[WonderfulRAGResult](
                {col: pd.array([], dtype="str") for col in ["file_id", "url", "filename", "content", "status", "error"]}
            )

        log.info(f"Uploading {len(inpt)} documents to Wonderful KB {self._kb_id}")
        existing = self._fetch_existing_filenames()

        with ThreadPoolExecutor(max_workers=self.settings.MAX_WORKERS) as executor:
            futures = {executor.submit(self._process_doc, idx, doc, existing): idx for idx, doc in enumerate(inpt)}
            results: list[dict[str, Any]] = [None] * len(inpt)  # type: ignore[list-item]
            for future in as_completed(futures):
                results[futures[future]] = future.result()

        success = sum(1 for r in results if r["status"] == "success")
        failed = len(results) - success
        log.info(f"Completed: {success} succeeded, {failed} failed")

        if failed == len(results):
            raise StepFailed(f"All {failed} documents failed to process")

        return DataFrame[WonderfulRAGResult](results)

    def finalize(self) -> None:
        self._session.close()
        super().finalize()
