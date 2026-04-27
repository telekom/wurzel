# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for /v1/projects/{project_id}/members routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

from fastapi.testclient import TestClient  # noqa: E402

from wurzel.api.app import create_app  # noqa: E402
from wurzel.api.auth.jwt import _get_auth_settings  # noqa: E402
from wurzel.api.auth.settings import AuthSettings as _AuthSettings  # noqa: E402
from wurzel.api.routes.member.data import ProjectRole  # noqa: E402

from .conftest import ADMIN_USER, make_app  # noqa: E402
from .conftest import SETTINGS as _SETTINGS

_FAKE_AUTH = _AuthSettings(JWKS_URL="http://localhost:9999/.well-known/jwks.json", ENABLED=True)

# ── Constants ─────────────────────────────────────────────────────────────────

_PROJECT_ID = uuid.uuid4()
_ADMIN_USER_ID = "admin-user-uuid"
_MEMBER_USER_ID = "member-user-uuid"
_NEW_USER_ID = "new-user-uuid"
_MEMBER_ID = uuid.uuid4()
_NOW = datetime(2025, 1, 1, 12, 0, 0)


def _make_member_row(
    user_id: str = _MEMBER_USER_ID,
    role: str = "viewer",
    member_id: uuid.UUID | None = None,
) -> dict:
    return {
        "id": str(member_id or uuid.uuid4()),
        "project_id": str(_PROJECT_ID),
        "user_id": user_id,
        "role": role,
        "created_at": _NOW.isoformat(),
    }


def _member_url(suffix: str = "") -> str:
    return f"/v1/projects/{_PROJECT_ID}/members{suffix}"


@pytest.fixture(scope="module")
def app():
    return make_app(ADMIN_USER)


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── Auth ──────────────────────────────────────────────────────────────────────


class TestMembersAuth:
    @pytest.mark.parametrize(
        "method,path_suffix",
        [
            pytest.param("GET", "", id="list"),
            pytest.param("POST", "", id="add"),
            pytest.param("PUT", "/some-user", id="update_role"),
            pytest.param("DELETE", "/some-user", id="remove"),
        ],
    )
    def test_missing_token_returns_401(self, method, path_suffix):
        app = create_app(settings=_SETTINGS)
        app.dependency_overrides[_get_auth_settings] = lambda: _FAKE_AUTH
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.request(method, _member_url(path_suffix), json={})
        assert r.status_code == 401


# ── GET /members ──────────────────────────────────────────────────────────────


class TestListMembers:
    @pytest.mark.parametrize("role_client", ["admin_client", "member_client", "secret_editor_client", "viewer_client"])
    def test_list_any_role_returns_200(self, role_client, request):
        with patch("wurzel.api.routes.member.router.db_list_members", new_callable=AsyncMock, return_value=[]):
            r = request.getfixturevalue(role_client).get(_member_url())
        assert r.status_code == 200

    def test_list_returns_member_list(self, client):
        rows = [_make_member_row(user_id="u1", role="admin"), _make_member_row(user_id="u2", role="member")]
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.member.router.db_list_members", new_callable=AsyncMock, return_value=rows),
        ):
            r = client.get(_member_url())
        body = r.json()
        assert isinstance(body, list)
        assert len(body) == 2

    def test_list_non_member_returns_404(self, no_role_client):
        r = no_role_client.get(_member_url())
        assert r.status_code == 404

    def test_list_each_item_has_required_fields(self, client):
        rows = [_make_member_row()]
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.member.router.db_list_members", new_callable=AsyncMock, return_value=rows),
        ):
            r = client.get(_member_url())
        item = r.json()[0]
        assert "id" in item
        assert "user_id" in item
        assert "role" in item
        assert "project_id" in item


# ── POST /members ─────────────────────────────────────────────────────────────


class TestAddMember:
    def test_add_as_admin_returns_201(self, admin_client):
        row = _make_member_row(user_id=_NEW_USER_ID, role="viewer")
        with (
            patch("wurzel.api.routes.member.router.db_get_member", new_callable=AsyncMock, return_value=None),
            patch("wurzel.api.routes.member.router.db_user_exists", new_callable=AsyncMock, return_value=True),
            patch("wurzel.api.routes.member.router.db_add_member", new_callable=AsyncMock, return_value=row),
        ):
            r = admin_client.post(_member_url(), json={"user_id": _NEW_USER_ID})
        assert r.status_code == 201

    def test_add_returns_member_with_role(self, admin_client):
        row = _make_member_row(user_id=_NEW_USER_ID, role="member")
        with (
            patch("wurzel.api.routes.member.router.db_get_member", new_callable=AsyncMock, return_value=None),
            patch("wurzel.api.routes.member.router.db_user_exists", new_callable=AsyncMock, return_value=True),
            patch("wurzel.api.routes.member.router.db_add_member", new_callable=AsyncMock, return_value=row),
        ):
            r = admin_client.post(_member_url(), json={"user_id": _NEW_USER_ID, "role": "member"})
        assert r.json()["role"] == "member"

    @pytest.mark.parametrize("role_client", ["member_client", "secret_editor_client", "viewer_client"])
    def test_add_non_admin_returns_403(self, role_client, request):
        r = request.getfixturevalue(role_client).post(_member_url(), json={"user_id": _NEW_USER_ID})
        assert r.status_code == 403

    def test_add_duplicate_member_returns_409(self, admin_client):
        existing_row = _make_member_row(user_id=_NEW_USER_ID)
        with patch("wurzel.api.routes.member.router.db_get_member", new_callable=AsyncMock, return_value=existing_row):
            r = admin_client.post(_member_url(), json={"user_id": _NEW_USER_ID})
        assert r.status_code == 409

    def test_add_nonexistent_user_returns_404(self, admin_client):
        with (
            patch("wurzel.api.routes.member.router.db_get_member", new_callable=AsyncMock, return_value=None),
            patch("wurzel.api.routes.member.router.db_user_exists", new_callable=AsyncMock, return_value=False),
        ):
            r = admin_client.post(_member_url(), json={"user_id": "ghost-user-uuid"})
        assert r.status_code == 404

    def test_add_non_member_project_returns_404(self, no_role_client):
        r = no_role_client.post(_member_url(), json={"user_id": _NEW_USER_ID})
        assert r.status_code == 404

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param({}, id="empty"),
            pytest.param({"user_id": _NEW_USER_ID, "role": "god"}, id="invalid_role"),
        ],
    )
    def test_add_invalid_body_returns_422(self, admin_client, body):
        r = admin_client.post(_member_url(), json=body)
        assert r.status_code == 422


