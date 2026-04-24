# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for GET /v1/steps and GET /v1/steps/{step_path} discovery endpoints."""

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

# A well-known step that always ships with wurzel
_KNOWN_STEP = "wurzel.steps.manual_markdown.ManualMarkdownStep"
_KNOWN_PACKAGE = "wurzel.steps"


class TestStepsAuth:
    def test_list_missing_key_returns_401(self, client):
        r = client.get("/v1/steps")
        assert r.status_code == 401

    def test_list_wrong_key_returns_401(self, client, wrong_headers):
        r = client.get("/v1/steps", headers=wrong_headers)
        assert r.status_code == 401

    def test_get_missing_key_returns_401(self, client):
        r = client.get(f"/v1/steps/{_KNOWN_STEP}")
        assert r.status_code == 401


class TestStepsList:
    def test_default_package_returns_200(self, client, auth_headers):
        r = client.get("/v1/steps", headers=auth_headers)
        assert r.status_code == 200

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
        r = client.get(f"/v1/steps/nonexistent.module.FakeClass", headers=auth_headers)
        assert r.status_code == 404

    def test_nonexistent_class_returns_404(self, client, auth_headers):
        r = client.get(f"/v1/steps/wurzel.steps.manual_markdown.FakeStep", headers=auth_headers)
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
