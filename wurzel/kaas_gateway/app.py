# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from contextlib import asynccontextmanager

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response
from temporalio.client import Client

from wurzel.kaas_gateway.api.health import router as health_router
from wurzel.kaas_gateway.api.pipeline import router as pipeline_router
from wurzel.kaas_gateway.api.search import router as search_router
from wurzel.kaas_gateway.api.workflow_status import router as workflow_status_router
from wurzel.kaas_gateway.middleware.prometheus import PrometheusHTTPMiddleware
from wurzel.kaas_gateway.settings import get_settings


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings()
    temporal_client = await Client.connect(
        settings.TEMPORAL_ADDRESS,
        namespace=settings.TEMPORAL_NAMESPACE,
    )
    app.state.temporal_client = temporal_client
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    kwargs: dict = {"title": "Wurzel KaaS Gateway", "version": "0.1.0"}
    if not settings.SWAGGER_ENABLED:
        kwargs["openapi_url"] = None

    app = FastAPI(lifespan=_lifespan, **kwargs)

    app.include_router(health_router)
    app.include_router(pipeline_router)
    app.include_router(workflow_status_router)
    app.include_router(search_router)

    app.add_middleware(PrometheusHTTPMiddleware)
    app.add_middleware(CorrelationIdMiddleware, header_name="x-correlation-id", validator=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
