# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Project-scoped role enforcement dependencies.

Usage in a route handler::

    @router.put("/{project_id}")
    async def update_project(
        project_id: uuid.UUID,
        body: UpdateProjectRequest,
        user: CurrentUser,
        _role: RequireAdmin,          # ← enforces 'admin' role
    ) -> Project: ...
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Path
from fastapi import status as http_status

from wurzel.api.auth.jwt import CurrentUser, UserClaims
from wurzel.api.errors import APIError
from wurzel.api.routes.member.data import ProjectRole


@dataclass
class ProjectAccess:
    """Carries both the resolved user and their project role for downstream use."""

    user: UserClaims
    role: ProjectRole
    project_id: uuid.UUID


async def _resolve_project_role(
    project_id: uuid.UUID,
    user: UserClaims,
) -> ProjectRole | None:
    """Look up the caller's role in *project_id*.

    The actual DB lookup is delegated to the Supabase backend.  This function
    is called by the permission dependencies below; route handlers inject the
    backend dependency separately and use this only for role resolution.

    We keep a separate helper here (rather than inlining into routes) so that
    permission logic lives in one place and is testable in isolation.
    """
    # Import here to avoid circular dependency at module load time
    from wurzel.api.backends.supabase.client import get_project_role_from_db  # noqa: PLC0415

    return await get_project_role_from_db(project_id, user.sub)


def _require_project_role(*allowed: str):
    """Return a FastAPI dependency that enforces the caller has one of *allowed* roles."""

    async def _dep(
        project_id: uuid.UUID = Path(...),
        user: UserClaims = Depends(_verify_user),
    ) -> ProjectAccess:
        role = await _resolve_project_role(project_id, user)
        if role is None:
            raise APIError(
                status_code=http_status.HTTP_404_NOT_FOUND,
                title="Project not found",
                detail=f"Project {project_id} does not exist or you are not a member.",
            )
        if role.value not in allowed:
            raise APIError(
                status_code=http_status.HTTP_403_FORBIDDEN,
                title="Forbidden",
                detail=f"This action requires one of the following roles: {', '.join(allowed)}.",
                extensions={"project_id": str(project_id), "your_role": role.value},
            )
        return ProjectAccess(user=user, role=role, project_id=project_id)

    return _dep


async def _verify_user(user: CurrentUser) -> UserClaims:
    """Pass-through dependency that extracts the current user (used internally)."""
    return user


# ── Ready-to-use role dependencies ───────────────────────────────────────────

# Any project member (all four roles)
_ANY_ROLE = ("admin", "member", "secret_editor", "viewer")

RequireAdmin = Annotated[
    ProjectAccess,
    Depends(_require_project_role("admin")),
]
RequireMember = Annotated[
    ProjectAccess,
    Depends(_require_project_role("admin", "member")),
]
RequireSecretEditor = Annotated[
    ProjectAccess,
    Depends(_require_project_role("admin", "secret_editor")),
]
RequireAnyRole = Annotated[
    ProjectAccess,
    Depends(_require_project_role(*_ANY_ROLE)),
]


# ── Branch-specific write guard ───────────────────────────────────────────────


async def _require_branch_write_dep(
    project_id: uuid.UUID = Path(...),
    branch_name: str = Path(...),
    user: UserClaims = Depends(_verify_user),
) -> ProjectAccess:
    """Deny writes to `main` always; deny writes to protected branches for non-admins."""
    from wurzel.api.backends.supabase.client import get_branch_protection  # noqa: PLC0415

    role = await _resolve_project_role(project_id, user)
    if role is None:
        raise APIError(
            status_code=http_status.HTTP_404_NOT_FOUND,
            title="Project not found",
            detail=f"Project {project_id} does not exist or you are not a member.",
        )

    # main is always protected
    if branch_name == "main":
        raise APIError(
            status_code=http_status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail="The 'main' branch is protected and cannot be modified directly.",
        )

    is_protected = await get_branch_protection(project_id, branch_name)
    if is_protected and role != ProjectRole.ADMIN:
        raise APIError(
            status_code=http_status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail=f"Branch '{branch_name}' is protected. Only admins can write to it.",
        )

    # Member and above can write to unprotected branches
    if role not in (ProjectRole.ADMIN, ProjectRole.MEMBER):
        raise APIError(
            status_code=http_status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail="Writing to a branch requires at least the 'member' role.",
        )

    return ProjectAccess(user=user, role=role, project_id=project_id)


RequireBranchWrite = Annotated[ProjectAccess, Depends(_require_branch_write_dep)]
