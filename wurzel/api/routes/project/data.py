# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Pydantic models for the project route."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class Project(BaseModel):
    """A Wurzel project."""

    id: uuid.UUID
    name: str
    description: str | None = None
    created_by: str = Field(description="Supabase Auth user UUID of the project creator")
    created_at: datetime
    updated_at: datetime


class CreateProjectRequest(BaseModel):
    """Request body for ``POST /v1/projects``."""

    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class UpdateProjectRequest(BaseModel):
    """Request body for ``PUT /v1/projects/{id}``."""

    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = None


class PaginatedProjectResponse(BaseModel):
    """Paginated list of projects the caller is a member of."""

    items: list[Project]
    total: int
    offset: int
    limit: int
