# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Pydantic models for the search route."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class SearchFilter(BaseModel):
    """Optional filters to narrow search results."""

    tags: list[str] = Field(default_factory=list, description="Restrict to items with all these tags")
    source: str | None = Field(None, description="Restrict to a specific source identifier")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Key/value metadata filters")


class SearchRequest(BaseModel):
    """Request body for ``POST /v1/search``."""

    query: str = Field(..., min_length=1, description="Natural-language or keyword query")
    limit: int = Field(10, gt=0, le=100, description="Maximum results to return")
    filters: SearchFilter = Field(default_factory=SearchFilter)


class SearchResult(BaseModel):
    """A single search hit."""

    id: uuid.UUID
    title: str
    content_snippet: str
    score: float = Field(ge=0.0, le=1.0, description="Relevance score in [0, 1]")
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Response envelope for ``POST /v1/search``."""

    query: str
    results: list[SearchResult]
    total: int
