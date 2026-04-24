# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Health-check endpoints.

These routes are intentionally unauthenticated so that Kubernetes liveness and
readiness probes work without credentials.

Routes
------
``GET /v1/health``       — aggregated health including backend connectivity
``GET /v1/health/live``  — liveness probe (always 200 if the process is up)
``GET /v1/health/ready`` — readiness probe (200 when the app can serve traffic)
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import status as http_status

from wurzel.api.routes.health.data import ComponentHealth, ComponentStatus, HealthResponse

router = APIRouter()


@router.get("", response_model=HealthResponse, summary="Aggregated health check")
async def health() -> HealthResponse:
    """Return the overall service health including infrastructure components."""
    # Extend this list as real components (DB, cache, …) are added.
    components: list[ComponentHealth] = []
    overall = ComponentStatus.OK
    return HealthResponse(status=overall, components=components)


@router.get(
    "/live",
    response_model=HealthResponse,
    summary="Kubernetes liveness probe",
    status_code=http_status.HTTP_200_OK,
)
async def liveness() -> HealthResponse:
    """Returns 200 as long as the process is alive."""
    return HealthResponse(status=ComponentStatus.OK)


@router.get(
    "/ready",
    response_model=HealthResponse,
    summary="Kubernetes readiness probe",
    status_code=http_status.HTTP_200_OK,
)
async def readiness() -> HealthResponse:
    """Returns 200 when the application is ready to serve traffic."""
    return HealthResponse(status=ComponentStatus.OK)
