# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Prometheus metrics exposition route.

Route
-----
``GET /metrics`` — Prometheus text-format metrics scrape endpoint.

This route is intentionally unauthenticated so that Prometheus can scrape
it without credentials.  ``prometheus-client`` is a core wurzel dependency
so no extra package is required.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter()


@router.get(
    "/metrics",
    response_class=Response,
    summary="Prometheus metrics scrape endpoint",
    include_in_schema=False,
)
async def metrics() -> Response:
    """Expose all registered Prometheus metrics in text exposition format."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