# ── PUT /members/{user_id} ────────────────────────────────────────────────────


class TestUpdateMemberRole:
    def test_update_role_as_admin_returns_200(self, admin_client):
        existing = _make_member_row(user_id=_MEMBER_USER_ID, role="viewer")
        updated = _make_member_row(user_id=_MEMBER_USER_ID, role="member")
        with (
            patch("wurzel.api.routes.member.router.db_get_member", new_callable=AsyncMock, return_value=existing),
            patch("wurzel.api.routes.member.router.db_update_member_role", new_callable=AsyncMock, return_value=updated),
        ):
            r = admin_client.put(_member_url(f"/{_MEMBER_USER_ID}"), json={"role": "member"})
        assert r.status_code == 200
        assert r.json()["role"] == "member"

    @pytest.mark.parametrize("role_client", ["member_client", "secret_editor_client", "viewer_client"])
    def test_update_non_admin_returns_403(self, role_client, request):
        r = request.getfixturevalue(role_client).put(_member_url(f"/{_MEMBER_USER_ID}"), json={"role": "member"})
        assert r.status_code == 403

    def test_update_missing_member_returns_404(self, admin_client):
        with patch("wurzel.api.routes.member.router.db_get_member", new_callable=AsyncMock, return_value=None):
            r = admin_client.put(_member_url("/ghost-user"), json={"role": "member"})
        assert r.status_code == 404

    def test_update_non_member_project_returns_404(self, no_role_client):
        r = no_role_client.put(_member_url(f"/{_MEMBER_USER_ID}"), json={"role": "member"})
        assert r.status_code == 404

    def test_demote_last_admin_returns_409(self, admin_client):
        """Cannot demote the only admin of a project."""
        existing = _make_member_row(user_id=_ADMIN_USER_ID, role="admin")
        with (
            patch("wurzel.api.routes.member.router.db_get_member", new_callable=AsyncMock, return_value=existing),
            patch("wurzel.api.routes.member.router.db_count_admins", new_callable=AsyncMock, return_value=1),
        ):
            r = admin_client.put(_member_url(f"/{_ADMIN_USER_ID}"), json={"role": "viewer"})
        assert r.status_code == 409

    def test_update_invalid_role_returns_422(self, admin_client):
        r = admin_client.put(_member_url(f"/{_MEMBER_USER_ID}"), json={"role": "superadmin"})
        assert r.status_code == 422


# ── DELETE /members/{user_id} ─────────────────────────────────────────────────


class TestRemoveMember:
    def test_remove_as_admin_returns_204(self, admin_client):
        existing = _make_member_row(user_id=_MEMBER_USER_ID, role="viewer")
        with (
            patch("wurzel.api.routes.member.router.db_get_member", new_callable=AsyncMock, return_value=existing),
            patch("wurzel.api.routes.member.router.db_remove_member", new_callable=AsyncMock),
        ):
            r = admin_client.delete(_member_url(f"/{_MEMBER_USER_ID}"))
        assert r.status_code == 204

    @pytest.mark.parametrize("role_client", ["member_client", "secret_editor_client", "viewer_client"])
    def test_remove_non_admin_returns_403(self, role_client, request):
        r = request.getfixturevalue(role_client).delete(_member_url(f"/{_MEMBER_USER_ID}"))
        assert r.status_code == 403

    def test_remove_missing_member_returns_404(self, admin_client):
        with patch("wurzel.api.routes.member.router.db_get_member", new_callable=AsyncMock, return_value=None):
            r = admin_client.delete(_member_url("/ghost-user"))
        assert r.status_code == 404

    def test_remove_non_member_project_returns_404(self, no_role_client):
        r = no_role_client.delete(_member_url(f"/{_MEMBER_USER_ID}"))
        assert r.status_code == 404

    def test_remove_last_admin_returns_409(self, admin_client):
        existing = _make_member_row(user_id=_ADMIN_USER_ID, role="admin")
        with (
            patch("wurzel.api.routes.member.router.db_get_member", new_callable=AsyncMock, return_value=existing),
            patch("wurzel.api.routes.member.router.db_count_admins", new_callable=AsyncMock, return_value=1),
        ):
            r = admin_client.delete(_member_url(f"/{_ADMIN_USER_ID}"))
        assert r.status_code == 409
