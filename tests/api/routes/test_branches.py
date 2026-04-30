# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for /v1/projects/{project_id}/branches routes."""

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
_BRANCH_ID = uuid.uuid4()
_BRANCH_ID_2 = uuid.uuid4()
_NOW = datetime(2025, 1, 1, 12, 0, 0)

_MINIMAL_MANIFEST = {
    "apiVersion": "wurzel.dev/v1alpha1",
    "kind": "Pipeline",
    "metadata": {"name": "test-pipeline"},
    "spec": {
        "backend": "dvc",
        "steps": [
            {
                "name": "source",
                "class": "wurzel.steps.manual_markdown.ManualMarkdownStep",
            }
        ],
    },
}


def _make_branch_row(
    name: str = "feature-x",
    branch_id: uuid.UUID | None = None,
    is_protected: bool = False,
    is_default: bool = False,
) -> dict:
    return {
        "id": str(branch_id or _BRANCH_ID),
        "project_id": str(_PROJECT_ID),
        "name": name,
        "is_protected": is_protected,
        "is_default": is_default,
        "promotes_to_id": None,
        "promotes_to_name": None,
        "created_at": _NOW.isoformat(),
        "updated_at": _NOW.isoformat(),
    }


def _make_manifest_row(definition: dict | None = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "branch_id": str(_BRANCH_ID),
        "definition": definition or _MINIMAL_MANIFEST,
        "run_status": "pending",
        "updated_at": _NOW.isoformat(),
    }


def _branch_url(suffix: str = "") -> str:
    return f"/v1/projects/{_PROJECT_ID}/branches{suffix}"


@pytest.fixture(scope="module")
def app():
    return make_app(ADMIN_USER)


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── Auth ──────────────────────────────────────────────────────────────────────


class TestBranchesAuth:
    @pytest.mark.parametrize(
        "method,path_suffix",
        [
            pytest.param("GET", "", id="list"),
            pytest.param("POST", "", id="create"),
            pytest.param("GET", "/main", id="get"),
            pytest.param("PUT", "/main", id="update"),
            pytest.param("DELETE", "/feature-x", id="delete"),
            pytest.param("GET", "/main/manifest", id="get_manifest"),
        ],
    )
    def test_missing_token_returns_401(self, method, path_suffix):
        app = create_app(settings=_SETTINGS)
        app.dependency_overrides[_get_auth_settings] = lambda: _FAKE_AUTH
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.request(method, _branch_url(path_suffix), json={})
        assert r.status_code == 401


# ── POST /branches ────────────────────────────────────────────────────────────


class TestCreateBranch:
    def test_create_as_admin_returns_201(self, client):
        row = _make_branch_row(name="feature-x")
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=None),
            patch("wurzel.api.routes.branch.router.db_create_branch", new_callable=AsyncMock, return_value=row),
        ):
            r = client.post(_branch_url(), json={"name": "feature-x"})
        assert r.status_code == 201

    def test_create_returns_branch_fields(self, client):
        row = _make_branch_row(name="feature-y")
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=None),
            patch("wurzel.api.routes.branch.router.db_create_branch", new_callable=AsyncMock, return_value=row),
        ):
            r = client.post(_branch_url(), json={"name": "feature-y"})
        body = r.json()
        assert body["name"] == "feature-y"
        assert "id" in body
        assert "project_id" in body

    def test_create_reserved_main_returns_409(self, client):
        with patch(
            "wurzel.api.backends.supabase.client.get_project_role_from_db",
            new_callable=AsyncMock,
            return_value=ProjectRole.ADMIN,
        ):
            r = client.post(_branch_url(), json={"name": "main"})
        assert r.status_code == 409

    def test_create_duplicate_branch_returns_409(self, client):
        existing = _make_branch_row(name="feature-x")
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=existing),
        ):
            r = client.post(_branch_url(), json={"name": "feature-x"})
        assert r.status_code == 409

    def test_create_non_member_returns_404(self, client):
        with patch(
            "wurzel.api.backends.supabase.client.get_project_role_from_db",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.post(_branch_url(), json={"name": "feature-x"})
        assert r.status_code == 404

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param({"name": ""}, id="empty_name"),
            pytest.param({"name": "UPPERCASE"}, id="uppercase_fails_pattern"),
            pytest.param({"name": "-starts-with-dash"}, id="leading_dash"),
            pytest.param({}, id="missing_name"),
        ],
    )
    def test_create_invalid_name_returns_422(self, client, body):
        with patch(
            "wurzel.api.backends.supabase.client.get_project_role_from_db",
            new_callable=AsyncMock,
            return_value=ProjectRole.ADMIN,
        ):
            r = client.post(_branch_url(), json=body)
        assert r.status_code == 422

    @pytest.mark.parametrize("role_client", ["member_client", "secret_editor_client", "viewer_client"])
    def test_create_non_admin_returns_403(self, role_client, request):
        r = request.getfixturevalue(role_client).post(_branch_url(), json={"name": "feature-new"})
        assert r.status_code == 403


