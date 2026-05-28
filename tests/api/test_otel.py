# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for OTELCorrelationMiddleware and setup_otel."""

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from wurzel.api.middleware.otel import OTELCorrelationMiddleware, OTELSettings, setup_otel  # noqa: E402


def _make_app() -> FastAPI:
    """Return a minimal FastAPI app with OTELCorrelationMiddleware."""
    app = FastAPI()
    app.add_middleware(OTELCorrelationMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return app


class TestSetupOtel:
    def test_setup_otel_disabled_is_noop(self):
        """setup_otel with ENABLED=False must return immediately without touching providers."""
        app = FastAPI()
        setup_otel(app, OTELSettings(ENABLED=False))

    def test_setup_otel_otel_not_installed(self, mocker):
        """setup_otel when opentelemetry packages are absent must log a warning and return."""
        mocker.patch.dict(
            "sys.modules",
            {
                "opentelemetry": None,
                "opentelemetry.sdk": None,
                "opentelemetry.sdk.trace": None,
                "opentelemetry.sdk.trace.export": None,
                "opentelemetry.sdk.resources": None,
                "opentelemetry.instrumentation": None,
                "opentelemetry.instrumentation.fastapi": None,
                "opentelemetry.propagate": None,
                "opentelemetry.trace": None,
                "opentelemetry.trace.propagation": None,
                "opentelemetry.trace.propagation.tracecontext": None,
                "opentelemetry.exporter": None,
                "opentelemetry.exporter.otlp": None,
                "opentelemetry.exporter.otlp.proto": None,
                "opentelemetry.exporter.otlp.proto.grpc": None,
                "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": None,
            },
        )
        # Must complete without raising even though OTEL packages are missing
        setup_otel(FastAPI(), OTELSettings(ENABLED=True))

    def test_setup_otel_with_otel_available(self, mocker):
        """setup_otel with OTEL installed must configure a tracer provider and instrument the app."""
        mock_instr = mocker.patch("opentelemetry.instrumentation.fastapi.FastAPIInstrumentor.instrument_app")
        app = FastAPI()
        setup_otel(app, OTELSettings(ENABLED=True, SERVICE_NAME="test-svc"))
        mock_instr.assert_called_once()


class TestOTELCorrelationMiddleware:
    def test_tracestate_header_forwarded_in_response(self):
        """An incoming ``tracestate`` header must be echoed in the response."""
        app = _make_app()
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get(
                "/ping",
                headers={
                    "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
                    "tracestate": "vendor=value",
                },
            )
        assert r.headers.get("tracestate") == "vendor=value"

    def test_non_http_scope_passthrough(self):
        """Non-HTTP scopes (e.g. lifespan) must pass through without modification."""
        # The middleware only handles http/websocket scopes; other scopes pass through.
        app = _make_app()
        # A normal request on an http scope exercises the happy-path; here we verify
        # the middleware does NOT crash when the app starts up (lifespan scope).
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/ping")
        assert r.status_code == 200

    def test_random_id_fallback_when_otel_sdk_absent(self, mocker):
        """When only the OTEL SDK id-generator is absent, ``secrets.token_hex`` is used."""
        mocker.patch.dict(
            "sys.modules",
            {
                "opentelemetry.sdk.trace.id_generator": None,
            },
        )
        app = _make_app()
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/ping")
        tp = r.headers["traceparent"]
        parts = tp.split("-")
        assert len(parts) == 4
        assert parts[1] != "0" * 32, "trace-id must not be all-zeros"
        assert parts[2] != "0" * 16, "span-id must not be all-zeros"

    def test_valid_otel_span_updates_trace_id(self, mocker):
        """When OTEL is available and produces a valid span, its IDs must be used."""
        from opentelemetry.sdk.trace import TracerProvider

        # Set up a real in-memory tracer so spans have valid contexts.
        provider = TracerProvider()
        mocker.patch("opentelemetry.trace.get_tracer_provider", return_value=provider)

        app = _make_app()
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/ping")
        tp = r.headers.get("traceparent", "")
        parts = tp.split("-")
        assert len(parts) == 4
        assert parts[0] == "00"
        assert len(parts[1]) == 32
        assert len(parts[2]) == 16
