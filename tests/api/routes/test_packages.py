# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for /v1/projects/{project_id}/packages and .../secrets routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

from fastapi.testclient import TestClient  # noqa: E402

from wurzel.api.app import create_app  # noqa: E402
from wurzel.api.auth.jwt import UserClaims, _verify_jwt  # noqa: E402
from wurzel.api.middleware.otel import OTELSettings  # noqa: E402
from wurzel.api.routes.member.data import ProjectRole  # noqa: E402
from wurzel.api.settings import APISettings  # noqa: E402

_SETTINGS = APISettings(API_KEY="test-key")
_OTEL = OTELSettings(ENABLED=False)
_PROJECT_ID = uuid.uuid4()
_PACKAGE_ID = uuid.uuid4()
_NOW = datetime(2025, 1, 1, 12, 0, 0).isoformat()

_ADMIN_USER = UserClaims(sub="uid-admin", email="admin@example.com", raw={})
_MEMBER_USER = UserClaims(sub="uid-member", email="member@example.com", raw={})
_VIEWER_USER = UserClaims(sub="uid-viewer", email="viewer@example.com", raw={})

_ROLE_DB_PATH = "wurzel.api.backends.supabase.client.get_project_role_from_db"

_PACKAGE_ROW = {
    "id": str(_PACKAGE_ID),
    "project_id": str(_PROJECT_ID),
    "package_spec": "mypkg==1.0.0",
    "index_secret_name": None,
    "status": "pending",
    "error": None,
    "installed_at": None,
    "created_at": _NOW,
    "created_by": "uid-admin",
}

_SECRET_ROW = {
    "id": str(uuid.uuid4()),
    "name": "my_index",
    "created_at": _NOW,
    "updated_at": _NOW,
}


def _make_client(user: UserClaims, role: ProjectRole | None) -> TestClient:
    app = create_app(settings=_SETTINGS, otel_settings=_OTEL)
    app.dependency_overrides[_verify_jwt] = lambda: user
    patcher = patch(_ROLE_DB_PATH, new_callable=AsyncMock, return_value=role)
    patcher.start()
    client = TestClient(app, raise_server_exceptions=False)
    client.__enter__()
    return client, patcher


# ── Packages ──────────────────────────────────────────────────────────────────


