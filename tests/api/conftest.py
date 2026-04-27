# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Shared fixtures for the wurzel/api test suite.

All fixtures require the ``fastapi`` optional extra — tests are skipped
automatically when the extra is not installed.
"""

import pytest

# Skip the entire test module if FastAPI is not installed.
fastapi = pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

from fastapi.testclient import TestClient  # noqa: E402

from wurzel.api.app import create_app  # noqa: E402
from wurzel.api.dependencies import _get_settings  # noqa: E402
from wurzel.api.settings import APISettings  # noqa: E402

TEST_API_KEY = "test-api-key-12345"  # pragma: allowlist secret


@pytest.fixture(scope="module")
def test_settings() -> APISettings:
    """APISettings with a fixed test API key — no env vars needed."""
    return APISettings(API_KEY=TEST_API_KEY)


@pytest.fixture(scope="module")
def app(test_settings: APISettings):
    """Fully wired FastAPI app with auth dependency overridden to use the test key."""
    _app = create_app(settings=test_settings)
    # Override the settings dependency so verify_api_key resolves the same key
    # without reading from environment variables.
    _app.dependency_overrides[_get_settings] = lambda: test_settings
    return _app


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    """Synchronous TestClient wrapping the test app."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Valid ``X-API-Key`` header for authenticated requests."""
    return {"X-API-Key": TEST_API_KEY}


@pytest.fixture
def wrong_headers() -> dict[str, str]:
    """Invalid API key header that must be rejected."""
    return {"X-API-Key": "wrong-key"}


@pytest.fixture
def minimal_manifest() -> dict:
    """Minimal valid PipelineManifest dict for testing."""
    return {
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
