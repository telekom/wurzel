# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Decagon Knowledge Base connector step for pushing markdown documents."""

from logging import getLogger
from typing import Any

import requests

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed
from wurzel.step import TypedStep

from .settings import DecagonSettings

log = getLogger(__name__)


class DecagonKnowledgeBaseStep(TypedStep[DecagonSettings, list[MarkdownDataContract], list[MarkdownDataContract]]):
    """Decagon Knowledge Base connector step.

    Takes MarkdownDataContract documents, chunks them via the Decagon API,
    creates individual articles for each chunk, and returns the original
    input documents unchanged.

    When PUSH_ENABLED is False the step returns the input data immediately
    without making any API calls.

    Environment Variables:
        DECAGONKBSTEP__API_URL: Base URL for the Decagon API
        DECAGONKBSTEP__API_KEY: API key for authentication (required when PUSH_ENABLED is True)
        DECAGONKBSTEP__SOURCE: Source label for articles (default: "Wurzel")
        DECAGONKBSTEP__TIMEOUT: Request timeout in seconds (default: 120)
        DECAGONKBSTEP__PUSH_ENABLED: Whether to push to Decagon (default: True)
    """

    def __init__(self) -> None:
        super().__init__()
        self._session: requests.Session | None = None
        if self.settings.PUSH_ENABLED:
            self._session = requests.Session()
            self._session.headers.update(
                {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.settings.API_KEY.get_secret_value()}",
                }
            )

    def _post(self, endpoint: str, payload: dict) -> dict[str, Any]:
        """Make a POST request to the Decagon API."""
        response = self._session.post(
            f"{self.settings.API_URL}{endpoint}",
            json=payload,
            timeout=self.settings.TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def _chunk_content(self, content: str, title: str) -> list[str]:
        """Chunk content via /article/chunks endpoint."""
        result = self._post(
            "/article/chunks",
            {"title": title, "content": content, "is_html": False},
        )
        return result.get("chunks") or [content]

    def _create_article(self, chunk: str, doc: MarkdownDataContract, chunk_idx: int, total: int) -> dict[str, Any]:
        """Create a single article from a chunk."""
        tags = [t.strip() for t in doc.keywords.split(",") if t.strip()]
        metadata = {
            **(doc.metadata or {}),
            "chunk_index": chunk_idx,
            "total_chunks": total,
            "original_url": doc.url,
        }

        return self._post(
            "/article/new",
            {
                "content": chunk,
                "source": self.settings.SOURCE,
                "tags": tags,
                "source_url": doc.url,
                "article_metadata": metadata,
            },
        )

    def _extract_title(self, doc: MarkdownDataContract) -> str:
        """Extract title from metadata, heading, URL, or content."""
        if doc.metadata and doc.metadata.get("title"):
            return str(doc.metadata["title"])

        for line in doc.md.split("\n"):
            if line.strip().startswith("# "):
                return line.strip()[2:].strip()

        if doc.url:
            filename = doc.url.split("/")[-1].removesuffix(".md")
            if filename:
                return filename.replace("-", " ").replace("_", " ").title()

        return doc.md.split("\n")[0].strip()[:100] or "Untitled"

    def _format_error(self, e: requests.exceptions.RequestException) -> str:
        """Format a request exception into a readable error message."""
        if hasattr(e, "response") and e.response is not None:
            try:
                detail = e.response.json().get("detail", str(e))
                return f"{e.response.status_code}: {detail}"
            except (ValueError, KeyError):
                return f"{e.response.status_code}: {e.response.text or str(e)}"
        return str(e)

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Push markdown documents to Decagon Knowledge Base and return them unchanged."""
        if not self.settings.PUSH_ENABLED:
            log.info("Push disabled, returning input data without pushing to Decagon")
            return inpt

        if not inpt:
            log.warning("No documents to process")
            return inpt

        log.info(f"Processing {len(inpt)} documents for Decagon (source: {self.settings.SOURCE})")
        success_count = 0
        failed_count = 0

        for doc in inpt:
            try:
                chunks = self._chunk_content(doc.md, self._extract_title(doc))
            except requests.exceptions.RequestException as e:
                log.error(f"Failed to chunk {doc.url}: {self._format_error(e)}")
                failed_count += 1
                continue

            for idx, chunk in enumerate(chunks):
                try:
                    self._create_article(chunk, doc, idx, len(chunks))
                    success_count += 1
                except requests.exceptions.RequestException as e:
                    log.error(f"Failed to create article for {doc.url} chunk {idx + 1}/{len(chunks)}: {self._format_error(e)}")
                    failed_count += 1

        log.info(f"Completed: {success_count} succeeded, {failed_count} failed")

        if failed_count > 0 and success_count == 0:
            raise StepFailed(f"All {failed_count} chunks failed to create in Decagon")

        return inpt

    def finalize(self) -> None:
        """Cleanup after step execution."""
        if self._session is not None:
            self._session.close()
        super().finalize()
