# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Decagon Knowledge Base connector step for pushing markdown documents."""

from logging import getLogger
from typing import Any

import pandas as pd
import requests
from pandera.typing import DataFrame

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed
from wurzel.step import TypedStep

from .data import ChunkResultInfo, DecagonArticleResult
from .settings import DecagonSettings

log = getLogger(__name__)


class DecagonKnowledgeBaseStep(TypedStep[DecagonSettings, list[MarkdownDataContract], DataFrame[DecagonArticleResult]]):
    """Decagon Knowledge Base connector step.

    Takes MarkdownDataContract documents, chunks them via the Decagon API,
    and creates individual articles for each chunk.

    Environment Variables:
        DECAGONKBSTEP__API_URL: Base URL for the Decagon API
        DECAGONKBSTEP__API_KEY: API key for authentication (required)
        DECAGONKBSTEP__SOURCE: Source label for articles (default: "Wurzel")
        DECAGONKBSTEP__TIMEOUT: Request timeout in seconds (default: 120)
    """

    def __init__(self) -> None:
        super().__init__()
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

    def _build_result(self, doc, chunk: str, info: ChunkResultInfo) -> dict[str, Any]:
        """Build a result dict for a chunk."""
        return {
            "article_id": info.article_id,
            "url": doc.url or "",
            "content": chunk[:500] + "..." if len(chunk) > 500 else chunk,
            "source": self.settings.SOURCE,
            "tags": [t.strip() for t in doc.keywords.split(",") if t.strip()],
            "status": info.status,
            "error": info.error,
            "metadata": {
                **(doc.metadata or {}),
                "chunk_index": info.chunk_idx,
                "total_chunks": info.total,
            },
        }

    def _format_error(self, e: requests.exceptions.RequestException) -> str:
        """Format a request exception into a readable error message."""
        if hasattr(e, "response") and e.response is not None:
            try:
                detail = e.response.json().get("detail", str(e))
                return f"{e.response.status_code}: {detail}"
            except (ValueError, KeyError):
                return f"{e.response.status_code}: {e.response.text or str(e)}"
        return str(e)

    def run(self, inpt: list[MarkdownDataContract]) -> DataFrame[DecagonArticleResult]:
        """Create articles in Decagon Knowledge Base from markdown documents."""
        if not inpt:
            log.warning("No documents to process")
            return DataFrame[DecagonArticleResult](
                {
                    "article_id": pd.array([], dtype="Int64"),
                    "url": pd.array([], dtype="str"),
                    "content": pd.array([], dtype="str"),
                    "source": pd.array([], dtype="str"),
                    "tags": pd.array([], dtype="object"),
                    "status": pd.array([], dtype="str"),
                    "error": pd.array([], dtype="str"),
                    "metadata": pd.array([], dtype="object"),
                }
            )

        log.info(f"Processing {len(inpt)} documents for Decagon (source: {self.settings.SOURCE})")
        results = []

        for doc in inpt:
            # Chunk the document
            try:
                chunks = self._chunk_content(doc.md, self._extract_title(doc))
            except requests.exceptions.RequestException as e:
                log.error(f"Failed to chunk {doc.url}: {self._format_error(e)}")
                results.append(
                    self._build_result(
                        doc,
                        doc.md,
                        ChunkResultInfo(
                            0,
                            1,
                            None,
                            "failed",
                            f"Chunking failed: {self._format_error(e)}",
                        ),
                    )
                )
                continue

            # Create an article for each chunk
            for idx, chunk in enumerate(chunks):
                try:
                    resp = self._create_article(chunk, doc, idx, len(chunks))
                    results.append(
                        self._build_result(
                            doc,
                            chunk,
                            ChunkResultInfo(
                                idx,
                                len(chunks),
                                resp.get("article_id"),
                                "success",
                                None,
                            ),
                        )
                    )
                except requests.exceptions.RequestException as e:
                    log.error(f"Failed to create article for {doc.url} chunk {idx + 1}/{len(chunks)}: {self._format_error(e)}")
                    results.append(
                        self._build_result(
                            doc,
                            chunk,
                            ChunkResultInfo(idx, len(chunks), None, "failed", self._format_error(e)),
                        )
                    )

        success = sum(1 for r in results if r["status"] == "success")
        failed = len(results) - success
        log.info(f"Completed: {success} succeeded, {failed} failed")

        if results and failed == len(results):
            raise StepFailed(f"All {failed} chunks failed to create in Decagon")

        return DataFrame[DecagonArticleResult](results)

    def finalize(self) -> None:
        """Cleanup after step execution."""
        self._session.close()
        super().finalize()
