# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Project member management routes.

Routes (all under /v1/projects/{project_id}/members)
------
``GET    /``              — list members (any member)
``POST   /``              — add member (admin)
``PUT    /{user_id}``     — change role (admin; last-admin guard)
``DELETE /{user_id}``     — remove member (admin; last-admin guard)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi import status as http_status

from wurzel.api.auth.permissions import RequireAdmin, RequireAnyRole
from wurzel.api.backends.supabase.client import (
    db_add_member,
    db_count_admins,
    db_get_member,
    db_list_members,
    db_remove_member,
    db_update_member_role,
)
from wurzel.api.errors import APIError
from wurzel.api.routes.member.data import (
    AddMemberRequest,
    ProjectMember,
    ProjectRole,
    UpdateRoleRequest,
)

router = APIRouter()


def _row_to_member(row: dict) -> ProjectMember:
    return ProjectMember(
        id=uuid.UUID(row["id"]),
        project_id=uuid.UUID(row["project_id"]),
        user_id=row["user_id"],
        role=ProjectRole(row["role"]),
        created_at=row["created_at"],
    )


@router.get("", response_model=list[ProjectMember])
async def list_members(
    project_id: uuid.UUID,
    _access: RequireAnyRole,
) -> list[ProjectMember]:
    """List all members of the project (any member)."""
    rows = await db_list_members(project_id)
    return [_row_to_member(r) for r in rows]


@router.post("", response_model=ProjectMember, status_code=http_status.HTTP_201_CREATED)
async def add_member(
    project_id: uuid.UUID,
    body: AddMemberRequest,
    _access: RequireAdmin,
) -> ProjectMember:
    """Add a user to the project (admin only)."""
    existing = await db_get_member(project_id, body.user_id)
    if existing is not None:
        raise APIError(
            status_code=http_status.HTTP_409_CONFLICT,
            title="Member already exists",
            detail=f"User '{body.user_id}' is already a member of this project.",
        )
    row = await db_add_member(project_id, body.user_id, body.role.value)
    return _row_to_member(row)


@router.put("/{user_id}", response_model=ProjectMember)
async def update_role(
    project_id: uuid.UUID,
    user_id: str,
    body: UpdateRoleRequest,
    _access: RequireAdmin,
) -> ProjectMember:
    """Change a member's role (admin only).

    Last-admin guard: cannot demote the final admin.
    """
    existing = await db_get_member(project_id, user_id)
    if existing is None:
        raise APIError(
            status_code=http_status.HTTP_404_NOT_FOUND,
            title="Member not found",
            detail=f"User '{user_id}' is not a member of this project.",
        )

    # Last-admin guard
    if existing["role"] == "admin" and body.role != ProjectRole.ADMIN:
        admin_count = await db_count_admins(project_id)
        if admin_count <= 1:
            raise APIError(
                status_code=http_status.HTTP_409_CONFLICT,
                title="Cannot remove last admin",
                detail="At least one admin must remain in the project.",
            )

    row = await db_update_member_role(project_id, user_id, body.role.value)
    if row is None:
        raise APIError(
            status_code=http_status.HTTP_404_NOT_FOUND,
            title="Member not found",
            detail=f"User '{user_id}' is not a member of this project.",
        )
    return _row_to_member(row)


@router.delete("/{user_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def remove_member(
    project_id: uuid.UUID,
    user_id: str,
    _access: RequireAdmin,
) -> None:
    """Remove a member from the project (admin only).

    Last-admin guard: cannot remove the final admin.
    """
    existing = await db_get_member(project_id, user_id)
    if existing is None:
        raise APIError(
            status_code=http_status.HTTP_404_NOT_FOUND,
            title="Member not found",
            detail=f"User '{user_id}' is not a member of this project.",
        )

    if existing["role"] == "admin":
        admin_count = await db_count_admins(project_id)
        if admin_count <= 1:
            raise APIError(
                status_code=http_status.HTTP_409_CONFLICT,
                title="Cannot remove last admin",
                detail="At least one admin must remain in the project.",
            )

    await db_remove_member(project_id, user_id)
