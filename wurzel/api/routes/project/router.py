# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Project CRUD routes.

Routes
------
``POST   /v1/projects``           — create project (auto-creates main branch + admin member)
``GET    /v1/projects``           — list projects the caller is a member of
``GET    /v1/projects/{id}``      — get project
``PUT    /v1/projects/{id}``      — update project metadata (admin)
``DELETE /v1/projects/{id}``      — delete project (admin)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi import status as http_status

from wurzel.api.auth.jwt import CurrentUser
from wurzel.api.auth.permissions import RequireAdmin, RequireAnyRole
from wurzel.api.backends.supabase.client import (
    db_add_member,
    db_create_branch,
    db_create_project,
    db_delete_project,
    db_get_project,
    db_list_projects_for_user,
    db_update_project,
)
from wurzel.api.dependencies import Pagination
from wurzel.api.errors import APIError
from wurzel.api.routes.project.data import (
    CreateProjectRequest,
    PaginatedProjectResponse,
    Project,
    UpdateProjectRequest,
)

router = APIRouter()


def _row_to_project(row: dict) -> Project:
    return Project(
        id=uuid.UUID(row["id"]),
        name=row["name"],
        description=row.get("description"),
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.post("", response_model=Project, status_code=http_status.HTTP_201_CREATED)
async def create_project(
    body: CreateProjectRequest,
    user: CurrentUser,
) -> Project:
    """Create a new project.

    Atomically:
    1. Creates the project row
    2. Creates the ``main`` branch (protected, default)
    3. Adds the creator as ``admin`` member
    """
    row = await db_create_project(body.name, body.description, user.sub)
    project_id = uuid.UUID(row["id"])

    # Create the main branch (always protected)
    await db_create_branch(
        project_id,
        "main",
        is_protected=True,
        is_default=True,
    )

    # Add creator as admin
    await db_add_member(project_id, user.sub, "admin")

    return _row_to_project(row)


@router.get("", response_model=PaginatedProjectResponse)
async def list_projects(
    user: CurrentUser,
    pagination: Pagination,
) -> PaginatedProjectResponse:
    """List all projects the calling user is a member of."""
    rows, total = await db_list_projects_for_user(user.sub, pagination.offset, pagination.limit)
    return PaginatedProjectResponse(
        items=[_row_to_project(r) for r in rows],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: uuid.UUID,
    _access: RequireAnyRole,
) -> Project:
    """Return a project by ID (any member)."""
    row = await db_get_project(project_id)
    if row is None:
        raise APIError(
            status_code=http_status.HTTP_404_NOT_FOUND,
            title="Project not found",
            detail=f"No project with id={project_id}",
        )
    return _row_to_project(row)


@router.put("/{project_id}", response_model=Project)
async def update_project(
    project_id: uuid.UUID,
    body: UpdateProjectRequest,
    _access: RequireAdmin,
) -> Project:
    """Update project metadata (admin only)."""
    fields = body.model_dump(exclude_none=True)
    if not fields:
        row = await db_get_project(project_id)
    else:
        row = await db_update_project(project_id, fields)
    if row is None:
        raise APIError(
            status_code=http_status.HTTP_404_NOT_FOUND,
            title="Project not found",
            detail=f"No project with id={project_id}",
        )
    return _row_to_project(row)


@router.delete("/{project_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    _access: RequireAdmin,
) -> None:
    """Delete a project and all its branches/manifests (admin only)."""
    row = await db_get_project(project_id)
    if row is None:
        raise APIError(
            status_code=http_status.HTTP_404_NOT_FOUND,
            title="Project not found",
            detail=f"No project with id={project_id}",
        )
    await db_delete_project(project_id)
