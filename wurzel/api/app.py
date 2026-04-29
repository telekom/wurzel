# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""FastAPI application factory."""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wurzel.api.errors import register_exception_handlers
from wurzel.api.middleware.otel import OTELCorrelationMiddleware, OTELSettings, setup_otel
from wurzel.api.routes.branch.router import router as branch_router
from wurzel.api.routes.files.router import router as files_router
from wurzel.api.routes.health.router import router as health_router
from wurzel.api.routes.ingest.router import router as ingest_router
from wurzel.api.routes.knowledge.router import router as knowledge_router
from wurzel.api.routes.member.router import router as member_router
from wurzel.api.routes.metrics.router import router as metrics_router
from wurzel.api.routes.project.router import router as project_router
from wurzel.api.routes.search.router import router as search_router
from wurzel.api.routes.steps.router import router as steps_router
from wurzel.api.routes.steps.service import warm_step_cache
from wurzel.api.settings import APISettings


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """App lifespan: warm the step cache in a background thread on startup."""
    t = threading.Thread(target=warm_step_cache, daemon=True, name="step-cache-warmup")
    t.start()
    yield


def create_app(
    settings: APISettings | None = None,
    otel_settings: OTELSettings | None = None,
) -> FastAPI:
    """Create and configure the Wurzel API application.

    Args:
        settings: Override :class:`~wurzel.api.settings.APISettings`.
                  Defaults to reading from environment variables.
        otel_settings: Override :class:`~wurzel.api.middleware.otel.OTELSettings`.
                       Defaults to reading from environment variables.

    Returns:
        A fully configured :class:`fastapi.FastAPI` instance.

    Example::

        from wurzel.api import create_app

        app = create_app()
    """
    _settings = settings or APISettings()
    _otel_settings = otel_settings or OTELSettings()

    prefix = f"/{_settings.API_VERSION}"

    app = FastAPI(
        title=_settings.API_TITLE,
        version=_settings.API_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=_lifespan,
    )

    # ── Middleware (outermost → innermost) ──────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(OTELCorrelationMiddleware)

    # ── OTEL SDK ────────────────────────────────────────────────────────────
    setup_otel(app, _otel_settings)

    # ── Exception handlers ──────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ─────────────────────────────────────────────────────────────
    # No auth, no version prefix
    app.include_router(health_router, prefix=f"{prefix}/health", tags=["Health"])
    app.include_router(metrics_router, tags=["Metrics"])

    # X-API-Key authenticated, versioned (legacy / machine-to-machine)
    app.include_router(knowledge_router, prefix=f"{prefix}/knowledge", tags=["Knowledge"])
    app.include_router(ingest_router, prefix=f"{prefix}/ingest", tags=["Ingest"])
    app.include_router(search_router, prefix=f"{prefix}/search", tags=["Search"])
    app.include_router(steps_router, prefix=f"{prefix}/steps", tags=["Steps"])

    # JWT-authenticated project hierarchy
    app.include_router(project_router, prefix=f"{prefix}/projects", tags=["Projects"])
    app.include_router(
        member_router,
        prefix=f"{prefix}/projects/{{project_id}}/members",
        tags=["Members"],
    )
    app.include_router(
        branch_router,
        prefix=f"{prefix}/projects/{{project_id}}/branches",
        tags=["Branches"],
    )
    app.include_router(
        files_router,
        prefix=f"{prefix}/projects/{{project_id}}/steps/{{step_id}}/files",
        tags=["Files"],
    )

    return app
