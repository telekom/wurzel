# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for GET /v1/steps and GET /v1/steps/{step_path} discovery endpoints."""

import time
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

from fastapi.testclient import TestClient  # noqa: E402

from wurzel.api.app import create_app  # noqa: E402
from wurzel.api.auth.jwt import UserClaims, _verify_jwt  # noqa: E402
from wurzel.api.routes.steps import service as service_module  # noqa: E402
from wurzel.api.settings import APISettings  # noqa: E402

# A well-known step that always ships with wurzel
_KNOWN_STEP = "wurzel.steps.manual_markdown.ManualMarkdownStep"
_KNOWN_PACKAGE = "wurzel.steps"

_TEST_USER = UserClaims(sub="test-user", email="test@example.com", raw={})
_SETTINGS = APISettings(API_KEY="test-key")


@pytest.fixture(scope="module")
def app():
    _app = create_app(settings=_SETTINGS)
    _app.dependency_overrides[_verify_jwt] = lambda: _TEST_USER
    return _app


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


class TestStepsList:
    def test_default_package_returns_200(self, client, auth_headers):
        r = client.get("/v1/steps", headers=auth_headers)
        assert r.status_code == 200

    def test_default_scan_contains_known_step(self, client, auth_headers):
        r = client.get("/v1/steps", headers=auth_headers)
        class_paths = [s["class_path"] for s in r.json()["steps"]]
        assert _KNOWN_STEP in class_paths

    def test_default_scan_package_label_is_wildcard(self, client, auth_headers):
        r = client.get("/v1/steps", headers=auth_headers)
        assert r.json()["package"] == "*"

    def test_response_has_steps_list(self, client, auth_headers):
        r = client.get("/v1/steps", headers=auth_headers)
        body = r.json()
        assert "steps" in body
        assert isinstance(body["steps"], list)

    def test_explicit_package_returns_200(self, client, auth_headers):
        r = client.get(f"/v1/steps?package={_KNOWN_PACKAGE}", headers=auth_headers)
        assert r.status_code == 200

    def test_known_step_in_package_listing(self, client, auth_headers):
        r = client.get(f"/v1/steps?package={_KNOWN_PACKAGE}", headers=auth_headers)
        class_paths = [s["class_path"] for s in r.json()["steps"]]
        assert _KNOWN_STEP in class_paths

    def test_nonexistent_package_returns_400(self, client, auth_headers):
        r = client.get("/v1/steps?package=nonexistent_xyz_pkg", headers=auth_headers)
        assert r.status_code == 400

    def test_nonexistent_package_body_is_problem_json(self, client, auth_headers):
        r = client.get("/v1/steps?package=nonexistent_xyz_pkg", headers=auth_headers)
        assert r.headers["content-type"] == "application/problem+json"
        assert r.json()["status"] == 400

    def test_each_item_has_required_fields(self, client, auth_headers):
        r = client.get(f"/v1/steps?package={_KNOWN_PACKAGE}", headers=auth_headers)
        for item in r.json()["steps"]:
            assert "class_path" in item
            assert "name" in item
            assert "input_type" in item
            assert "output_type" in item

    def test_known_step_has_output_type_in_list(self, client, auth_headers):
        r = client.get(f"/v1/steps?package={_KNOWN_PACKAGE}", headers=auth_headers)
        step = next(s for s in r.json()["steps"] if s["class_path"] == _KNOWN_STEP)
        assert step["output_type"] is not None

    def test_known_step_output_type_is_fully_qualified(self, client, auth_headers):
        # ManualMarkdownStep output is list[MarkdownDataContract] — should show full module path
        r = client.get(f"/v1/steps?package={_KNOWN_PACKAGE}", headers=auth_headers)
        step = next(s for s in r.json()["steps"] if s["class_path"] == _KNOWN_STEP)
        assert step["output_type"] == "list[wurzel.datacontract.MarkdownDataContract]"

    def test_known_step_has_null_input_type_in_list(self, client, auth_headers):
        # ManualMarkdownStep is a source step — its input type must be null
        r = client.get(f"/v1/steps?package={_KNOWN_PACKAGE}", headers=auth_headers)
        step = next(s for s in r.json()["steps"] if s["class_path"] == _KNOWN_STEP)
        assert step["input_type"] is None

    def test_excluded_base_class_not_in_list(self, client, auth_headers):
        r = client.get("/v1/steps", headers=auth_headers)
        class_paths = [s["class_path"] for s in r.json()["steps"]]
        assert "wurzel.core.self_consuming_step.SelfConsumingLeafStep" not in class_paths


