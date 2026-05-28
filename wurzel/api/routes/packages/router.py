# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Packages and secrets routes.

Routes
------
``POST   /v1/projects/{project_id}/packages``                — request a package install (admin)
``GET    /v1/projects/{project_id}/packages``                — list packages (any member)
``DELETE /v1/projects/{project_id}/packages/{package_id}``  — soft-delete a package (admin)

``PUT    /v1/projects/{project_id}/secrets/{secret_name}``  — upsert a secret (admin / secret_editor)
``DELETE /v1/projects/{project_id}/secrets/{secret_name}``  — delete a secret (admin / secret_editor)
``GET    /v1/projects/{project_id}/secrets``                 — list secret metadata (admin / secret_editor)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Path
from fastapi import status as http_status

from wurzel.api.auth.jwt import CurrentUser
from wurzel.api.auth.permissions import RequireAdmin, RequireAnyRole, RequireSecretEditor
from wurzel.api.errors import RESPONSE_401, RESPONSE_403, RESPONSE_404, RESPONSE_409, APIError
from wurzel.api.package_manager.db import (
    db_add_project_package,
    db_delete_project_package,
    db_delete_project_secret,
    db_get_active_project_package,
    db_list_project_packages,
    db_list_project_secrets,
    db_upsert_project_secret,
)
from wurzel.api.package_manager.installer import validate_package_spec
from wurzel.api.package_manager.settings import PackageManagerSettings
from wurzel.api.routes.packages.data import (
    AddPackageRequest,
    PackageResponse,
    SecretMetaResponse,
    SecretRequest,
)

router = APIRouter()


def _get_pkg_settings() -> PackageManagerSettings:
    return PackageManagerSettings()


def _row_to_package(row: dict) -> PackageResponse:
    return PackageResponse(
        id=uuid.UUID(row["id"]),
        project_id=uuid.UUID(row["project_id"]),
        package_spec=row["package_spec"],
        index_secret_name=row.get("index_secret_name"),
        status=row["status"],
        error=row.get("error"),
        installed_at=row.get("installed_at"),
        created_at=row["created_at"],
        created_by=row["created_by"],
    )


def _row_to_secret_meta(row: dict) -> SecretMetaResponse:
    return SecretMetaResponse(
        id=uuid.UUID(row["id"]),
        name=row["name"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ── Packages ──────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=PackageResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
    responses={**RESPONSE_401, **RESPONSE_403, **RESPONSE_404, **RESPONSE_409},
)
async def add_package(
    project_id: uuid.UUID,
    body: AddPackageRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    _access: RequireAdmin,
) -> PackageResponse:
    """Request installation of a Python package for this project.

    The package is queued immediately (``status='pending'``) and installed
    asynchronously after the response is sent.  Poll
    ``GET /v1/projects/{id}/packages`` to check ``status``.
    """
    try:
        validate_package_spec(body.package_spec)
    except ValueError as exc:
        raise APIError(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Invalid package spec",
            detail=str(exc),
        ) from exc

    try:
        settings = _get_pkg_settings()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise APIError(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            title="Package manager not configured",
            detail="PACKAGE_MANAGER__PACKAGES_DIR is not set. Configure the package manager before installing packages.",
        ) from exc

    existing = await db_get_active_project_package(project_id, body.package_spec, body.index_secret_name)
    if existing is not None:
        raise APIError(
            status_code=http_status.HTTP_409_CONFLICT,
            title="Package already exists",
            detail=(f"Package '{body.package_spec}' already exists for project {project_id} with status '{existing.get('status')}'."),
        )

    row = await db_add_project_package(
        project_id,
        body.package_spec,
        body.index_secret_name,
        user.sub,
    )
    package_id = uuid.UUID(row["id"])

    from wurzel.api.package_manager.background import perform_install  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    background_tasks.add_task(perform_install, package_id, settings)

    return _row_to_package(row)


@router.get("", response_model=list[PackageResponse], responses={**RESPONSE_401, **RESPONSE_403, **RESPONSE_404})
async def list_packages(
    project_id: uuid.UUID,
    _access: RequireAnyRole,
) -> list[PackageResponse]:
    """List all packages for this project (excluding soft-deleted ones)."""
    rows = await db_list_project_packages(project_id)
    return [_row_to_package(r) for r in rows]


@router.delete("/{package_id}", status_code=http_status.HTTP_204_NO_CONTENT, responses={**RESPONSE_401, **RESPONSE_403, **RESPONSE_404})
async def delete_package(
    project_id: uuid.UUID,
    package_id: uuid.UUID = Path(...),
    _access: RequireAdmin = None,  # type: ignore
) -> None:
    """Soft-delete a package (sets ``status='deleted'``).

    Installed files on the shared volume are **not** removed because
    ``uv pip install --target`` is not cleanly reversible per-package.
    The step discovery layer excludes deleted packages automatically.
    """
    await db_delete_project_package(project_id, package_id)


# ── Secrets ───────────────────────────────────────────────────────────────────


@router.put(
    "/secrets/{secret_name}",
    response_model=SecretMetaResponse,
    status_code=http_status.HTTP_200_OK,
    responses={**RESPONSE_401, **RESPONSE_403, **RESPONSE_404},
)
async def upsert_secret(
    project_id: uuid.UUID,
    secret_name: str = Path(...),
    body: SecretRequest = None,  # type: ignore
    user: CurrentUser = None,  # type: ignore
    _access: RequireSecretEditor = None,  # type: ignore
) -> SecretMetaResponse:
    """Create or update a project secret.

    The value is stored as-is and is never returned by any list endpoint.
    Typically used to store private PyPI index URLs (including credentials).
    """
    row = await db_upsert_project_secret(project_id, secret_name, body.value, user.sub)
    return _row_to_secret_meta(row)


@router.delete(
    "/secrets/{secret_name}", status_code=http_status.HTTP_204_NO_CONTENT, responses={**RESPONSE_401, **RESPONSE_403, **RESPONSE_404}
)
async def delete_secret(
    project_id: uuid.UUID,
    secret_name: str = Path(...),
    _access: RequireSecretEditor = None,  # type: ignore
) -> None:
    """Delete a project secret by name."""
    await db_delete_project_secret(project_id, secret_name)


@router.get("/secrets", response_model=list[SecretMetaResponse], responses={**RESPONSE_401, **RESPONSE_403, **RESPONSE_404})
async def list_secrets(
    project_id: uuid.UUID,
    _access: RequireSecretEditor = None,  # type: ignore
) -> list[SecretMetaResponse]:
    """List secret metadata (name, timestamps) — values are never included."""
    rows = await db_list_project_secrets(project_id)
    return [_row_to_secret_meta(r) for r in rows]