# ── GET /branches ─────────────────────────────────────────────────────────────


class TestListBranches:
    def test_list_returns_branch_list(self, client):
        rows = [_make_branch_row("main"), _make_branch_row("feature-x")]
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.branch.router.db_list_branches", new_callable=AsyncMock, return_value=rows),
        ):
            r = client.get(_branch_url())
        body = r.json()
        assert isinstance(body, list)
        assert len(body) == 2

    def test_list_non_member_returns_404(self, client):
        with patch(
            "wurzel.api.backends.supabase.client.get_project_role_from_db",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.get(_branch_url())
        assert r.status_code == 404

    @pytest.mark.parametrize("role_client", ["admin_client", "member_client", "secret_editor_client", "viewer_client"])
    def test_list_any_role_returns_200(self, role_client, request):
        with patch("wurzel.api.routes.branch.router.db_list_branches", new_callable=AsyncMock, return_value=[]):
            r = request.getfixturevalue(role_client).get(_branch_url())
        assert r.status_code == 200


# ── GET /branches/{branch_name} ───────────────────────────────────────────────


class TestGetBranch:
    def test_get_existing_branch_returns_200(self, client):
        row = _make_branch_row("main", is_protected=True)
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.VIEWER,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=row),
        ):
            r = client.get(_branch_url("/main"))
        assert r.status_code == 200
        assert r.json()["name"] == "main"

    def test_get_missing_branch_returns_404(self, client):
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=None),
        ):
            r = client.get(_branch_url("/nonexistent"))
        assert r.status_code == 404

    def test_get_non_member_returns_404(self, client):
        with patch(
            "wurzel.api.backends.supabase.client.get_project_role_from_db",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.get(_branch_url("/main"))
        assert r.status_code == 404

    @pytest.mark.parametrize("role_client", ["admin_client", "member_client", "secret_editor_client", "viewer_client"])
    def test_get_any_role_returns_200(self, role_client, request):
        row = _make_branch_row("feature-x")
        with patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=row):
            r = request.getfixturevalue(role_client).get(_branch_url("/feature-x"))
        assert r.status_code == 200


# ── PUT /branches/{branch_name} ───────────────────────────────────────────────


class TestUpdateBranch:
    def test_update_as_admin_returns_200(self, client):
        row = _make_branch_row("feature-x")
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=row),
            patch("wurzel.api.routes.branch.router.db_update_branch", new_callable=AsyncMock, return_value=row),
        ):
            r = client.put(_branch_url("/feature-x"), json={})
        assert r.status_code == 200

    def test_update_missing_branch_returns_404(self, client):
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=None),
        ):
            r = client.put(_branch_url("/ghost"), json={})
        assert r.status_code == 404

    @pytest.mark.parametrize("role_client", ["member_client", "secret_editor_client", "viewer_client"])
    def test_update_non_admin_returns_403(self, role_client, request):
        r = request.getfixturevalue(role_client).put(_branch_url("/feature-x"), json={})
        assert r.status_code == 403


# ── DELETE /branches/{branch_name} ────────────────────────────────────────────


