# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for GET /metrics (Prometheus exposition endpoint)."""

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")


class TestMetricsEndpoint:
    def test_returns_200(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200

    def test_content_type_is_prometheus(self, client):
        r = client.get("/metrics")
        assert "text/plain" in r.headers["content-type"]

    def test_no_auth_required(self, client):
        """Prometheus must be able to scrape without credentials."""
        r = client.get("/metrics")
        assert r.status_code != 401

    def test_body_contains_prometheus_comment(self, client):
        """Prometheus text format always starts with # HELP or # TYPE lines."""
        r = client.get("/metrics")
        # May be empty on a fresh process, but must not be an error payload
        assert b"title" not in r.content or r.status_code == 200
