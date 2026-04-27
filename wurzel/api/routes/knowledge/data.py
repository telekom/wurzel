# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Pydantic models for the knowledge route."""
# pylint: disable=duplicate-code

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeItem(BaseModel):
    """A single knowledge item stored in the backend."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    title: str
    content: str
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CreateKnowledgeRequest(BaseModel):
    """Request body for ``POST /v1/knowledge``."""

    title: str
    content: str
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateKnowledgeRequest(BaseModel):
    """Request body for ``PUT /v1/knowledge/{id}``."""

    title: str | None = None
    content: str | None = None
    source: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class PaginatedKnowledgeResponse(BaseModel):
    """Paginated list of knowledge items."""

    items: list[KnowledgeItem]
    total: int
    offset: int
    limit: int