class TestDeleteBranch:
    def test_delete_as_admin_returns_204(self, client):
        row = _make_branch_row("feature-x")
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=row),
            patch("wurzel.api.routes.branch.router.db_delete_branch", new_callable=AsyncMock),
        ):
            r = client.delete(_branch_url("/feature-x"))
        assert r.status_code == 204

    def test_delete_main_branch_returns_409(self, client):
        with patch(
            "wurzel.api.backends.supabase.client.get_project_role_from_db",
            new_callable=AsyncMock,
            return_value=ProjectRole.ADMIN,
        ):
            r = client.delete(_branch_url("/main"))
        assert r.status_code == 409

    def test_delete_missing_branch_returns_404(self, client):
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=None),
        ):
            r = client.delete(_branch_url("/nonexistent"))
        assert r.status_code == 404

    @pytest.mark.parametrize("role_client", ["member_client", "secret_editor_client", "viewer_client"])
    def test_delete_non_admin_returns_403(self, role_client, request):
        r = request.getfixturevalue(role_client).delete(_branch_url("/feature-x"))
        assert r.status_code == 403


# ── POST /branches/{branch_name}/protect ──────────────────────────────────────


class TestProtectBranch:
    def test_protect_branch_as_admin_returns_200(self, client):
        row = _make_branch_row("feature-x", is_protected=False)
        protected_row = _make_branch_row("feature-x", is_protected=True)
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=row),
            patch("wurzel.api.routes.branch.router.db_update_branch", new_callable=AsyncMock, return_value=protected_row),
        ):
            r = client.post(_branch_url("/feature-x/protect"), json={"is_protected": True})
        assert r.status_code == 200
        assert r.json()["is_protected"] is True

    def test_unprotect_main_returns_409(self, client):
        with patch(
            "wurzel.api.backends.supabase.client.get_project_role_from_db",
            new_callable=AsyncMock,
            return_value=ProjectRole.ADMIN,
        ):
            r = client.post(_branch_url("/main/protect"), json={"is_protected": False})
        assert r.status_code == 409

    @pytest.mark.parametrize("role_client", ["member_client", "secret_editor_client", "viewer_client"])
    def test_protect_non_admin_returns_403(self, role_client, request):
        r = request.getfixturevalue(role_client).post(_branch_url("/feature-x/protect"), json={"is_protected": True})
        assert r.status_code == 403


# ── GET /branches/{branch_name}/manifest ──────────────────────────────────────


class TestGetBranchManifest:
    def test_get_manifest_returns_200(self, client):
        branch_row = _make_branch_row("feature-x")
        manifest_row = _make_manifest_row()
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.VIEWER,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=branch_row),
            patch("wurzel.api.routes.branch.router.db_get_branch_manifest", new_callable=AsyncMock, return_value=manifest_row),
        ):
            r = client.get(_branch_url("/feature-x/manifest"))
        assert r.status_code == 200

    def test_get_manifest_returns_branch_fields(self, client):
        branch_row = _make_branch_row("feature-x")
        manifest_row = _make_manifest_row()
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.VIEWER,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=branch_row),
            patch("wurzel.api.routes.branch.router.db_get_branch_manifest", new_callable=AsyncMock, return_value=manifest_row),
        ):
            r = client.get(_branch_url("/feature-x/manifest"))
        body = r.json()
        assert body["branch_name"] == "feature-x"
        assert "branch_id" in body

    def test_get_manifest_no_manifest_stored(self, client):
        """Branch exists but has no manifest yet — returns BranchManifest with null definition."""
        branch_row = _make_branch_row("feature-x")
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.VIEWER,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=branch_row),
            patch("wurzel.api.routes.branch.router.db_get_branch_manifest", new_callable=AsyncMock, return_value=None),
        ):
            r = client.get(_branch_url("/feature-x/manifest"))
        assert r.status_code == 200
        assert r.json()["definition"] is None

    def test_get_manifest_missing_branch_returns_404(self, client):
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=None),
        ):
            r = client.get(_branch_url("/ghost/manifest"))
        assert r.status_code == 404

    def test_get_manifest_non_member_returns_404(self, client):
        with patch(
            "wurzel.api.backends.supabase.client.get_project_role_from_db",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.get(_branch_url("/feature-x/manifest"))
        assert r.status_code == 404

    @pytest.mark.parametrize("role_client", ["admin_client", "member_client", "secret_editor_client", "viewer_client"])
    def test_get_manifest_any_role_returns_200(self, role_client, request):
        branch_row = _make_branch_row("feature-x")
        manifest_row = _make_manifest_row()
        with (
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=branch_row),
            patch("wurzel.api.routes.branch.router.db_get_branch_manifest", new_callable=AsyncMock, return_value=manifest_row),
        ):
            r = request.getfixturevalue(role_client).get(_branch_url("/feature-x/manifest"))
        assert r.status_code == 200


