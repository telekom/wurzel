# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Project-scoped step discovery routes.

Routes
------
``GET /v1/projects/{project_id}/steps``                   — list all steps visible to the project
``GET /v1/projects/{project_id}/steps/{step_path:path}``  — full schema for a single step
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Query

from wurzel.api.auth.permissions import RequireAnyRole
from wurzel.api.package_manager.installer import get_project_package_dir
from wurzel.api.package_manager.settings import PackageManagerSettings
from wurzel.api.routes.steps.data import StepInfo, StepListResponse
from wurzel.api.routes.steps.service import CachedStepList, discover_steps_for_project, fetch_step_info_for_project

router = APIRouter()


def _get_pkg_settings() -> PackageManagerSettings:
    return PackageManagerSettings()


def _get_project_package_path(project_id: uuid.UUID) -> Path | None:
    try:
        settings = _get_pkg_settings()
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        return None
    return get_project_package_dir(project_id, settings.PACKAGES_DIR)


@router.get("", response_model=StepListResponse)
async def list_project_steps(
    project_id: uuid.UUID,
    cache: CachedStepList,
    _access: RequireAnyRole,
    refresh: bool = Query(
        False,
        description="Force reload the step cache for this project.",
    ),
) -> StepListResponse:
    """Return all TypedStep subclasses visible to this project.

    Includes both globally installed steps (from all wurzel-dependent packages)
    and any steps installed into this project's private package directory.
    """
    extra_path = _get_project_package_path(project_id)
    return discover_steps_for_project(str(project_id), extra_path, cache, refresh=refresh)


@router.get("/{step_path:path}", response_model=StepInfo)
async def get_project_step(
    project_id: uuid.UUID,  # pylint: disable=unused-argument
    step_path: str,
    _access: RequireAnyRole,
) -> StepInfo:
    """Return the full introspection schema for a single step.

    ``step_path`` is the fully-qualified class path, e.g.
    ``wurzel.steps.splitter.SimpleSplitterStep``.

    The ``project_id`` path segment is used for access control only; the step
    itself is resolved from the global environment and the project's installed
    packages directory.
    """
    return fetch_step_info_for_project(step_path, _get_project_package_path(project_id))
