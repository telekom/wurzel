# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import time

from fastapi import Request
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

EXCLUDED_PREFIXES = (
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
)

EXCLUDED_PATHS = frozenset({"/api/v1/isAlive"})

http_requests_total = Counter(
    "kaas_gateway_http_requests_total",
    "HTTP requests",
    ["method", "path_template", "status"],
)

http_request_duration_seconds = Histogram(
    "kaas_gateway_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path_template", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")),
)


class PrometheusHTTPMiddleware(BaseHTTPMiddleware):
    """Record request counts and latency (path from route template when available)."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in EXCLUDED_PATHS or any(path.startswith(p) for p in EXCLUDED_PREFIXES):
            return await call_next(request)

        route = request.scope.get("route")
        path_template = getattr(route, "path", None) or path

        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        status = str(response.status_code)

        http_requests_total.labels(request.method, path_template, status).inc()
        http_request_duration_seconds.labels(request.method, path_template, status).observe(elapsed)
        return response
