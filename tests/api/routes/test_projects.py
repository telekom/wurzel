# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for /v1/projects CRUD routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

from fastapi.testclient import TestClient  # noqa: E402

from wurzel.api.app import create_app  # noqa: E402
from wurzel.api.auth.jwt import UserClaims, _get_auth_settings, _verify_jwt  # noqa: E402
from wurzel.api.auth.settings import AuthSettings as _AuthSettings  # noqa: E402
from wurzel.api.routes.member.data import ProjectRole  # noqa: E402
from wurzel.api.settings import APISettings  # noqa: E402

# AuthSettings with ENABLED=True but no real JWKS endpoint — enough to get 401
_FAKE_AUTH = _AuthSettings(JWKS_URL="http://localhost:9999/.well-known/jwks.json", ENABLED=True)

# ── Fixtures ──────────────────────────────────────────────────────────────────

_SETTINGS = APISettings(API_KEY="test-key")
_USER_ID = "user-uuid-1111"
_OTHER_USER_ID = "user-uuid-2222"
_PROJECT_ID = uuid.uuid4()

_USER = UserClaims(sub=_USER_ID, email="test@example.com", raw={})
_NOW = datetime(2025, 1, 1, 12, 0, 0)


def _make_project_row(
    project_id: uuid.UUID | None = None,
    name: str = "My Project",
    description: str | None = "A project",
    created_by: str = _USER_ID,
) -> dict:
    pid = project_id or _PROJECT_ID
    return {
        "id": str(pid),
        "name": name,
        "description": description,
        "created_by": created_by,
        "created_at": _NOW.isoformat(),
        "updated_at": _NOW.isoformat(),
    }


@pytest.fixture(scope="module")
def app():
    _app = create_app(settings=_SETTINGS)
    # Bypass JWT validation — always return our test user
    _app.dependency_overrides[_verify_jwt] = lambda: _USER
    return _app


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── Auth guard ────────────────────────────────────────────────────────────────


class TestProjectsAuth:
    """All project routes require a valid JWT bearer token."""

    @pytest.mark.parametrize(
        "method,path",
        [
            pytest.param("POST", "/v1/projects", id="create"),
            pytest.param("GET", "/v1/projects", id="list"),
            pytest.param("GET", f"/v1/projects/{_PROJECT_ID}", id="get"),
            pytest.param("PUT", f"/v1/projects/{_PROJECT_ID}", id="update"),
            pytest.param("DELETE", f"/v1/projects/{_PROJECT_ID}", id="delete"),
        ],
    )
    def test_missing_bearer_returns_401(self, method, path):
        app = create_app(settings=_SETTINGS)
        app.dependency_overrides[_get_auth_settings] = lambda: _FAKE_AUTH
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.request(method, path, json={})
        assert r.status_code == 401

    @pytest.mark.parametrize(
        "method,path",
        [
            pytest.param("POST", "/v1/projects", id="create"),
            pytest.param("GET", "/v1/projects", id="list"),
            pytest.param("GET", f"/v1/projects/{_PROJECT_ID}", id="get"),
            pytest.param("PUT", f"/v1/projects/{_PROJECT_ID}", id="update"),
            pytest.param("DELETE", f"/v1/projects/{_PROJECT_ID}", id="delete"),
        ],
    )
    def test_invalid_token_returns_401(self, method, path):
        app = create_app(settings=_SETTINGS)
        app.dependency_overrides[_get_auth_settings] = lambda: _FAKE_AUTH
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.request(method, path, json={}, headers={"Authorization": "Bearer bad-token"})
        assert r.status_code == 401

    @pytest.mark.parametrize(
        "method,path",
        [
            pytest.param("POST", "/v1/projects", id="create"),
            pytest.param("GET", "/v1/projects", id="list"),
        ],
    )
    def test_401_body_is_problem_json(self, method, path):
        app = create_app(settings=_SETTINGS)
        app.dependency_overrides[_get_auth_settings] = lambda: _FAKE_AUTH
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.request(method, path, json={})
        assert r.headers["content-type"] == "application/problem+json"
        assert r.json()["status"] == 401


# ── POST /v1/projects ─────────────────────────────────────────────────────────


