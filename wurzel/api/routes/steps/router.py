# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Step-discovery routes.

Exposes all installed TypedStep subclasses so that a future UI can browse,
inspect, and configure any step without prior knowledge of the codebase.

Routes
------
``GET /v1/steps``                 — list all discoverable steps
``GET /v1/steps/{step_path:path}`` — full schema for a single step (settings, secrets, IO types)
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from wurzel.api.auth.jwt import CurrentUser
from wurzel.api.routes.steps.data import StepInfo, StepListResponse
from wurzel.api.routes.steps.service import CachedStepList, discover_steps, fetch_step_info

router = APIRouter()


@router.get("", response_model=StepListResponse)
async def list_steps(
    _current_user: CurrentUser,
    cache: CachedStepList,
    package: str | None = Query(
        None,
        description="Python package to scan for TypedStep subclasses. Omit to scan all installed venv packages.",
    ),
) -> StepListResponse:
    """Return all TypedStep subclasses discoverable in the current venv.

    By default scans every installed package via AST (no imports, no side
    effects).  Pass ``?package=my_pkg`` to restrict the scan to a single
    installed package.
    """
    return discover_steps(cache, package)


@router.get("/{step_path:path}", response_model=StepInfo)
async def get_step(
    step_path: str,
    _current_user: CurrentUser,
) -> StepInfo:
    """Return the full introspection schema for a single step.

    ``step_path`` is the fully-qualified class path, e.g.
    ``wurzel.steps.splitter.SimpleSplitterStep``.
    """
    return fetch_step_info(step_path)
