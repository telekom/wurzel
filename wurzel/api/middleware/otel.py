# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""OpenTelemetry setup and correlation-ID middleware.

Uses the OTEL trace ID as the distributed correlation ID so that every log
line and every downstream span share the same identifier.

Install the optional dependencies with::

    pip install wurzel[otel]
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from pydantic import Field
from pydantic_settings import SettingsConfigDict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from wurzel.core.settings import Settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class OTELSettings(Settings):
    """Configuration for the OpenTelemetry exporter.

    Reads from environment variables with the prefix ``OTEL__``.
    """

    model_config = SettingsConfigDict(
        env_prefix="OTEL__",
        extra="ignore",
        case_sensitive=True,
    )

    EXPORTER_OTLP_ENDPOINT: str = Field(
        "http://localhost:4317",
        description="OTLP gRPC endpoint for the trace exporter",
    )
    SERVICE_NAME: str = Field("wurzel-api", description="Service name reported to the collector")
    ENABLED: bool = Field(True, description="Set to false to disable OTEL entirely")


class OTELCorrelationMiddleware(BaseHTTPMiddleware):
    """Injects the OTEL trace ID into the Python logging context.

    After this middleware runs, every ``logging.LogRecord`` emitted within the
    request lifecycle will carry a ``trace_id`` extra field so that log
    aggregators (Loki, Elasticsearch, …) can correlate entries across services.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            from opentelemetry import trace  # noqa: PLC0415

            span = trace.get_current_span()
            ctx = span.get_span_context()
            trace_id = format(ctx.trace_id, "032x") if ctx and ctx.is_valid else "0" * 32
        except ImportError:  # pragma: no cover
            trace_id = "0" * 32

        # Inject into logging context for the duration of this request.
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
            record = old_factory(*args, **kwargs)
            record.trace_id = trace_id  # type: ignore[attr-defined]
            return record

        logging.setLogRecordFactory(record_factory)
        try:
            response = await call_next(request)
        finally:
            logging.setLogRecordFactory(old_factory)

        response.headers["X-Trace-Id"] = trace_id
        return response


def setup_otel(app: ASGIApp, settings: OTELSettings) -> None:
    """Configure OTEL SDK and attach instrumentation to *app*.

    This is a no-op when ``settings.ENABLED`` is ``False`` or when the
    ``opentelemetry`` packages are not installed.

    Args:
        app: The FastAPI / Starlette ASGI application instance.
        settings: :class:`OTELSettings` instance.
    """
    if not settings.ENABLED:
        logger.info("OTEL disabled via OTEL__ENABLED=false")
        return

    try:
        from opentelemetry import trace  # noqa: PLC0415
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: PLC0415
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: PLC0415
        from opentelemetry.sdk.resources import Resource  # noqa: PLC0415
        from opentelemetry.sdk.trace import TracerProvider  # noqa: PLC0415
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa: PLC0415
    except ImportError:
        logger.warning("opentelemetry packages not found — OTEL disabled. Install wurzel[otel] to enable tracing.")
        return

    resource = Resource.create({"service.name": settings.SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.EXPORTER_OTLP_ENDPOINT, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)  # type: ignore[arg-type]
    logger.info(
        "OTEL configured: service=%s endpoint=%s",
        settings.SERVICE_NAME,
        settings.EXPORTER_OTLP_ENDPOINT,
    )
