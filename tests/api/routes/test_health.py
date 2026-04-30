# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for GET /v1/health*, /v1/health/live, /v1/health/ready."""

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")


class TestHealthEndpoints:
    @pytest.mark.parametrize(
        "path",
        [
            pytest.param("/v1/health", id="aggregated"),
            pytest.param("/v1/health/live", id="liveness"),
            pytest.param("/v1/health/ready", id="readiness"),
        ],
    )
    def test_returns_200(self, client, path):
        r = client.get(path)
        assert r.status_code == 200

    @pytest.mark.parametrize(
        "path",
        [
            pytest.param("/v1/health", id="aggregated"),
            pytest.param("/v1/health/live", id="liveness"),
            pytest.param("/v1/health/ready", id="readiness"),
        ],
    )
    def test_status_is_ok(self, client, path):
        r = client.get(path)
        assert r.json()["status"] == "ok"

    @pytest.mark.parametrize(
        "path",
        [
            pytest.param("/v1/health", id="aggregated"),
            pytest.param("/v1/health/live", id="liveness"),
            pytest.param("/v1/health/ready", id="readiness"),
        ],
    )
    def test_no_auth_required(self, client, path):
        """Health probes must work without X-API-Key so k8s probes never need credentials."""
        r = client.get(path)
        assert r.status_code != 401

    def test_aggregated_health_has_components_list(self, client):
        body = client.get("/v1/health").json()
        assert "components" in body
        assert isinstance(body["components"], list)
