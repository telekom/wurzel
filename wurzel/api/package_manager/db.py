# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Supabase DB helpers for the package manager domain.

Covers ``project_secrets``, ``project_packages``, and
``project_package_locks`` tables.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


async def _get_client():
    """Return the shared async Supabase client."""
    from wurzel.api.backends.supabase.client import _get_async_client  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    return await _get_async_client()


# ── project_secrets ───────────────────────────────────────────────────────────


async def db_list_project_secrets(project_id: uuid.UUID) -> list[dict]:
    """Return secret metadata (id, name, timestamps) for *project_id*.

    The ``value`` field is intentionally excluded.
    """
    db = await _get_client()
    result = await db.table("project_secrets").select("id, name, created_at, updated_at").eq("project_id", str(project_id)).execute()
    return result.data or []


async def db_get_secret_value(project_id: uuid.UUID, secret_name: str) -> str | None:
    """Return the plaintext value of *secret_name* in *project_id*, or ``None``.

    Called by the background job immediately before install — result is not
    cached to avoid exposing credentials in memory longer than necessary.
    """
    db = await _get_client()
    result = (
        await db.table("project_secrets").select("value").eq("project_id", str(project_id)).eq("name", secret_name).maybe_single().execute()
    )
    if result is None or result.data is None:
        return None
    return result.data["value"]


async def db_upsert_project_secret(
    project_id: uuid.UUID,
    name: str,
    value: str,
    created_by: str,
) -> dict:
    """Insert or update the secret *name* for *project_id* and return the row.

    Uses ``upsert`` with ``on_conflict="project_id,name"`` so an existing
    secret with the same name is updated in place.
    """
    db = await _get_client()
    result = (
        await db.table("project_secrets")
        .upsert(
            {
                "project_id": str(project_id),
                "name": name,
                "value": value,
                "created_by": created_by,
            },
            on_conflict="project_id,name",
        )
        .execute()
    )
    return result.data[0]


async def db_delete_project_secret(project_id: uuid.UUID, secret_name: str) -> None:
    """Delete the secret *secret_name* from *project_id*."""
    db = await _get_client()
    await db.table("project_secrets").delete().eq("project_id", str(project_id)).eq("name", secret_name).execute()


# ── project_packages ──────────────────────────────────────────────────────────


async def db_add_project_package(
    project_id: uuid.UUID,
    package_spec: str,
    index_secret_name: str | None,
    created_by: str,
) -> dict:
    """Insert a new package row with ``status='pending'`` and return it."""
    db = await _get_client()
    result = (
        await db.table("project_packages")
        .insert(
            {
                "project_id": str(project_id),
                "package_spec": package_spec,
                "index_secret_name": index_secret_name,
                "created_by": created_by,
            }
        )
        .execute()
    )
    return result.data[0]


async def db_list_project_packages(project_id: uuid.UUID) -> list[dict]:
    """Return all non-deleted package rows for *project_id*."""
    db = await _get_client()
    result = await db.table("project_packages").select("*").eq("project_id", str(project_id)).neq("status", "deleted").execute()
    return result.data or []


async def db_delete_project_package(project_id: uuid.UUID, package_id: uuid.UUID) -> None:
    """Soft-delete the package row by setting ``status='deleted'``.

    Physical deletion is avoided because ``uv pip install --target`` installs
    are not cleanly reversible per-package.  The step discovery layer excludes
    rows with ``status='deleted'``.
    """
    db = await _get_client()
    await db.table("project_packages").update({"status": "deleted"}).eq("project_id", str(project_id)).eq("id", str(package_id)).execute()


async def db_claim_pending_package(package_id: uuid.UUID, installer_id: str) -> bool:
    """Attempt to claim *package_id* for installation by this replica.

    Uses a conditional update (``WHERE status='pending'``) as an optimistic
    distributed lock.  Returns ``True`` if this replica won the race,
    ``False`` if another replica already claimed it.
    """
    db = await _get_client()
    result = (
        await db.table("project_packages")
        .update({"status": "installing", "installer_id": installer_id})
        .eq("id", str(package_id))
        .eq("status", "pending")
        .execute()
    )
    return bool(result.data)


async def db_mark_installed(
    package_id: uuid.UUID,
    lock_entries: list[dict[str, str]],
) -> None:
    """Mark *package_id* as successfully installed and persist lock entries.

    Args:
        package_id: UUID of the ``project_packages`` row.
        lock_entries: List of ``{"requirement": ..., "sha256": ...}`` dicts
                      produced by :func:`~wurzel.api.package_manager.installer.read_lock_entries`.
    """
    db = await _get_client()
    await (
        db.table("project_packages")
        .update(
            {
                "status": "installed",
                "installed_at": datetime.now(tz=UTC).isoformat(),
                "error": None,
            }
        )
        .eq("id", str(package_id))
        .execute()
    )
    if lock_entries:
        rows = [
            {
                "package_id": str(package_id),
                "requirement": entry["requirement"],
                "sha256": entry["sha256"],
            }
            for entry in lock_entries
        ]
        await db.table("project_package_locks").insert(rows).execute()


async def db_mark_failed(package_id: uuid.UUID, error: str) -> None:
    """Mark *package_id* as failed and record the error message."""
    db = await _get_client()
    await db.table("project_packages").update({"status": "failed", "error": error}).eq("id", str(package_id)).execute()


async def db_get_pending_packages() -> list[dict]:
    """Return all package rows with ``status='pending'`` across all projects."""
    db = await _get_client()
    result = await db.table("project_packages").select("*").eq("status", "pending").execute()
    return result.data or []


async def db_reset_stale_installing(installer_id: str, timeout_seconds: int) -> int:
    """Reset packages stuck in ``'installing'`` back to ``'pending'``.

    Only resets rows owned by *other* replicas (``installer_id != this_id``),
    whose ``created_at`` is older than *timeout_seconds*.  Returns the number
    of rows reset.

    Note: Supabase PostgREST does not support time-based filters via the
    Python client's arithmetic helpers, so we use a raw SQL expression via
    ``rpc`` to apply the timeout.  If RPC is unavailable, we fall back to
    resetting all foreign stale rows unconditionally.
    """
    db = await _get_client()
    # Fetch stale candidates first (avoids needing raw SQL via rpc)
    result = (
        await db.table("project_packages").select("id, created_at").eq("status", "installing").neq("installer_id", installer_id).execute()
    )
    rows = result.data or []
    now = datetime.now(tz=UTC)
    stale_ids = []
    for row in rows:
        created_at_str = row.get("created_at", "")
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            if (now - created_at).total_seconds() >= timeout_seconds:
                stale_ids.append(row["id"])
        except (ValueError, TypeError):
            stale_ids.append(row["id"])  # reset if we can't parse the timestamp

    if stale_ids:
        await db.table("project_packages").update({"status": "pending", "installer_id": None}).in_("id", stale_ids).execute()
        logger.info("Reset %d stale 'installing' packages to 'pending'", len(stale_ids))

    return len(stale_ids)


async def db_get_installed_packages_with_locks() -> list[dict]:
    """Return all ``status='installed'`` packages with their lock entries.

    Used at startup to re-install packages on replicas where the shared volume
    does not yet contain the installed files.
    """
    db = await _get_client()
    result = (
        await db.table("project_packages")
        .select("id, project_id, package_spec, index_secret_name, project_package_locks(requirement, sha256)")
        .eq("status", "installed")
        .execute()
    )
    return result.data or []