class TestCreateProject:
    def test_create_returns_201(self, client):
        row = _make_project_row()
        with (
            patch("wurzel.api.routes.project.router.db_create_project", new_callable=AsyncMock, return_value=row),
            patch("wurzel.api.routes.project.router.db_create_branch", new_callable=AsyncMock, return_value={}),
            patch("wurzel.api.routes.project.router.db_add_member", new_callable=AsyncMock, return_value={}),
        ):
            r = client.post("/v1/projects", json={"name": "My Project"})
        assert r.status_code == 201

    def test_create_returns_project_with_id(self, client):
        row = _make_project_row()
        with (
            patch("wurzel.api.routes.project.router.db_create_project", new_callable=AsyncMock, return_value=row),
            patch("wurzel.api.routes.project.router.db_create_branch", new_callable=AsyncMock, return_value={}),
            patch("wurzel.api.routes.project.router.db_add_member", new_callable=AsyncMock, return_value={}),
        ):
            r = client.post("/v1/projects", json={"name": "My Project"})
        body = r.json()
        assert "id" in body
        uuid.UUID(body["id"])

    def test_create_sets_created_by_to_caller(self, client):
        row = _make_project_row(created_by=_USER_ID)
        with (
            patch("wurzel.api.routes.project.router.db_create_project", new_callable=AsyncMock, return_value=row),
            patch("wurzel.api.routes.project.router.db_create_branch", new_callable=AsyncMock, return_value={}),
            patch("wurzel.api.routes.project.router.db_add_member", new_callable=AsyncMock, return_value={}),
        ):
            r = client.post("/v1/projects", json={"name": "My Project"})
        assert r.json()["created_by"] == _USER_ID

    def test_create_also_creates_main_branch(self, client):
        row = _make_project_row()
        with (
            patch("wurzel.api.routes.project.router.db_create_project", new_callable=AsyncMock, return_value=row),
            patch("wurzel.api.routes.project.router.db_create_branch", new_callable=AsyncMock, return_value={}) as mock_branch,
            patch("wurzel.api.routes.project.router.db_add_member", new_callable=AsyncMock, return_value={}),
        ):
            client.post("/v1/projects", json={"name": "My Project"})
        mock_branch.assert_awaited_once()
        call_kwargs = mock_branch.call_args
        assert call_kwargs.args[1] == "main"

    def test_create_adds_creator_as_admin(self, client):
        row = _make_project_row()
        with (
            patch("wurzel.api.routes.project.router.db_create_project", new_callable=AsyncMock, return_value=row),
            patch("wurzel.api.routes.project.router.db_create_branch", new_callable=AsyncMock, return_value={}),
            patch("wurzel.api.routes.project.router.db_add_member", new_callable=AsyncMock, return_value={}) as mock_member,
        ):
            client.post("/v1/projects", json={"name": "My Project"})
        mock_member.assert_awaited_once()
        assert mock_member.call_args.args[2] == "admin"

    def test_create_with_description(self, client):
        row = _make_project_row(description="desc text")
        with (
            patch("wurzel.api.routes.project.router.db_create_project", new_callable=AsyncMock, return_value=row),
            patch("wurzel.api.routes.project.router.db_create_branch", new_callable=AsyncMock, return_value={}),
            patch("wurzel.api.routes.project.router.db_add_member", new_callable=AsyncMock, return_value={}),
        ):
            r = client.post("/v1/projects", json={"name": "My Project", "description": "desc text"})
        assert r.json()["description"] == "desc text"

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param({}, id="empty_body"),
            pytest.param({"name": ""}, id="empty_name"),
            pytest.param({"name": "x" * 121}, id="name_too_long"),
        ],
    )
    def test_create_invalid_body_returns_422(self, client, body):
        r = client.post("/v1/projects", json=body)
        assert r.status_code == 422


# ── GET /v1/projects ──────────────────────────────────────────────────────────


class TestListProjects:
    def test_list_returns_200(self, client):
        with patch(
            "wurzel.api.routes.project.router.db_list_projects_for_user",
            new_callable=AsyncMock,
            return_value=([], 0),
        ):
            r = client.get("/v1/projects")
        assert r.status_code == 200

    def test_list_returns_paginated_envelope(self, client):
        with patch(
            "wurzel.api.routes.project.router.db_list_projects_for_user",
            new_callable=AsyncMock,
            return_value=([], 0),
        ):
            r = client.get("/v1/projects")
        body = r.json()
        assert "items" in body
        assert "total" in body
        assert "offset" in body
        assert "limit" in body

    def test_list_returns_projects(self, client):
        rows = [_make_project_row(name="P1"), _make_project_row(name="P2")]
        with patch(
            "wurzel.api.routes.project.router.db_list_projects_for_user",
            new_callable=AsyncMock,
            return_value=(rows, 2),
        ):
            r = client.get("/v1/projects")
        body = r.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    def test_list_pagination_params_forwarded(self, client):
        with patch(
            "wurzel.api.routes.project.router.db_list_projects_for_user",
            new_callable=AsyncMock,
            return_value=([], 0),
        ) as mock_list:
            client.get("/v1/projects?offset=10&limit=5")
        mock_list.assert_awaited_once_with(_USER_ID, 10, 5)

    def test_list_invalid_offset_returns_422(self, client):
        r = client.get("/v1/projects?offset=-1")
        assert r.status_code == 422

    def test_list_invalid_limit_returns_422(self, client):
        r = client.get("/v1/projects?limit=0")
        assert r.status_code == 422