# ── PUT /branches/{branch_name}/manifest ─────────────────────────────────────


class TestSetBranchManifest:
    def test_set_manifest_as_member_returns_200(self, client):
        branch_row = _make_branch_row("feature-x")
        manifest_row = _make_manifest_row()
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.MEMBER,
            ),
            patch(
                "wurzel.api.backends.supabase.client.get_branch_protection",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=branch_row),
            patch("wurzel.api.routes.branch.router.db_upsert_branch_manifest", new_callable=AsyncMock, return_value=manifest_row),
        ):
            r = client.put(_branch_url("/feature-x/manifest"), json=_MINIMAL_MANIFEST)
        assert r.status_code == 200

    def test_set_manifest_on_main_returns_403(self, client):
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch(
                "wurzel.api.backends.supabase.client.get_branch_protection",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            r = client.put(_branch_url("/main/manifest"), json=_MINIMAL_MANIFEST)
        assert r.status_code == 403

    def test_set_manifest_missing_branch_returns_404(self, client):
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.MEMBER,
            ),
            patch(
                "wurzel.api.backends.supabase.client.get_branch_protection",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=None),
        ):
            r = client.put(_branch_url("/ghost/manifest"), json=_MINIMAL_MANIFEST)
        assert r.status_code == 404

    def test_set_manifest_non_member_returns_404(self, client):
        with patch(
            "wurzel.api.backends.supabase.client.get_project_role_from_db",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.put(_branch_url("/feature-x/manifest"), json=_MINIMAL_MANIFEST)
        assert r.status_code == 404

    def test_set_manifest_invalid_body_returns_422(self, client):
        r = client.put(_branch_url("/feature-x/manifest"), json={"not": "a manifest"})
        assert r.status_code == 422

    @pytest.mark.parametrize("role_client", ["admin_client", "member_client"])
    def test_set_manifest_write_role_unprotected_returns_200(self, role_client, request):
        branch_row = _make_branch_row("feature-x")
        manifest_row = _make_manifest_row()
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_branch_protection",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=branch_row),
            patch("wurzel.api.routes.branch.router.db_upsert_branch_manifest", new_callable=AsyncMock, return_value=manifest_row),
        ):
            r = request.getfixturevalue(role_client).put(_branch_url("/feature-x/manifest"), json=_MINIMAL_MANIFEST)
        assert r.status_code == 200

    @pytest.mark.parametrize("role_client", ["secret_editor_client", "viewer_client"])
    def test_set_manifest_read_role_unprotected_returns_403(self, role_client, request):
        with patch(
            "wurzel.api.backends.supabase.client.get_branch_protection",
            new_callable=AsyncMock,
            return_value=False,
        ):
            r = request.getfixturevalue(role_client).put(_branch_url("/feature-x/manifest"), json=_MINIMAL_MANIFEST)
        assert r.status_code == 403

    def test_set_manifest_protected_as_admin_returns_200(self, admin_client):
        branch_row = _make_branch_row("feature-x", is_protected=True)
        manifest_row = _make_manifest_row()
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_branch_protection",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=branch_row),
            patch("wurzel.api.routes.branch.router.db_upsert_branch_manifest", new_callable=AsyncMock, return_value=manifest_row),
        ):
            r = admin_client.put(_branch_url("/feature-x/manifest"), json=_MINIMAL_MANIFEST)
        assert r.status_code == 200

    @pytest.mark.parametrize("role_client", ["member_client", "secret_editor_client", "viewer_client"])
    def test_set_manifest_protected_non_admin_returns_403(self, role_client, request):
        with patch(
            "wurzel.api.backends.supabase.client.get_branch_protection",
            new_callable=AsyncMock,
            return_value=True,
        ):
            r = request.getfixturevalue(role_client).put(_branch_url("/feature-x/manifest"), json=_MINIMAL_MANIFEST)
        assert r.status_code == 403