class TestAddPackage:
    def test_admin_can_add_package(self):
        client, patcher = _make_client(_ADMIN_USER, ProjectRole.ADMIN)
        try:
            with (
                patch("wurzel.api.routes.packages.router.db_add_project_package", new_callable=AsyncMock, return_value=_PACKAGE_ROW),
                patch(
                    "wurzel.api.routes.packages.router.db_get_active_project_package",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
                patch("wurzel.api.package_manager.background.perform_install"),
                patch("wurzel.api.routes.packages.router._get_pkg_settings"),
            ):
                resp = client.post(
                    f"/v1/projects/{_PROJECT_ID}/packages",
                    json={"package_spec": "mypkg==1.0.0"},
                )
            assert resp.status_code == 202
            data = resp.json()
            assert data["package_spec"] == "mypkg==1.0.0"
            assert data["status"] == "pending"
        finally:
            client.__exit__(None, None, None)
            patcher.stop()

    def test_member_cannot_add_package(self):
        client, patcher = _make_client(_MEMBER_USER, ProjectRole.MEMBER)
        try:
            resp = client.post(
                f"/v1/projects/{_PROJECT_ID}/packages",
                json={"package_spec": "mypkg==1.0.0"},
            )
            assert resp.status_code == 403
        finally:
            client.__exit__(None, None, None)
            patcher.stop()

    def test_viewer_cannot_add_package(self):
        client, patcher = _make_client(_VIEWER_USER, ProjectRole.VIEWER)
        try:
            resp = client.post(
                f"/v1/projects/{_PROJECT_ID}/packages",
                json={"package_spec": "mypkg==1.0.0"},
            )
            assert resp.status_code == 403
        finally:
            client.__exit__(None, None, None)
            patcher.stop()

    def test_invalid_package_spec_returns_422(self):
        client, patcher = _make_client(_ADMIN_USER, ProjectRole.ADMIN)
        try:
            resp = client.post(
                f"/v1/projects/{_PROJECT_ID}/packages",
                json={"package_spec": "pkg; rm -rf /"},
            )
            assert resp.status_code == 422
        finally:
            client.__exit__(None, None, None)
            patcher.stop()

    def test_package_manager_not_configured_returns_503(self):
        from pydantic import ValidationError

        client, patcher = _make_client(_ADMIN_USER, ProjectRole.ADMIN)
        try:
            with patch(
                "wurzel.api.routes.packages.router._get_pkg_settings",
                side_effect=ValidationError.from_exception_data("PackageManagerSettings", []),
            ):
                resp = client.post(
                    f"/v1/projects/{_PROJECT_ID}/packages",
                    json={"package_spec": "mypkg==1.0.0"},
                )
            assert resp.status_code == 503
        finally:
            client.__exit__(None, None, None)
            patcher.stop()

    def test_duplicate_active_package_returns_409(self):
        existing_row = {
            **_PACKAGE_ROW,
            "status": "installing",
        }
        client, patcher = _make_client(_ADMIN_USER, ProjectRole.ADMIN)
        try:
            with (
                patch("wurzel.api.routes.packages.router._get_pkg_settings"),
                patch(
                    "wurzel.api.routes.packages.router.db_get_active_project_package",
                    new_callable=AsyncMock,
                    return_value=existing_row,
                ),
                patch("wurzel.api.routes.packages.router.db_add_project_package", new_callable=AsyncMock) as add_mock,
            ):
                resp = client.post(
                    f"/v1/projects/{_PROJECT_ID}/packages",
                    json={"package_spec": "mypkg==1.0.0"},
                )
            assert resp.status_code == 409
            add_mock.assert_not_awaited()
        finally:
            client.__exit__(None, None, None)
            patcher.stop()


class TestListPackages:
    def test_any_member_can_list(self):
        for role in (ProjectRole.ADMIN, ProjectRole.MEMBER, ProjectRole.VIEWER):
            client, patcher = _make_client(_MEMBER_USER, role)
            try:
                with patch(
                    "wurzel.api.routes.packages.router.db_list_project_packages", new_callable=AsyncMock, return_value=[_PACKAGE_ROW]
                ):
                    resp = client.get(f"/v1/projects/{_PROJECT_ID}/packages")
                assert resp.status_code == 200
                assert isinstance(resp.json(), list)
            finally:
                client.__exit__(None, None, None)
                patcher.stop()


class TestDeletePackage:
    def test_admin_can_delete(self):
        client, patcher = _make_client(_ADMIN_USER, ProjectRole.ADMIN)
        try:
            with patch("wurzel.api.routes.packages.router.db_delete_project_package", new_callable=AsyncMock):
                resp = client.delete(f"/v1/projects/{_PROJECT_ID}/packages/{_PACKAGE_ID}")
            assert resp.status_code == 204
        finally:
            client.__exit__(None, None, None)
            patcher.stop()

    def test_member_cannot_delete(self):
        client, patcher = _make_client(_MEMBER_USER, ProjectRole.MEMBER)
        try:
            resp = client.delete(f"/v1/projects/{_PROJECT_ID}/packages/{_PACKAGE_ID}")
            assert resp.status_code == 403
        finally:
            client.__exit__(None, None, None)
            patcher.stop()


# ── Secrets ───────────────────────────────────────────────────────────────────


class TestSecretRoutes:
    def test_admin_can_upsert_secret(self):
        client, patcher = _make_client(_ADMIN_USER, ProjectRole.ADMIN)
        try:
            with patch("wurzel.api.routes.packages.router.db_upsert_project_secret", new_callable=AsyncMock, return_value=_SECRET_ROW):
                resp = client.put(
                    f"/v1/projects/{_PROJECT_ID}/packages/secrets/my_index",
                    json={"value": "https://user:pass@pypi.example.com/simple"},  # pragma: allowlist secret
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "my_index"
            # Value must NOT be in the response
            assert "value" not in data

        finally:
            client.__exit__(None, None, None)
            patcher.stop()

    def test_member_cannot_upsert_secret(self):
        client, patcher = _make_client(_MEMBER_USER, ProjectRole.MEMBER)
        try:
            resp = client.put(
                f"/v1/projects/{_PROJECT_ID}/packages/secrets/my_index",
                json={"value": "secret"},
            )
            assert resp.status_code == 403
        finally:
            client.__exit__(None, None, None)
            patcher.stop()

    def test_list_secrets_excludes_values(self):
        client, patcher = _make_client(_ADMIN_USER, ProjectRole.ADMIN)
        try:
            with patch("wurzel.api.routes.packages.router.db_list_project_secrets", new_callable=AsyncMock, return_value=[_SECRET_ROW]):
                resp = client.get(f"/v1/projects/{_PROJECT_ID}/packages/secrets")
            assert resp.status_code == 200
            for item in resp.json():
                assert "value" not in item
        finally:
            client.__exit__(None, None, None)
            patcher.stop()

    def test_admin_can_delete_secret(self):
        client, patcher = _make_client(_ADMIN_USER, ProjectRole.ADMIN)
        try:
            with patch("wurzel.api.routes.packages.router.db_delete_project_secret", new_callable=AsyncMock):
                resp = client.delete(f"/v1/projects/{_PROJECT_ID}/packages/secrets/my_index")
            assert resp.status_code == 204
        finally:
            client.__exit__(None, None, None)
            patcher.stop()


class TestPackageRouterHelpers:
    def test_get_pkg_settings_constructs_settings(self):
        from wurzel.api.routes.packages import router as module

        sentinel = object()
        with patch("wurzel.api.routes.packages.router.PackageManagerSettings", return_value=sentinel):
            assert module._get_pkg_settings() is sentinel