# ── GET /v1/projects/{project_id} ─────────────────────────────────────────────


class TestGetProject:
    def test_get_known_project_returns_200(self, client):
        row = _make_project_row()
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.project.router.db_get_project", new_callable=AsyncMock, return_value=row),
        ):
            r = client.get(f"/v1/projects/{_PROJECT_ID}")
        assert r.status_code == 200

    def test_get_returns_project_fields(self, client):
        row = _make_project_row(name="Special Project")
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.project.router.db_get_project", new_callable=AsyncMock, return_value=row),
        ):
            r = client.get(f"/v1/projects/{_PROJECT_ID}")
        assert r.json()["name"] == "Special Project"

    def test_get_missing_project_returns_404(self, client):
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.project.router.db_get_project", new_callable=AsyncMock, return_value=None),
        ):
            r = client.get(f"/v1/projects/{_PROJECT_ID}")
        assert r.status_code == 404

    def test_get_invalid_uuid_returns_422(self, client):
        r = client.get("/v1/projects/not-a-uuid")
        assert r.status_code == 422

    @pytest.mark.parametrize("role_client", ["admin_client", "member_client", "secret_editor_client", "viewer_client"])
    def test_get_any_role_returns_200(self, role_client, request):
        row = _make_project_row()
        with patch("wurzel.api.routes.project.router.db_get_project", new_callable=AsyncMock, return_value=row):
            r = request.getfixturevalue(role_client).get(f"/v1/projects/{_PROJECT_ID}")
        assert r.status_code == 200

    def test_get_non_member_returns_404(self, no_role_client):
        r = no_role_client.get(f"/v1/projects/{_PROJECT_ID}")
        assert r.status_code == 404


# ── PUT /v1/projects/{project_id} ─────────────────────────────────────────────


class TestUpdateProject:
    def test_update_as_admin_returns_200(self, client):
        updated = _make_project_row(name="Updated Name")
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.project.router.db_update_project", new_callable=AsyncMock, return_value=updated),
        ):
            r = client.put(f"/v1/projects/{_PROJECT_ID}", json={"name": "Updated Name"})
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Name"

    def test_update_non_member_returns_404(self, client):
        with patch(
            "wurzel.api.backends.supabase.client.get_project_role_from_db",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.put(f"/v1/projects/{_PROJECT_ID}", json={"name": "X"})
        assert r.status_code == 404

    @pytest.mark.parametrize("role_client", ["member_client", "secret_editor_client", "viewer_client"])
    def test_update_non_admin_returns_403(self, role_client, request):
        r = request.getfixturevalue(role_client).put(f"/v1/projects/{_PROJECT_ID}", json={"name": "X"})
        assert r.status_code == 403

    def test_update_empty_body_uses_get_project(self, client):
        """Empty update body should re-fetch via db_get_project (no-op)."""
        row = _make_project_row()
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.project.router.db_get_project", new_callable=AsyncMock, return_value=row) as mock_get,
            patch("wurzel.api.routes.project.router.db_update_project", new_callable=AsyncMock) as mock_update,
        ):
            r = client.put(f"/v1/projects/{_PROJECT_ID}", json={})
        assert r.status_code == 200
        mock_get.assert_awaited_once()
        mock_update.assert_not_awaited()

    def test_update_missing_project_returns_404(self, client):
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.project.router.db_update_project", new_callable=AsyncMock, return_value=None),
        ):
            r = client.put(f"/v1/projects/{_PROJECT_ID}", json={"name": "X"})
        assert r.status_code == 404


# ── DELETE /v1/projects/{project_id} ──────────────────────────────────────────


class TestDeleteProject:
    def test_delete_as_admin_returns_204(self, client):
        row = _make_project_row()
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.project.router.db_get_project", new_callable=AsyncMock, return_value=row),
            patch("wurzel.api.routes.project.router.db_delete_project", new_callable=AsyncMock),
        ):
            r = client.delete(f"/v1/projects/{_PROJECT_ID}")
        assert r.status_code == 204

    def test_delete_missing_project_returns_404(self, client):
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.project.router.db_get_project", new_callable=AsyncMock, return_value=None),
        ):
            r = client.delete(f"/v1/projects/{_PROJECT_ID}")
        assert r.status_code == 404

    def test_delete_non_member_returns_404(self, client):
        with patch(
            "wurzel.api.backends.supabase.client.get_project_role_from_db",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.delete(f"/v1/projects/{_PROJECT_ID}")
        assert r.status_code == 404

    @pytest.mark.parametrize("role_client", ["member_client", "secret_editor_client", "viewer_client"])
    def test_delete_non_admin_returns_403(self, role_client, request):
        r = request.getfixturevalue(role_client).delete(f"/v1/projects/{_PROJECT_ID}")
        assert r.status_code == 403
