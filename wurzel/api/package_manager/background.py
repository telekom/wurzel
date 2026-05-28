# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Background install logic for the runtime package manager.

Two entry points:

* :func:`perform_install` — async entry point used by FastAPI/Starlette
    ``BackgroundTasks``. Triggered via
  ``background_tasks.add_task(perform_install, package_id, settings)`` on the
  POST /packages endpoint.

* :func:`recover_and_reinstall_on_startup` — called once from the app
  lifespan in a daemon thread.  Handles three startup scenarios:
    1. Packages stuck in ``'installing'`` from a previous crashed replica.
    2. Packages with ``status='installed'`` whose files are absent from the
       shared volume (fresh pod / new replica).
    3. Any remaining ``'pending'`` packages queued while this replica was down.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


async def perform_install(package_id: uuid.UUID, settings) -> None:  # type: ignore[type-arg]
    """Claim and install a single package row.

    Designed to be scheduled via FastAPI ``BackgroundTasks`` so it runs after
    the HTTP response is sent.  Declared ``async`` so FastAPI awaits it directly
    in the running event loop rather than requiring a new one.

    Args:
        package_id: UUID of the ``project_packages`` row to install.
        settings: :class:`~wurzel.api.package_manager.settings.PackageManagerSettings`
                  instance.
    """
    try:
        await _perform_install_async(package_id, settings)
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.exception("Unhandled error in perform_install for package %s", package_id)


async def _perform_install_async(package_id: uuid.UUID, settings) -> None:  # type: ignore[type-arg]
    from wurzel.api.package_manager.db import (  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        db_claim_pending_package,
    )

    # Step 1: claim the row
    claimed = await db_claim_pending_package(package_id, settings.INSTALLER_ID)
    if not claimed:
        logger.info("Package %s already claimed by another replica — skipping", package_id)
        return

    # Step 2–5: install, read locks, persist, and invalidate cache
    package_data = await _fetch_and_validate_package(package_id)
    if package_data is None:
        return

    project_id, package_spec, index_secret_name = package_data
    index_url = await _resolve_index_url(project_id, index_secret_name, package_id)
    if index_url is None and index_secret_name:
        return

    success = await _install_and_persist(package_id, project_id, package_spec, index_url, settings)
    if success:
        _invalidate_project_step_cache(project_id)


async def _fetch_and_validate_package(package_id: uuid.UUID) -> tuple[uuid.UUID, str, str | None] | None:
    """Fetch and return package row data, or None if not found."""
    from wurzel.api.backends.supabase.client import _get_async_client  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    db = await _get_async_client()
    result = await db.table("project_packages").select("*").eq("id", str(package_id)).maybe_single().execute()
    if result is None or result.data is None:
        logger.error("Package row %s not found after claiming — aborting", package_id)
        return None

    row = result.data
    return uuid.UUID(row["project_id"]), row["package_spec"], row.get("index_secret_name")


async def _resolve_index_url(project_id: uuid.UUID, index_secret_name: str | None, package_id: uuid.UUID) -> str | None:
    """Resolve index URL from secrets, or None if no secret is needed."""
    if not index_secret_name:
        return None

    from wurzel.api.package_manager.db import (  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        db_get_secret_value,
        db_mark_failed,
    )

    index_url = await db_get_secret_value(project_id, index_secret_name)
    if index_url is None:
        await db_mark_failed(package_id, f"Secret '{index_secret_name}' not found in project secrets.")
    return index_url


async def _install_and_persist(
    package_id: uuid.UUID,
    project_id: uuid.UUID,
    package_spec: str,
    index_url: str | None,  # noqa: PLC0415
    settings,  # type: ignore[type-arg]
) -> bool:
    """Install package, read locks, and persist. Return True on success."""
    from wurzel.api.package_manager.db import db_mark_failed, db_mark_installed  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
    from wurzel.api.package_manager.installer import (  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        get_project_package_dir,
        install_package,
        read_lock_entries,
    )

    try:
        install_package(project_id, package_spec, index_url, settings.PACKAGES_DIR, settings.UV_EXECUTABLE)
    except RuntimeError as exc:
        await db_mark_failed(package_id, str(exc))
        return False
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        await db_mark_failed(package_id, f"Package install failed unexpectedly: {exc}")
        return False

    target_dir = get_project_package_dir(project_id, settings.PACKAGES_DIR)
    lock_entries = read_lock_entries(target_dir)
    await db_mark_installed(package_id, lock_entries)
    logger.info("Package %s (%r) installed for project %s", package_id, package_spec, project_id)
    return True