# ── POST /branches/{branch_name}/manifest/submit ──────────────────────────────


class TestSubmitBranchManifest:
    def test_submit_as_member_returns_202(self, client):
        branch_row = _make_branch_row("feature-x")
        manifest_row = _make_manifest_row()
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.MEMBER,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=branch_row),
            patch("wurzel.api.routes.branch.router.db_get_branch_manifest", new_callable=AsyncMock, return_value=manifest_row),
        ):
            r = client.post(_branch_url("/feature-x/manifest/submit"))
        assert r.status_code == 202

    def test_submit_returns_pending_status(self, client):
        branch_row = _make_branch_row("feature-x")
        manifest_row = _make_manifest_row()
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.MEMBER,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=branch_row),
            patch("wurzel.api.routes.branch.router.db_get_branch_manifest", new_callable=AsyncMock, return_value=manifest_row),
        ):
            r = client.post(_branch_url("/feature-x/manifest/submit"))
        assert r.json()["run_status"] == "pending"

    def test_submit_no_manifest_returns_409(self, client):
        branch_row = _make_branch_row("feature-x")
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.MEMBER,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=branch_row),
            patch("wurzel.api.routes.branch.router.db_get_branch_manifest", new_callable=AsyncMock, return_value=None),
        ):
            r = client.post(_branch_url("/feature-x/manifest/submit"))
        assert r.status_code == 409

    def test_submit_as_viewer_returns_403(self, client):
        with patch(
            "wurzel.api.backends.supabase.client.get_project_role_from_db",
            new_callable=AsyncMock,
            return_value=ProjectRole.VIEWER,
        ):
            r = client.post(_branch_url("/feature-x/manifest/submit"))
        assert r.status_code == 403


# ── GET /branches/{branch_name}/diff/{target_branch} ─────────────────────────


