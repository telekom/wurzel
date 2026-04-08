# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StartPipelineRequest(BaseModel):
    config_revision_id: str = Field(..., min_length=1)


class StartPipelineResponse(BaseModel):
    pipeline_run_id: str
    temporal_workflow_id: str


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=500)
    filters: dict[str, Any] | None = None


class SearchResultItem(BaseModel):
    """Placeholder for future vector search results."""

    id: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    results: list[SearchResultItem] = Field(default_factory=list)


class IsAliveResponse(BaseModel):
    status: str = "ok"


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    pipeline_run_id: str
    temporal_status: str
    db_status: str
