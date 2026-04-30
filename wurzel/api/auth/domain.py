# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Domain logic for authentication and authorization.

Separates pure business logic (checking roles, validating permissions) from
infrastructure concerns (database lookups, JWT validation). This makes
permissions testable without external dependencies.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from wurzel.api.error_codes import ErrorCode
from wurzel.api.routes.member.data import ProjectRole


@dataclass
class UserClaims:
    """Parsed, validated JWT claims for the calling user."""

    sub: str
    """Supabase user UUID."""

    email: str
    """User e-mail address (from JWT claims)."""

    raw: dict | None = None
    """Full decoded payload for extension points (optional)."""


@dataclass
class ProjectAccess:
    """Carries both the resolved user and their project role for downstream use."""

    user: UserClaims
    role: ProjectRole
    project_id: uuid.UUID


class RoleResolver(Protocol):
    """Abstract interface for resolving a user's role in a project.

    This allows permissions logic to be tested without a database.
    Implementations (e.g., Supabase) provide the actual DB lookup.

    Usage::

        class TestRoleResolver:
            async def get_role(self, project_id: uuid.UUID, user_id: str) -> ProjectRole | None:
                return ProjectRole.ADMIN  # hardcode for testing

        access = await enforce_role(user, project_id, role_resolver, "admin", "member")
    """

    async def get_role(
        self,
        project_id: uuid.UUID,
        user_id: str,
    ) -> ProjectRole | None:
        """Return the user's role in the project, or None if not a member."""


async def enforce_role(
    user: UserClaims,
    project_id: uuid.UUID,
    role_resolver: RoleResolver,
    *allowed_roles: str,
) -> ProjectAccess:
    """Enforce that the user has one of the allowed roles in a project.

    Args:
        user: The authenticated user.
        project_id: The project to check access for.
        role_resolver: Implementation for looking up roles (e.g., database query).
        *allowed_roles: One or more role names that are permitted (e.g., "admin", "member").

    Returns:
        ProjectAccess with the user and resolved role.

    Raises:
        APIError: If the user is not a member (404) or lacks required role (403).
    """
    role = await role_resolver.get_role(project_id, user.sub)

    if role is None:
        raise ErrorCode.PROJECT_NOT_FOUND.error(detail=f"Project {project_id} does not exist or you are not a member.")

    if role.value not in allowed_roles:
        raise ErrorCode.INSUFFICIENT_PERMISSIONS.error(
            detail=f"This action requires one of the following roles: {', '.join(allowed_roles)}.",
            extensions={"project_id": str(project_id), "your_role": role.value},
        )

    return ProjectAccess(user=user, role=role, project_id=project_id)
