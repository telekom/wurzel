# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Abstract storage backend Protocol.

All concrete backends (Supabase, Postgres, in-memory, …) must implement this
interface so that route handlers can be written against a single stable API.
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from wurzel.api.dependencies import PaginationParams
from wurzel.api.routes.ingest.data import IngestJobResponse, IngestRequest, IngestResponse
from wurzel.api.routes.knowledge.data import (
    CreateKnowledgeRequest,
    KnowledgeItem,
    UpdateKnowledgeRequest,
)
from wurzel.api.routes.manifest.data import ManifestRecord
from wurzel.api.routes.search.data import SearchRequest, SearchResult


@runtime_checkable
class KnowledgeBackend(Protocol):
    """Storage backend interface for the Wurzel Knowledge API.

    Implementations must be safe for concurrent async access.
    """

    # ── Knowledge CRUD ───────────────────────────────────────────────────────

    async def create(self, request: CreateKnowledgeRequest) -> KnowledgeItem:
        """Persist a new knowledge item and return it with its generated ID."""
        ...

    async def get(self, item_id: uuid.UUID) -> KnowledgeItem | None:
        """Return a knowledge item by ID, or *None* if not found."""
        ...

    async def list(self, pagination: PaginationParams) -> tuple[list[KnowledgeItem], int]:
        """Return a page of knowledge items and the total count."""
        ...

    async def update(self, item_id: uuid.UUID, patch: UpdateKnowledgeRequest) -> KnowledgeItem | None:
        """Apply *patch* to an existing item and return the updated item."""
        ...

    async def delete(self, item_id: uuid.UUID) -> None:
        """Permanently delete a knowledge item."""
        ...

    # ── Search ────────────────────────────────────────────────────────────────

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """Execute a semantic / full-text search and return ranked results."""
        ...

    # ── Ingest jobs ───────────────────────────────────────────────────────────

    async def create_job(self, job_id: uuid.UUID, request: IngestRequest) -> IngestResponse:
        """Create a new ingest job record and return its initial state."""
        ...

    async def get_job(self, job_id: uuid.UUID) -> IngestJobResponse | None:
        """Return the current state of an ingest job, or *None* if not found."""
        ...

    # ── Manifest records ──────────────────────────────────────────────────────

    async def create_manifest(self, record: ManifestRecord) -> ManifestRecord:
        """Persist a new manifest record."""
        ...

    async def get_manifest(self, manifest_id: uuid.UUID) -> ManifestRecord | None:
        """Return a manifest record by ID, or *None* if not found."""
        ...

    async def list_manifests(self, pagination: PaginationParams) -> tuple[list[ManifestRecord], int]:
        """Return a page of manifest records and the total count."""
        ...

    async def update_manifest(self, record: ManifestRecord) -> ManifestRecord:
        """Persist an updated manifest record."""
        ...

    async def delete_manifest(self, manifest_id: uuid.UUID) -> None:
        """Permanently delete a manifest record."""
        ...