class TestStepGet:
    def test_known_step_returns_200(self, client, auth_headers):
        r = client.get(f"/v1/steps/{_KNOWN_STEP}", headers=auth_headers)
        assert r.status_code == 200

    def test_known_step_has_class_path(self, client, auth_headers):
        r = client.get(f"/v1/steps/{_KNOWN_STEP}", headers=auth_headers)
        assert r.json()["class_path"] == _KNOWN_STEP

    def test_known_step_has_settings_schema(self, client, auth_headers):
        r = client.get(f"/v1/steps/{_KNOWN_STEP}", headers=auth_headers)
        schema = r.json().get("settings_schema")
        assert schema is not None
        assert isinstance(schema, list)

    def test_known_step_has_input_type(self, client, auth_headers):
        r = client.get(f"/v1/steps/{_KNOWN_STEP}", headers=auth_headers)
        assert "input_type" in r.json()

    def test_known_step_has_output_type(self, client, auth_headers):
        r = client.get(f"/v1/steps/{_KNOWN_STEP}", headers=auth_headers)
        assert "output_type" in r.json()

    def test_invalid_path_no_dot_returns_400(self, client, auth_headers):
        r = client.get("/v1/steps/nodothere", headers=auth_headers)
        assert r.status_code == 400

    def test_invalid_path_no_class_returns_400(self, client, auth_headers):
        r = client.get("/v1/steps/just.a.module", headers=auth_headers)
        assert r.status_code in (400, 404)

    def test_nonexistent_module_returns_404(self, client, auth_headers):
        r = client.get("/v1/steps/nonexistent.module.FakeClass", headers=auth_headers)
        assert r.status_code == 404

    def test_nonexistent_class_returns_404(self, client, auth_headers):
        r = client.get("/v1/steps/wurzel.steps.manual_markdown.FakeStep", headers=auth_headers)
        assert r.status_code == 404


class TestStepSecretDetection:
    """Steps with SecretStr fields must have secret=True in the settings schema."""

    def test_secret_field_flagged(self, client, auth_headers):
        """ScraperAPIStep.TOKEN is a SecretStr — must be reported as secret=True."""
        step_path = "wurzel.steps.scraperapi.step.ScraperAPIStep"
        r = client.get(f"/v1/steps/{step_path}", headers=auth_headers)
        if r.status_code == 404:
            pytest.skip("ScraperAPIStep not available in this environment")
        schema = r.json()["settings_schema"]
        secret_fields = [f for f in schema if f.get("secret") is True]
        assert secret_fields, "Expected at least one secret field in ScraperAPIStep settings"

    def test_non_secret_field_not_flagged(self, client, auth_headers):
        r = client.get(f"/v1/steps/{_KNOWN_STEP}", headers=auth_headers)
        schema = r.json().get("settings_schema", [])
        # ManualMarkdownStep settings should not have any SecretStr fields
        secret_fields = [f for f in schema if f.get("secret") is True]
        assert not secret_fields, "ManualMarkdownStep should have no secret fields"


class TestStepListCache:
    """The list endpoint caches results to avoid re-scanning on every request."""

    def test_second_request_is_served_from_cache(self, client, auth_headers):
        """Two consecutive requests should return identical results, second much faster."""
        # Clear the cache so the first request is a cold start
        service_module._DEFAULT_CACHE.clear()

        t0 = time.monotonic()
        r1 = client.get(f"/v1/steps?package={_KNOWN_PACKAGE}", headers=auth_headers)
        cold_duration = time.monotonic() - t0

        t1 = time.monotonic()
        r2 = client.get(f"/v1/steps?package={_KNOWN_PACKAGE}", headers=auth_headers)
        warm_duration = time.monotonic() - t1

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["steps"] == r2.json()["steps"]
        # Warm request should be at least 3x faster than cold (more reliable on slow CI runners)
        assert warm_duration < cold_duration / 3

    def test_cache_expires_after_ttl(self, client, auth_headers):
        """After the TTL is exceeded a fresh scan is performed."""
        service_module._DEFAULT_CACHE.clear()

        # Populate cache with an artificially old timestamp
        old_entry = (time.monotonic() - service_module._CACHE_TTL - 1, ["fake.Step"])
        service_module._DEFAULT_CACHE._data[_KNOWN_PACKAGE] = old_entry

        with patch(
            "wurzel.api.routes.steps.service.scan_path_for_typed_steps",
            return_value=["wurzel.steps.manual_markdown.ManualMarkdownStep"],
        ) as mock_scan:
            r = client.get(f"/v1/steps?package={_KNOWN_PACKAGE}", headers=auth_headers)

        assert r.status_code == 200
        mock_scan.assert_called_once()

    def test_cache_hit_skips_scan(self, client, auth_headers):
        """A fresh cache entry must not trigger a new scan."""
        service_module._DEFAULT_CACHE.clear()
        service_module._DEFAULT_CACHE._data[_KNOWN_PACKAGE] = (
            time.monotonic(),
            ["wurzel.steps.manual_markdown.ManualMarkdownStep"],
        )

        with patch("wurzel.api.routes.steps.service.scan_path_for_typed_steps") as mock_scan:
            r = client.get(f"/v1/steps?package={_KNOWN_PACKAGE}", headers=auth_headers)

        assert r.status_code == 200
        mock_scan.assert_not_called()


class TestStepInfoCache:
    """The detail endpoint caches StepInfo objects permanently."""

    def test_step_info_is_cached_after_first_request(self, client, auth_headers):
        service_module._build_step_info.cache_clear()
        assert service_module._build_step_info.cache_info().currsize == 0

        r = client.get(f"/v1/steps/{_KNOWN_STEP}", headers=auth_headers)
        assert r.status_code == 200
        assert service_module._build_step_info.cache_info().currsize > 0

    def test_cached_step_info_returned_on_second_request(self, client, auth_headers):
        service_module._build_step_info.cache_clear()
        r1 = client.get(f"/v1/steps/{_KNOWN_STEP}", headers=auth_headers)
        r2 = client.get(f"/v1/steps/{_KNOWN_STEP}", headers=auth_headers)
        assert r1.json() == r2.json()
