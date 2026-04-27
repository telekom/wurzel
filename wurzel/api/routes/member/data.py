# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Pydantic models for the member route."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ProjectRole(str, Enum):
    """Roles a user can hold within a project.

    Permission summary
    ------------------
    - ``admin``         — full control: manage project, members, branches, and manifests
    - ``member``        — read + write to unprotected branches, submit manifests
    - ``secret_editor`` — read only + patch secret fields in branch manifests
    - ``viewer``        — read-only access to everything in the project
    """

    ADMIN = "admin"
    MEMBER = "member"
    SECRET_EDITOR = "secret_editor"  # pragma: allowlist secret
    VIEWER = "viewer"


class ProjectMember(BaseModel):
    """A project member record."""

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: str = Field(description="Supabase Auth user UUID (JWT 'sub' claim)")
    role: ProjectRole
    created_at: datetime


class AddMemberRequest(BaseModel):
    """Request body for ``POST /v1/projects/{id}/members``."""

    user_id: str = Field(description="Supabase Auth user UUID to add")
    role: ProjectRole = ProjectRole.VIEWER


class UpdateRoleRequest(BaseModel):
    """Request body for ``PUT /v1/projects/{id}/members/{user_id}``."""

    role: ProjectRole
