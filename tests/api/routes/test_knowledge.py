# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for /v1/knowledge CRUD routes."""

import uuid

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

# ── Auth guard tests ─────────────────────────────────────────────────────────
_KNOWLEDGE_ROUTES = [
    pytest.param("POST", "/v1/knowledge", id="create"),
    pytest.param("GET", "/v1/knowledge", id="list"),
    pytest.param("GET", f"/v1/knowledge/{uuid.uuid4()}", id="get"),
    pytest.param("PUT", f"/v1/knowledge/{uuid.uuid4()}", id="update"),
    pytest.param("DELETE", f"/v1/knowledge/{uuid.uuid4()}", id="delete"),
]


class TestKnowledgeAuth:
    @pytest.mark.parametrize("method,path", _KNOWLEDGE_ROUTES)
    def test_missing_api_key_returns_401(self, client, method, path):
        r = client.request(method, path, json={})
        assert r.status_code == 401

    @pytest.mark.parametrize("method,path", _KNOWLEDGE_ROUTES)
    def test_wrong_api_key_returns_401(self, client, wrong_headers, method, path):
        r = client.request(method, path, json={}, headers=wrong_headers)
        assert r.status_code == 401

    @pytest.mark.parametrize("method,path", _KNOWLEDGE_ROUTES)
    def test_401_is_problem_json(self, client, method, path):
        r = client.request(method, path, json={})
        assert r.headers["content-type"] == "application/problem+json"
        assert r.json()["status"] == 401


class TestKnowledgeStubResponses:
    """Until the Supabase backend is wired up, all knowledge routes return 501."""

    def test_create_returns_501_with_valid_key(self, client, auth_headers):
        body = {"title": "t", "content": "c"}
        r = client.post("/v1/knowledge", json=body, headers=auth_headers)
        assert r.status_code == 501

    def test_list_returns_501_with_valid_key(self, client, auth_headers):
        r = client.get("/v1/knowledge", headers=auth_headers)
        assert r.status_code == 501

    def test_get_returns_501_with_valid_key(self, client, auth_headers):
        r = client.get(f"/v1/knowledge/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 501

    def test_update_returns_501_with_valid_key(self, client, auth_headers):
        r = client.put(
            f"/v1/knowledge/{uuid.uuid4()}",
            json={"title": "new"},
            headers=auth_headers,
        )
        assert r.status_code == 501

    def test_delete_returns_501_with_valid_key(self, client, auth_headers):
        r = client.delete(f"/v1/knowledge/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 501

    def test_501_body_is_problem_json(self, client, auth_headers):
        r = client.get("/v1/knowledge", headers=auth_headers)
        assert r.headers["content-type"] == "application/problem+json"
        assert r.json()["status"] == 501
