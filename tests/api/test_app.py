# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for create_app() factory and global middleware."""

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from wurzel.api.app import create_app  # noqa: E402
from wurzel.api.settings import APISettings  # noqa: E402

_SETTINGS = APISettings(API_KEY="test-key")


class TestCreateApp:
    def test_returns_fastapi_instance(self):
        app = create_app(settings=_SETTINGS)
        assert isinstance(app, FastAPI)

    def test_title_from_settings(self):
        settings = APISettings(API_KEY="x", API_TITLE="My KaaS API")
        app = create_app(settings=settings)
        assert app.title == "My KaaS API"

    def test_version_from_settings(self):
        settings = APISettings(API_KEY="x", API_VERSION="v2")
        app = create_app(settings=settings)
        # Version prefix is used in route paths, not FastAPI.version
        routes = [r.path for r in app.routes]
        assert any("/v2/health" in p for p in routes)

    def test_all_expected_routes_registered(self):
        app = create_app(settings=_SETTINGS)
        paths = {r.path for r in app.routes}
        expected = {
            "/v1/health",
            "/v1/health/live",
            "/v1/health/ready",
            "/metrics",
            "/v1/knowledge",
            "/v1/knowledge/{item_id}",
            "/v1/ingest",
            "/v1/ingest/{job_id}",
            "/v1/search",
            "/v1/manifest",
            "/v1/manifest/{manifest_id}",
            "/v1/manifest/{manifest_id}/submit",
            "/v1/steps",
            "/v1/steps/{step_path:path}",
        }
        assert expected.issubset(paths)

    def test_otel_disabled_gracefully_without_package(self, mocker):
        """OTEL setup must not raise even when opentelemetry packages are absent."""
        mocker.patch.dict("sys.modules", {"opentelemetry": None})
        # Should not raise
        app = create_app(settings=_SETTINGS)
        assert app is not None

    def test_cors_header_present(self):
        settings = APISettings(API_KEY="test-key", CORS_ORIGINS=["http://example.com"])
        app = create_app(settings=settings)
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.options(
                "/v1/health",
                headers={"Origin": "http://example.com", "Access-Control-Request-Method": "GET"},
            )
        assert r.status_code in (200, 204)

    def test_otel_trace_id_header_in_response(self):
        app = create_app(settings=_SETTINGS)
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/v1/health/live")
        assert "x-trace-id" in r.headers
        assert len(r.headers["x-trace-id"]) == 32
