# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import io
import uuid

import pytest

pytestmark = pytest.mark.supabase_e2e


def test_health_and_metrics_are_available_without_auth(client):
    assert client.get("/v1/health").status_code == 200
    assert client.get("/v1/health/live").status_code == 200
    assert client.get("/v1/health/ready").status_code == 200

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "text/plain" in metrics.headers["content-type"]


def test_ingest_api_key_happy_and_error_paths(client, api_key_headers):
    no_key = client.post("/v1/ingest", json={"items": [{"title": "a", "content": "b"}]})
    assert no_key.status_code == 401

    ok = client.post("/v1/ingest", json={"items": [{"title": "a", "content": "b"}]}, headers=api_key_headers)
    assert ok.status_code == 202
    assert ok.json()["status"] == "pending"

    missing_body = client.post("/v1/ingest", json={}, headers=api_key_headers)
    assert missing_body.status_code == 422

    status_resp = client.get(f"/v1/ingest/{uuid.uuid4()}", headers=api_key_headers)
    assert status_resp.status_code == 501


def test_search_and_knowledge_api_key_error_paths(client, api_key_headers):
    search_missing_key = client.post("/v1/search", json={"query": "hello"})
    assert search_missing_key.status_code == 401

    search_with_key = client.post("/v1/search", json={"query": "hello"}, headers=api_key_headers)
    assert search_with_key.status_code == 501

    knowledge_with_key = client.get("/v1/knowledge", headers=api_key_headers)
    assert knowledge_with_key.status_code == 501


def test_steps_require_jwt_and_list_for_authenticated_user(client, role_headers):
    no_auth = client.get("/v1/steps")
    assert no_auth.status_code == 401

    authenticated = client.get("/v1/steps", headers=role_headers["admin"])
    assert authenticated.status_code == 200
    body = authenticated.json()
    assert "steps" in body
    assert isinstance(body["steps"], list)


@pytest.mark.parametrize("role", ["admin", "member", "secret_editor", "viewer", "no_role"])
def test_files_endpoint_currently_returns_server_error_without_wiring(client, role_headers, project_context, role):
    project_id = project_context["project_id"]
    response = client.post(
        f"/v1/projects/{project_id}/steps/step-a/files",
        params={"step_path": "wurzel.steps.manual_markdown.ManualMarkdownStep"},
        files={"files": ("test.md", io.BytesIO(b"# hello"), "text/markdown")},
        headers=role_headers[role],
    )
    assert response.status_code == 500