def _invalidate_project_step_cache(project_id: uuid.UUID) -> None:
    """Evict the per-project step discovery cache entry after a successful install."""
    try:
        from wurzel.api.routes.steps.service import _DEFAULT_CACHE  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

        _DEFAULT_CACHE.clear_project(project_id)
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.debug("Could not invalidate step cache for project %s", project_id)


def recover_and_reinstall_on_startup(settings) -> None:  # type: ignore[type-arg]
    """One-shot startup recovery: reset stale rows and reinstall missing packages.

    Intended to be called from the app lifespan in a daemon thread
    (matches the existing ``step-cache-warmup`` pattern).

    Steps:
        1. Reset packages stuck in ``'installing'`` (crashed replica) back to
           ``'pending'`` using the configurable timeout threshold.
        2. For packages with ``status='installed'`` whose target directory is
           absent (fresh pod), re-install from DB lock hashes using
           ``uv pip install --require-hashes``.
        3. Trigger :func:`perform_install` for any remaining ``'pending'``
           packages (queued while this replica was down).
    """
    try:
        asyncio.run(_recover_and_reinstall_async(settings))
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.exception("Unhandled error in recover_and_reinstall_on_startup")


async def _recover_and_reinstall_async(settings) -> None:  # type: ignore[type-arg]
    from postgrest.exceptions import APIError  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    from wurzel.api.package_manager.db import (  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        db_get_installed_packages_with_locks,
        db_get_pending_packages,
        db_reset_stale_installing,
    )

    # 1. Reset stale 'installing' rows from other (crashed) replicas
    try:
        reset_count = await db_reset_stale_installing(settings.INSTALLER_ID, settings.INSTALLING_TIMEOUT_SECONDS)
    except APIError as exc:
        if exc.code == "PGRST205":
            logger.warning("Startup recovery skipped: table not found in schema cache (PGRST205). Migrations may not have run yet.")
            return
        raise
    if reset_count:
        logger.info("Startup recovery: reset %d stale 'installing' rows to 'pending'", reset_count)

    # 2. Re-install packages whose files are missing from the shared volume
    installed = await db_get_installed_packages_with_locks()
    for row in installed:
        await _reinstall_missing_package(row, settings)

    # 3. Kick off any remaining pending installs
    pending = await db_get_pending_packages()
    for row in pending:
        package_id = uuid.UUID(row["id"])
        logger.info("Startup recovery: triggering deferred install for package %s", package_id)
        await perform_install(package_id, settings)


async def _reinstall_missing_package(row: dict, settings) -> None:  # type: ignore[type-arg]
    """Re-install a package if its target directory is missing."""
    import subprocess  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    from wurzel.api.package_manager.db import db_mark_failed  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
    from wurzel.api.package_manager.installer import get_project_package_dir  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    project_id = uuid.UUID(row["project_id"])
    package_id = uuid.UUID(row["id"])
    target_dir = get_project_package_dir(project_id, settings.PACKAGES_DIR)

    if target_dir.exists():
        return  # already on disk — nothing to do

    lock_entries: list[dict] = row.get("project_package_locks") or []
    if not lock_entries:
        logger.warning(
            "Package %s has no lock entries — cannot reinstall with --require-hashes; skipping",
            package_id,
        )
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    hash_args: list[str] = []
    req_args: list[str] = []
    for entry in lock_entries:
        req_args.append(entry["requirement"])
        hash_args.extend(["--hash", f"sha256:{entry['sha256']}"])

    cmd = [
        settings.UV_EXECUTABLE,
        "pip",
        "install",
        "--require-hashes",
        "--target",
        str(target_dir),
        *req_args,
        *hash_args,
    ]
    logger.info("Startup re-install for project %s: %s", project_id, req_args)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
    if result.returncode != 0:
        error_msg = f"Startup re-install failed (exit {result.returncode}):\n{result.stderr}"
        logger.error(error_msg)
        await db_mark_failed(package_id, error_msg)
    else:
        _invalidate_project_step_cache(project_id)
