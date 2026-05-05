# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for /v1/projects/{project_id}/steps routes."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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

_ADMIN_USER = UserClaims(sub="uid-admin", email="admin@example.com", raw={})
_VIEWER_USER = UserClaims(sub="uid-viewer", email="viewer@example.com", raw={})

_ROLE_DB_PATH = "wurzel.api.backends.supabase.client.get_project_role_from_db"


def _make_client(user: UserClaims, role: ProjectRole | None) -> tuple:
    app = create_app(settings=_SETTINGS, otel_settings=_OTEL)
    app.dependency_overrides[_verify_jwt] = lambda: user
    patcher = patch(_ROLE_DB_PATH, new_callable=AsyncMock, return_value=role)
    patcher.start()
    client = TestClient(app, raise_server_exceptions=False)
    client.__enter__()
    return client, patcher


class TestListProjectSteps:
    def test_any_member_can_list_steps(self):
        from wurzel.api.routes.steps.data import StepListResponse

        for role in (ProjectRole.ADMIN, ProjectRole.MEMBER, ProjectRole.VIEWER):
            client, patcher = _make_client(_ADMIN_USER, role)
            try:
                mock_response = StepListResponse(steps=[], total=0, package="*")
                mock_settings = MagicMock()
                mock_settings.PACKAGES_DIR = Path("/tmp")

                with (
                    patch("wurzel.api.routes.project_steps.router._get_pkg_settings", return_value=mock_settings),
                    patch("wurzel.api.routes.project_steps.router.discover_steps_for_project", return_value=mock_response),
                ):
                    resp = client.get(f"/v1/projects/{_PROJECT_ID}/steps")
                assert resp.status_code == 200
            finally:
                client.__exit__(None, None, None)
                patcher.stop()

    def test_non_member_gets_404(self):
        client, patcher = _make_client(_ADMIN_USER, None)
        try:
            resp = client.get(f"/v1/projects/{_PROJECT_ID}/steps")
            assert resp.status_code == 404
        finally:
            client.__exit__(None, None, None)
            patcher.stop()

    def test_includes_global_and_project_steps(self):
        """discover_steps_for_project is called with correct project_id and extra_path."""
        from wurzel.api.routes.steps.data import StepListResponse

        client, patcher = _make_client(_ADMIN_USER, ProjectRole.ADMIN)
        try:
            captured_args = {}

            def fake_discover(project_id, extra_path, cache, refresh=False):
                captured_args["project_id"] = project_id
                captured_args["extra_path"] = extra_path
                return StepListResponse(steps=[], total=0, package="*")

            mock_settings = MagicMock()
            mock_settings.PACKAGES_DIR = Path("/fake/packages")

            with (
                patch("wurzel.api.routes.project_steps.router._get_pkg_settings", return_value=mock_settings),
                patch("wurzel.api.routes.project_steps.router.discover_steps_for_project", side_effect=fake_discover),
            ):
                resp = client.get(f"/v1/projects/{_PROJECT_ID}/steps")

            assert resp.status_code == 200
            assert captured_args["project_id"] == str(_PROJECT_ID)
        finally:
            client.__exit__(None, None, None)
            patcher.stop()


class TestDiscoverStepsForProject:
    def test_merges_global_and_project_steps(self, tmp_path):
        from wurzel.api.routes.steps.data import StepListResponse, StepSummary
        from wurzel.api.routes.steps.service import StepListCache, discover_steps_for_project

        global_step = StepSummary(
            class_path="myapp.GlobalStep",
            name="GlobalStep",
            module="myapp",
            input_type=None,
            output_type="list[str]",
        )
        global_response = StepListResponse(steps=[global_step], total=1, package="*")

        project_step_path = "mypkg.MyProjectStep"

        cache = StepListCache()
        with (
            patch("wurzel.api.routes.steps.service.discover_steps", return_value=global_response),
            patch("wurzel.api.routes.steps.service.scan_path_for_typed_steps", return_value=[project_step_path]),
            patch("wurzel.api.routes.steps.service._safe_io_types", return_value=(None, "str")),
        ):
            result = discover_steps_for_project(str(uuid.uuid4()), tmp_path, cache)

        paths = {s.class_path for s in result.steps}
        assert "myapp.GlobalStep" in paths
        assert project_step_path in paths

    def test_handles_missing_extra_path(self, tmp_path):
        from wurzel.api.routes.steps.data import StepListResponse
        from wurzel.api.routes.steps.service import StepListCache, discover_steps_for_project

        global_response = StepListResponse(steps=[], total=0, package="*")
        nonexistent = tmp_path / "does_not_exist"

        cache = StepListCache()
        with patch("wurzel.api.routes.steps.service.discover_steps", return_value=global_response):
            result = discover_steps_for_project(str(uuid.uuid4()), nonexistent, cache)

        assert result.total == 0


class TestProjectStepsRouterHelpers:
    def test_get_pkg_settings_constructs_settings(self):
        from wurzel.api.routes.project_steps import router as module

        sentinel = object()
        with patch("wurzel.api.routes.project_steps.router.PackageManagerSettings", return_value=sentinel):
            assert module._get_pkg_settings() is sentinel
