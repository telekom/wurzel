# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for shared FastAPI dependencies (auth, pagination)."""

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

from wurzel.api.dependencies import PaginationParams  # noqa: E402


class TestPaginationParams:
    def test_defaults(self):
        p = PaginationParams()
        assert p.offset == 0
        assert p.limit == 50

    def test_custom_values(self):
        p = PaginationParams(offset=20, limit=10)
        assert p.offset == 20
        assert p.limit == 10

    @pytest.mark.parametrize(
        "offset,limit",
        [
            pytest.param(0, 1, id="min_limit"),
            pytest.param(0, 200, id="max_limit"),
            pytest.param(999, 50, id="large_offset"),
        ],
    )
    def test_valid_params(self, offset, limit):
        p = PaginationParams(offset=offset, limit=limit)
        assert p.offset == offset
        assert p.limit == limit


class TestAuthDependency:
    """Auth is exercised through the full client in other test modules.
    These tests verify the dependency wiring directly via the app.
    """

    def test_missing_api_key_returns_401(self, client):
        r = client.get("/v1/knowledge")
        assert r.status_code == 401

    def test_wrong_api_key_returns_401(self, client, wrong_headers):
        r = client.get("/v1/knowledge", headers=wrong_headers)
        assert r.status_code == 401

    def test_401_body_is_problem_json(self, client):
        r = client.get("/v1/knowledge")
        assert r.headers["content-type"] == "application/problem+json"
        body = r.json()
        assert body["status"] == 401
        assert "title" in body
