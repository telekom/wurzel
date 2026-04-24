# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for POST /v1/search."""

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")


class TestSearchAuth:
    def test_missing_key_returns_401(self, client):
        r = client.post("/v1/search", json={"query": "hello"})
        assert r.status_code == 401

    def test_wrong_key_returns_401(self, client, wrong_headers):
        r = client.post("/v1/search", json={"query": "hello"}, headers=wrong_headers)
        assert r.status_code == 401


class TestSearchValidation:
    def test_missing_query_returns_422(self, client, auth_headers):
        r = client.post("/v1/search", json={}, headers=auth_headers)
        assert r.status_code == 422

    def test_empty_query_returns_422(self, client, auth_headers):
        r = client.post("/v1/search", json={"query": ""}, headers=auth_headers)
        assert r.status_code == 422

    def test_limit_above_max_returns_422(self, client, auth_headers):
        r = client.post("/v1/search", json={"query": "x", "limit": 999}, headers=auth_headers)
        assert r.status_code == 422

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param({"query": "hello"}, id="minimal"),
            pytest.param({"query": "hello", "limit": 5}, id="with_limit"),
            pytest.param(
                {
                    "query": "hello",
                    "limit": 10,
                    "filters": {"tags": ["rag"], "source": "confluence"},
                },
                id="with_filters",
            ),
        ],
    )
    def test_valid_body_reaches_backend_stub(self, client, auth_headers, body):
        """Valid bodies should pass validation and hit the 501 backend stub."""
        r = client.post("/v1/search", json=body, headers=auth_headers)
        assert r.status_code == 501
        assert r.headers["content-type"] == "application/problem+json"
