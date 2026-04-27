# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Shared fixtures for /v1/projects/* route tests.

Provides:
- ``app`` / ``client`` — module-scoped, ADMIN_USER JWT, no role patch (existing
  tests supply inline role patches where needed).
- ``admin_client`` / ``member_client`` / ``secret_editor_client`` /
  ``viewer_client`` / ``no_role_client`` — function-scoped clients that both
  bypass JWT *and* pre-patch ``get_project_role_from_db`` with the
  corresponding ``ProjectRole`` (or ``None`` for non-member).  Use these for
  permission-coverage tests so you don't have to repeat the role patch in
  every test body.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

from fastapi.testclient import TestClient  # noqa: E402

from wurzel.api.app import create_app  # noqa: E402
from wurzel.api.auth.jwt import UserClaims, _verify_jwt  # noqa: E402
from wurzel.api.middleware.otel import OTELSettings  # noqa: E402
from wurzel.api.routes.member.data import ProjectRole  # noqa: E402
from wurzel.api.settings import APISettings  # noqa: E402

# ── Shared constants ──────────────────────────────────────────────────────────

SETTINGS = APISettings(API_KEY="test-key")
_OTEL_DISABLED = OTELSettings(ENABLED=False)

_ROLE_DB_PATH = "wurzel.api.backends.supabase.client.get_project_role_from_db"

# One user per role (sub values are arbitrary but distinct)
ADMIN_USER = UserClaims(sub="uid-admin", email="admin@example.com", raw={})
MEMBER_USER = UserClaims(sub="uid-member", email="member@example.com", raw={})
SECRET_EDITOR_USER = UserClaims(sub="uid-secret-editor", email="secret-editor@example.com", raw={})
VIEWER_USER = UserClaims(sub="uid-viewer", email="viewer@example.com", raw={})
NO_ROLE_USER = UserClaims(sub="uid-no-role", email="norole@example.com", raw={})


# ── Internal helpers ──────────────────────────────────────────────────────────


def make_app(user: UserClaims):
    """Return a fresh FastAPI app with JWT bypassed to *user*."""
    _app = create_app(settings=SETTINGS, otel_settings=_OTEL_DISABLED)
    _app.dependency_overrides[_verify_jwt] = lambda: user
    return _app


def _role_client(user: UserClaims, role: ProjectRole | None):
    """Yield a TestClient for *user* with ``get_project_role_from_db`` patched to *role*."""
    patcher = patch(_ROLE_DB_PATH, new_callable=AsyncMock, return_value=role)
    patcher.start()
    try:
        with TestClient(make_app(user), raise_server_exceptions=False) as c:
            yield c
    finally:
        patcher.stop()


# ── Module-scoped default fixtures (used by existing happy-path tests) ────────


@pytest.fixture(scope="module")
def jwt_app():
    """FastAPI app with JWT overridden to ADMIN_USER; no role patch."""
    return make_app(ADMIN_USER)


@pytest.fixture(scope="module")
def jwt_client(jwt_app) -> TestClient:
    with TestClient(jwt_app, raise_server_exceptions=False) as c:
        yield c


# ── Function-scoped role fixtures ─────────────────────────────────────────────


@pytest.fixture
def admin_client():
    """TestClient whose JWT user has ADMIN role in every project."""
    yield from _role_client(ADMIN_USER, ProjectRole.ADMIN)


@pytest.fixture
def member_client():
    """TestClient whose JWT user has MEMBER role in every project."""
    yield from _role_client(MEMBER_USER, ProjectRole.MEMBER)


@pytest.fixture
def secret_editor_client():
    """TestClient whose JWT user has SECRET_EDITOR role in every project."""
    yield from _role_client(SECRET_EDITOR_USER, ProjectRole.SECRET_EDITOR)


@pytest.fixture
def viewer_client():
    """TestClient whose JWT user has VIEWER role in every project."""
    yield from _role_client(VIEWER_USER, ProjectRole.VIEWER)


@pytest.fixture
def no_role_client():
    """TestClient whose JWT user is not a member of any project (role → None → 404)."""
    yield from _role_client(NO_ROLE_USER, None)