class TestDiffBranches:
    def test_diff_returns_200(self, client):
        source_row = _make_branch_row("feature-x", branch_id=_BRANCH_ID)
        target_row = _make_branch_row("main", branch_id=_BRANCH_ID_2)
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.VIEWER,
            ),
            patch(
                "wurzel.api.routes.branch.router.db_get_branch",
                new_callable=AsyncMock,
                side_effect=[source_row, target_row],
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch_manifest", new_callable=AsyncMock, return_value=None),
        ):
            r = client.get(_branch_url("/feature-x/diff/main"))
        assert r.status_code == 200

    def test_diff_response_has_expected_fields(self, client):
        source_row = _make_branch_row("feature-x", branch_id=_BRANCH_ID)
        target_row = _make_branch_row("main", branch_id=_BRANCH_ID_2)
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.VIEWER,
            ),
            patch(
                "wurzel.api.routes.branch.router.db_get_branch",
                new_callable=AsyncMock,
                side_effect=[source_row, target_row],
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch_manifest", new_callable=AsyncMock, return_value=None),
        ):
            r = client.get(_branch_url("/feature-x/diff/main"))
        body = r.json()
        assert "source_branch" in body
        assert "target_branch" in body
        assert "diffs" in body
        assert "has_conflicts" in body

    def test_diff_both_have_manifest_shows_changes(self, client):
        source_row = _make_branch_row("feature-x", branch_id=_BRANCH_ID)
        target_row = _make_branch_row("main", branch_id=_BRANCH_ID_2)
        source_manifest = _make_manifest_row()
        target_manifest = {
            **_make_manifest_row(),
            "definition": {
                **_MINIMAL_MANIFEST,
                "metadata": {"name": "different-pipeline"},
            },
        }
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.VIEWER,
            ),
            patch(
                "wurzel.api.routes.branch.router.db_get_branch",
                new_callable=AsyncMock,
                side_effect=[source_row, target_row],
            ),
            patch(
                "wurzel.api.routes.branch.router.db_get_branch_manifest",
                new_callable=AsyncMock,
                side_effect=[source_manifest, target_manifest],
            ),
        ):
            r = client.get(_branch_url("/feature-x/diff/main"))
        assert r.status_code == 200
        body = r.json()
        assert len(body["diffs"]) > 0

    def test_diff_missing_source_branch_returns_404(self, client):
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.VIEWER,
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch", new_callable=AsyncMock, return_value=None),
        ):
            r = client.get(_branch_url("/ghost/diff/main"))
        assert r.status_code == 404

    def test_diff_non_member_returns_404(self, client):
        with patch(
            "wurzel.api.backends.supabase.client.get_project_role_from_db",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.get(_branch_url("/feature-x/diff/main"))
        assert r.status_code == 404


# ── POST /branches/{branch_name}/promote/{target_branch} ──────────────────────


class TestPromoteBranch:
    def test_promote_as_admin_returns_200(self, client):
        source_row = _make_branch_row("feature-x", branch_id=_BRANCH_ID)
        target_row = _make_branch_row("staging", branch_id=_BRANCH_ID_2)
        source_manifest = _make_manifest_row()
        upserted = {**source_manifest, "id": str(uuid.uuid4())}
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch(
                "wurzel.api.backends.supabase.client.get_branch_protection",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "wurzel.api.routes.branch.router.db_get_branch",
                new_callable=AsyncMock,
                side_effect=[source_row, target_row],
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch_manifest", new_callable=AsyncMock, return_value=source_manifest),
            patch("wurzel.api.routes.branch.router.db_upsert_branch_manifest", new_callable=AsyncMock, return_value=upserted),
        ):
            r = client.post(_branch_url("/feature-x/promote/staging"))
        assert r.status_code == 200

    def test_promote_response_has_expected_fields(self, client):
        source_row = _make_branch_row("feature-x", branch_id=_BRANCH_ID)
        target_row = _make_branch_row("staging", branch_id=_BRANCH_ID_2)
        source_manifest = _make_manifest_row()
        upserted = {**source_manifest, "id": str(uuid.uuid4())}
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch(
                "wurzel.api.backends.supabase.client.get_branch_protection",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "wurzel.api.routes.branch.router.db_get_branch",
                new_callable=AsyncMock,
                side_effect=[source_row, target_row],
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch_manifest", new_callable=AsyncMock, return_value=source_manifest),
            patch("wurzel.api.routes.branch.router.db_upsert_branch_manifest", new_callable=AsyncMock, return_value=upserted),
        ):
            r = client.post(_branch_url("/feature-x/promote/staging"))
        body = r.json()
        assert body["source_branch"] == "feature-x"
        assert body["target_branch"] == "staging"
        assert "manifest_id" in body

    def test_promote_source_has_no_manifest_returns_409(self, client):
        source_row = _make_branch_row("feature-x", branch_id=_BRANCH_ID)
        target_row = _make_branch_row("staging", branch_id=_BRANCH_ID_2)
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch(
                "wurzel.api.backends.supabase.client.get_branch_protection",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "wurzel.api.routes.branch.router.db_get_branch",
                new_callable=AsyncMock,
                side_effect=[source_row, target_row],
            ),
            patch("wurzel.api.routes.branch.router.db_get_branch_manifest", new_callable=AsyncMock, return_value=None),
        ):
            r = client.post(_branch_url("/feature-x/promote/staging"))
        assert r.status_code == 409

    def test_promote_to_main_returns_403(self, client):
        """Promoting to main is blocked by the branch-write guard."""
        with (
            patch(
                "wurzel.api.backends.supabase.client.get_project_role_from_db",
                new_callable=AsyncMock,
                return_value=ProjectRole.ADMIN,
            ),
            patch(
                "wurzel.api.backends.supabase.client.get_branch_protection",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            r = client.post(_branch_url("/feature-x/promote/main"))
        assert r.status_code == 403
