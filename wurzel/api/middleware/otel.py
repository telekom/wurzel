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

import contextlib
import logging
import secrets
from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Any, cast

from pydantic import Field
from pydantic_settings import SettingsConfigDict
from starlette.types import ASGIApp, Receive, Scope, Send

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
    EXCLUDED_URLS: str = Field(
        "health,live,ready,metrics",
        description=(
            "Comma-separated list of URL path regexes to exclude from tracing "
            "(passed to FastAPIInstrumentor as ``excluded_urls``). "
            "Health-check and metrics endpoints are excluded by default to keep "
            "traces free of probe noise."
        ),
    )


class OTELCorrelationMiddleware:
    """Pure ASGI middleware that propagates W3C trace context and injects the
    trace ID into the Python logging context for every request.

    Implemented as a raw ASGI callable (not Starlette's ``BaseHTTPMiddleware``)
    to avoid the ``contextvars`` propagation issue described in
    https://github.com/open-telemetry/opentelemetry-python/discussions/4131 —
    ``BaseHTTPMiddleware`` spawns an inner task that does not inherit the active
    context, so spans created inside route handlers would not be children of the
    gateway span started here.

    After this middleware runs, every ``logging.LogRecord`` emitted within the
    request lifecycle will carry a ``trace_id`` extra field so that log
    aggregators (Loki, Elasticsearch, …) can correlate entries across services.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    @staticmethod
    def _resolve_ids(scope: Scope) -> tuple[str, str, str, str]:
        """Return ``(tracestate, trace_id, span_id, trace_flags)`` for the request.

        Generates IDs using :class:`~opentelemetry.sdk.trace.id_generator.RandomIdGenerator`
        when the OTEL SDK is available — it satisfies the W3C spec requirement that the 56
        least-significant bits are uniformly random (needed for TraceIdRatioBased sampling).
        Falls back to ``secrets.token_hex`` when the SDK is not installed.

        If an incoming ``traceparent`` header is present its values take priority.
        """
        raw = dict(scope.get("headers", []))
        tracestate = raw.get(b"tracestate", b"").decode()
        trace_flags = "00"
        try:
            from opentelemetry.sdk.trace.id_generator import (  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
                RandomIdGenerator,
            )

            _gen = RandomIdGenerator()
            trace_id = format(_gen.generate_trace_id(), "032x")
            span_id = format(_gen.generate_span_id(), "016x")
        except ImportError:
            trace_id = secrets.token_hex(16)  # 32 hex chars
            span_id = secrets.token_hex(8)  # 16 hex chars
        parts = raw.get(b"traceparent", b"").decode().split("-")
        if len(parts) == 4:
            trace_id, span_id, trace_flags = parts[1], parts[2], parts[3]
        return tracestate, trace_id, span_id, trace_flags

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        tracestate, trace_id, span_id, trace_flags = self._resolve_ids(scope)

        # Try the OTEL SDK: extract W3C context and start a gateway span that
        # wraps the entire request so route-handler spans are children of it.
        span_ctx: contextlib.AbstractContextManager = contextlib.nullcontext()
        try:
            from opentelemetry import propagate  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
            from opentelemetry import trace as otel_trace  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

            span_ctx = otel_trace.get_tracer(__name__).start_as_current_span(
                "http.request",
                context=propagate.extract({k.decode(): v.decode() for k, v in scope.get("headers", [])}),
            )
        except ImportError:
            pass  # OTEL not installed; random/header IDs are already set above

        with span_ctx as span:
            if span is not None:
                sctx = span.get_span_context()
                if sctx and sctx.is_valid:
                    trace_id = format(sctx.trace_id, "032x")
                    span_id = format(sctx.span_id, "016x")
                    trace_flags = "01" if sctx.trace_flags.sampled else "00"

            # Inject trace_id into the Python logging context for this request.
            old_factory = logging.getLogRecordFactory()

            def record_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
                record = old_factory(*args, **kwargs)
                record.trace_id = trace_id  # type: ignore[attr-defined]
                return record

            logging.setLogRecordFactory(record_factory)
            tp_header = f"00-{trace_id}-{span_id}-{trace_flags}".encode()

            async def send_with_traceparent(message: MutableMapping[str, Any]) -> None:
                if message["type"] == "http.response.start":
                    resp_headers = list(message.get("headers", []))
                    resp_headers.append((b"traceparent", tp_header))
                    if tracestate:
                        resp_headers.append((b"tracestate", tracestate.encode()))
                    message = {**message, "headers": resp_headers}
                await send(message)

            try:
                await self._app(scope, receive, send_with_traceparent)
            finally:
                logging.setLogRecordFactory(old_factory)


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
        import fastapi as _fastapi  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        from opentelemetry import trace  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        from opentelemetry.propagate import set_global_textmap  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        from opentelemetry.sdk.resources import Resource  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        from opentelemetry.sdk.trace import TracerProvider  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        from opentelemetry.trace.propagation.tracecontext import (  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
            TraceContextTextMapPropagator,
        )
    except ImportError:
        logger.warning("opentelemetry packages not found — OTEL disabled. Install wurzel[otel] to enable tracing.")
        return

    # Explicitly register the W3C Trace Context propagator as the global textmap
    # so that propagate.extract() / propagate.inject() always use the W3C
    # traceparent/tracestate headers regardless of environment defaults.
    set_global_textmap(TraceContextTextMapPropagator())

    resource = Resource.create({"service.name": settings.SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.EXPORTER_OTLP_ENDPOINT, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Exclude health-check and metrics endpoints from span creation to keep
    # traces free of probe noise (configurable via OTEL__EXCLUDED_URLS).
    FastAPIInstrumentor.instrument_app(cast(_fastapi.FastAPI, app), excluded_urls=settings.EXCLUDED_URLS)
    logger.info(
        "OTEL configured: service=%s endpoint=%s excluded_urls=%s",
        settings.SERVICE_NAME,
        settings.EXPORTER_OTLP_ENDPOINT,
        settings.EXCLUDED_URLS,
    )
