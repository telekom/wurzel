# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Supabase async client and all DB helpers for the project/member/branch domain.

Install the optional dependency::

    pip install wurzel[supabase]
"""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache
from typing import Any

from wurzel.api.backends.supabase.settings import SupabaseSettings

logger = logging.getLogger(__name__)


# ── Settings singleton ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _get_settings() -> SupabaseSettings:
    return SupabaseSettings()


# ── Async client singleton ────────────────────────────────────────────────────

_async_client: Any = None  # pylint: disable=invalid-name


async def _get_async_client():
    """Return (or lazily create) the module-level async Supabase client."""
    global _async_client  # noqa: PLW0603  # pylint: disable=global-statement
    if _async_client is None:
        try:
            from supabase import acreate_client  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        except ImportError as exc:
            raise ImportError("supabase is not installed. Run: pip install wurzel[supabase]") from exc

        settings = _get_settings()
        _async_client = await acreate_client(
            settings.URL,
            settings.SERVICE_KEY.get_secret_value(),  # pylint: disable=no-member
        )
        logger.info("Async Supabase client created for %s", settings.URL)
    return _async_client


async def get_db():
    """FastAPI dependency: yield the async Supabase client."""
    return await _get_async_client()


# ── Role resolution (used by permissions.py) ─────────────────────────────────


async def get_project_role_from_db(
    project_id: uuid.UUID,
    user_id: str,
):
    """Return the ProjectRole for user_id in project_id, or None if not a member."""
    from wurzel.api.routes.member.data import ProjectRole  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    db = await _get_async_client()
    result = (
        await db.table("project_members").select("role").eq("project_id", str(project_id)).eq("user_id", user_id).maybe_single().execute()
    )
    if result is None or result.data is None:
        return None
    try:
        return ProjectRole(result.data["role"])
    except ValueError:
        return None


async def get_branch_protection(project_id: uuid.UUID, branch_name: str) -> bool:
    """Return True if the named branch is protected."""
    db = await _get_async_client()
    result = (
        await db.table("branches").select("is_protected").eq("project_id", str(project_id)).eq("name", branch_name).maybe_single().execute()
    )
    if result is None or result.data is None:
        return False
    return bool(result.data.get("is_protected", False))


# ── Project CRUD ──────────────────────────────────────────────────────────────


async def db_create_project(name: str, description: str | None, created_by: str) -> dict:
    """Insert a new project and return the created row."""
    db = await _get_async_client()
    result = (
        await db.table("projects")
        .insert(
            {
                "name": name,
                "description": description,
                "created_by": created_by,
            }
        )
        .execute()
    )
    return result.data[0]


async def db_get_project(project_id: uuid.UUID) -> dict | None:
    """Return the project row for *project_id*, or ``None`` if not found."""
    db = await _get_async_client()
    result = await db.table("projects").select("*").eq("id", str(project_id)).maybe_single().execute()
    return result.data if result is not None else None


async def db_list_projects_for_user(user_id: str, offset: int, limit: int) -> tuple[list[dict], int]:
    """Return a paginated list of projects the user belongs to, plus total count."""
    db = await _get_async_client()
    member_result = await db.table("project_members").select("project_id").eq("user_id", user_id).execute()
    project_ids = [row["project_id"] for row in (member_result.data or [])]
    if not project_ids:
        return [], 0

    result = await db.table("projects").select("*", count="exact").in_("id", project_ids).range(offset, offset + limit - 1).execute()
    return result.data or [], result.count or 0


async def db_update_project(project_id: uuid.UUID, fields: dict) -> dict | None:
    """Update *fields* on the project and return the updated row, or ``None`` if not found."""
    db = await _get_async_client()
    result = await db.table("projects").update(fields).eq("id", str(project_id)).execute()
    return result.data[0] if result.data else None


async def db_delete_project(project_id: uuid.UUID) -> None:
    """Delete the project row for *project_id*."""
    db = await _get_async_client()
    await db.table("projects").delete().eq("id", str(project_id)).execute()


# ── Member CRUD ───────────────────────────────────────────────────────────────


async def db_list_members(project_id: uuid.UUID) -> list[dict]:
    """Return all member rows for *project_id*."""
    db = await _get_async_client()
    result = await db.table("project_members").select("*").eq("project_id", str(project_id)).execute()
    return result.data or []


async def db_get_member(project_id: uuid.UUID, user_id: str) -> dict | None:
    """Return the member row for *user_id* in *project_id*, or ``None`` if not a member."""
    db = await _get_async_client()
    result = await db.table("project_members").select("*").eq("project_id", str(project_id)).eq("user_id", user_id).maybe_single().execute()
    return result.data if result is not None else None


async def db_add_member(project_id: uuid.UUID, user_id: str, role: str) -> dict:
    """Insert a new project member row and return it."""
    db = await _get_async_client()
    result = (
        await db.table("project_members")
        .insert(
            {
                "project_id": str(project_id),
                "user_id": user_id,
                "role": role,
            }
        )
        .execute()
    )
    return result.data[0]


async def db_update_member_role(project_id: uuid.UUID, user_id: str, role: str) -> dict | None:
    """Update the role for *user_id* in *project_id* and return the updated row."""
    db = await _get_async_client()
    result = await db.table("project_members").update({"role": role}).eq("project_id", str(project_id)).eq("user_id", user_id).execute()
    return result.data[0] if result.data else None


async def db_remove_member(project_id: uuid.UUID, user_id: str) -> None:
    """Delete the member row for *user_id* from *project_id*."""
    db = await _get_async_client()
    await db.table("project_members").delete().eq("project_id", str(project_id)).eq("user_id", user_id).execute()


async def db_count_admins(project_id: uuid.UUID) -> int:
    """Return the number of admin members in *project_id*."""
    db = await _get_async_client()
    result = await db.table("project_members").select("id", count="exact").eq("project_id", str(project_id)).eq("role", "admin").execute()
    return result.count or 0


# ── Branch CRUD ───────────────────────────────────────────────────────────────


async def db_create_branch(
    project_id: uuid.UUID,
    name: str,
    *,
    is_protected: bool = False,
    is_default: bool = False,
    promotes_to_id: uuid.UUID | None = None,
) -> dict:
    """Insert a new branch row and return it."""
    db = await _get_async_client()
    row: dict = {
        "project_id": str(project_id),
        "name": name,
        "is_protected": is_protected,
        "is_default": is_default,
    }
    if promotes_to_id is not None:
        row["promotes_to_id"] = str(promotes_to_id)
    result = await db.table("branches").insert(row).execute()
    return result.data[0]


async def db_get_branch(project_id: uuid.UUID, branch_name: str) -> dict | None:
    """Return the branch row for *branch_name* in *project_id*, or ``None``."""
    db = await _get_async_client()
    result = await db.table("branches").select("*").eq("project_id", str(project_id)).eq("name", branch_name).maybe_single().execute()
    return result.data if result is not None else None


async def db_get_branch_by_id(branch_id: uuid.UUID) -> dict | None:
    """Return the branch row for *branch_id*, or ``None``."""
    db = await _get_async_client()
    result = await db.table("branches").select("*").eq("id", str(branch_id)).maybe_single().execute()
    return result.data if result is not None else None


async def db_list_branches(project_id: uuid.UUID) -> list[dict]:
    """Return all branch rows for *project_id*."""
    db = await _get_async_client()
    result = await db.table("branches").select("*").eq("project_id", str(project_id)).execute()
    return result.data or []


async def db_update_branch(project_id: uuid.UUID, branch_name: str, fields: dict) -> dict | None:
    """Update *fields* on a branch and return the updated row, or ``None``."""
    db = await _get_async_client()
    result = await db.table("branches").update(fields).eq("project_id", str(project_id)).eq("name", branch_name).execute()
    return result.data[0] if result.data else None


async def db_delete_branch(project_id: uuid.UUID, branch_name: str) -> None:
    """Delete the branch row for *branch_name* in *project_id*."""
    db = await _get_async_client()
    await db.table("branches").delete().eq("project_id", str(project_id)).eq("name", branch_name).execute()


# ── Branch manifest CRUD ──────────────────────────────────────────────────────


async def db_get_branch_manifest(branch_id: uuid.UUID) -> dict | None:
    """Return the manifest row for *branch_id*, or ``None`` if none exists."""
    db = await _get_async_client()
    result = await db.table("branch_manifests").select("*").eq("branch_id", str(branch_id)).maybe_single().execute()
    return result.data if result is not None else None


async def db_upsert_branch_manifest(branch_id: uuid.UUID, definition: dict) -> dict:
    """Insert or replace the manifest for a branch (1:1 enforced by UNIQUE branch_id)."""
    db = await _get_async_client()
    result = await (
        db.table("branch_manifests")
        .upsert(
            {"branch_id": str(branch_id), "definition": definition, "run_status": "pending"},
            on_conflict="branch_id",
        )
        .execute()
    )
    return result.data[0]


async def db_patch_manifest_status(branch_id: uuid.UUID, status: str) -> None:
    """Update the ``run_status`` field of the manifest for *branch_id*."""
    db = await _get_async_client()
    await db.table("branch_manifests").update({"run_status": status}).eq("branch_id", str(branch_id)).execute()
