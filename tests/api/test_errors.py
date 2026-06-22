# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for RFC 7807 error models and exception handlers."""

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from wurzel.api.errors import APIError, ProblemDetail, register_exception_handlers  # noqa: E402


def _make_error_app(*routes) -> FastAPI:
    """Build a minimal app that registers our exception handlers and adds the given routes."""
    app = FastAPI()
    register_exception_handlers(app)
    for route in routes:
        app.add_api_route(**route)
    return app


class TestProblemDetail:
    def test_required_fields(self):
        p = ProblemDetail(title="Oops", status=400)
        assert p.title == "Oops"
        assert p.status == 400
        assert p.type == "about:blank"

    def test_optional_fields_none_by_default(self):
        p = ProblemDetail(title="X", status=500)
        assert p.detail is None
        assert p.instance is None
        assert p.extensions is None

    def test_serialisation_excludes_none(self):
        p = ProblemDetail(title="X", status=404)
        d = p.model_dump(exclude_none=True)
        assert "detail" not in d
        assert "instance" not in d


class TestAPIError:
    def test_inherits_exception(self):
        err = APIError(status_code=400, title="Bad")
        assert isinstance(err, Exception)

    def test_attributes(self):
        err = APIError(status_code=422, title="Invalid", detail="extra info")
        assert err.status_code == 422
        assert err.title == "Invalid"
        assert err.detail == "extra info"

    def test_str_falls_back_to_title(self):
        err = APIError(status_code=404, title="Missing")
        assert "Missing" in str(err)


class TestExceptionHandlers:
    @pytest.fixture(scope="class")
    def error_client(self):
        async def _raise_api_error():
            raise APIError(status_code=409, title="Conflict", detail="Duplicate item")

        async def _raise_generic():
            raise RuntimeError("Something exploded")

        app = _make_error_app(
            {"path": "/api-error", "endpoint": _raise_api_error, "methods": ["GET"]},
            {"path": "/generic-error", "endpoint": _raise_generic, "methods": ["GET"]},
        )
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_api_error_returns_problem_json(self, error_client):
        r = error_client.get("/api-error")
        assert r.status_code == 409
        assert r.headers["content-type"] == "application/problem+json"

    def test_api_error_body_fields(self, error_client):
        r = error_client.get("/api-error")
        body = r.json()
        assert body["title"] == "Conflict"
        assert body["status"] == 409
        assert body["detail"] == "Duplicate item"
        assert "instance" in body

    def test_generic_exception_returns_500_problem_json(self, error_client):
        r = error_client.get("/generic-error")
        assert r.status_code == 500
        assert r.headers["content-type"] == "application/problem+json"
        assert r.json()["title"] == "Internal Server Error"
