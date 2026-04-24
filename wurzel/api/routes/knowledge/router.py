# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Knowledge CRUD routes.

Routes
------
``POST   /v1/knowledge``        — create a knowledge item
``GET    /v1/knowledge``        — list (paginated)
``GET    /v1/knowledge/{id}``   — retrieve by ID
``PUT    /v1/knowledge/{id}``   — update
``DELETE /v1/knowledge/{id}``   — delete
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi import status as http_status

from wurzel.api.dependencies import Pagination, RequireAPIKey
from wurzel.api.errors import APIError
from wurzel.api.routes.knowledge.data import (
    CreateKnowledgeRequest,
    KnowledgeItem,
    PaginatedKnowledgeResponse,
    UpdateKnowledgeRequest,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Dependency injection point for the storage backend.
# Replace _get_backend() with a real FastAPI dependency once the backend is
# wired up (see wurzel/api/backends/).
# ---------------------------------------------------------------------------


def _get_backend():  # type: ignore[return]
    raise APIError(
        status_code=http_status.HTTP_501_NOT_IMPLEMENTED,
        title="Not Implemented",
        detail="No storage backend is configured. Wire up wurzel.api.backends.supabase.",
    )


@router.post("", response_model=KnowledgeItem, status_code=http_status.HTTP_201_CREATED)
async def create_knowledge(
    body: CreateKnowledgeRequest,
    _auth: RequireAPIKey,
    backend=Depends(_get_backend),
) -> KnowledgeItem:
    """Create and persist a new knowledge item."""
    return await backend.create(body)


@router.get("", response_model=PaginatedKnowledgeResponse)
async def list_knowledge(
    _auth: RequireAPIKey,
    pagination: Pagination,
    backend=Depends(_get_backend),
) -> PaginatedKnowledgeResponse:
    """Return a paginated list of knowledge items."""
    items, total = await backend.list(pagination)
    return PaginatedKnowledgeResponse(
        items=items,
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{item_id}", response_model=KnowledgeItem)
async def get_knowledge(
    item_id: uuid.UUID,
    _auth: RequireAPIKey,
    backend=Depends(_get_backend),
) -> KnowledgeItem:
    """Retrieve a single knowledge item by its UUID."""
    item = await backend.get(item_id)
    if item is None:
        raise APIError(
            status_code=http_status.HTTP_404_NOT_FOUND,
            title="Knowledge item not found",
            detail=f"No item with id={item_id}",
        )
    return item


@router.put("/{item_id}", response_model=KnowledgeItem)
async def update_knowledge(
    item_id: uuid.UUID,
    body: UpdateKnowledgeRequest,
    _auth: RequireAPIKey,
    backend=Depends(_get_backend),
) -> KnowledgeItem:
    """Update an existing knowledge item."""
    item = await backend.update(item_id, body)
    if item is None:
        raise APIError(
            status_code=http_status.HTTP_404_NOT_FOUND,
            title="Knowledge item not found",
            detail=f"No item with id={item_id}",
        )
    return item


@router.delete("/{item_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_knowledge(
    item_id: uuid.UUID,
    _auth: RequireAPIKey,
    backend=Depends(_get_backend),
) -> None:
    """Delete a knowledge item permanently."""
    await backend.delete(item_id)
