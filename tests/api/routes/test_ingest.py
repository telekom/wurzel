# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for /v1/ingest routes."""

import uuid

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")


class TestIngestAuth:
    @pytest.mark.parametrize(
        "method,path",
        [
            pytest.param("POST", "/v1/ingest", id="submit"),
            pytest.param("GET", f"/v1/ingest/{uuid.uuid4()}", id="status"),
        ],
    )
    def test_missing_key_returns_401(self, client, method, path):
        r = client.request(method, path, json={})
        assert r.status_code == 401


class TestIngestSubmit:
    def test_submit_accepted(self, client, auth_headers):
        body = {
            "items": [
                {"title": "Doc 1", "content": "Hello world"},
                {"title": "Doc 2", "content": "Goodbye world"},
            ]
        }
        r = client.post("/v1/ingest", json=body, headers=auth_headers)
        assert r.status_code == 202

    def test_submit_response_has_job_id(self, client, auth_headers):
        body = {"items": [{"title": "T", "content": "C"}]}
        r = client.post("/v1/ingest", json=body, headers=auth_headers)
        data = r.json()
        assert "job_id" in data
        uuid.UUID(data["job_id"])  # must be a valid UUID

    def test_submit_response_status_is_pending(self, client, auth_headers):
        body = {"items": [{"title": "T", "content": "C"}]}
        r = client.post("/v1/ingest", json=body, headers=auth_headers)
        assert r.json()["status"] == "pending"

    def test_submit_reflects_item_count(self, client, auth_headers):
        items = [{"title": f"Doc {i}", "content": f"Content {i}"} for i in range(5)]
        r = client.post("/v1/ingest", json={"items": items}, headers=auth_headers)
        assert r.json()["item_count"] == 5

    def test_submit_empty_items_returns_422(self, client, auth_headers):
        r = client.post("/v1/ingest", json={"items": []}, headers=auth_headers)
        assert r.status_code == 422

    def test_submit_missing_body_returns_422(self, client, auth_headers):
        r = client.post("/v1/ingest", json={}, headers=auth_headers)
        assert r.status_code == 422


class TestIngestStatus:
    def test_get_job_status_returns_501(self, client, auth_headers):
        """Job persistence not wired yet — expect 501."""
        r = client.get(f"/v1/ingest/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 501
        assert r.headers["content-type"] == "application/problem+json"


class TestIngestInputValidation:
    @pytest.mark.parametrize(
        "item",
        [
            pytest.param({"title": "T", "content": "C"}, id="minimal"),
            pytest.param(
                {"title": "T", "content": "C", "source": "s3://bucket/key", "tags": ["a", "b"]},
                id="with_source_and_tags",
            ),
            pytest.param(
                {"title": "T", "content": "C", "metadata": {"key": "value"}},
                id="with_metadata",
            ),
        ],
    )
    def test_valid_item_shapes_accepted(self, client, auth_headers, item):
        r = client.post("/v1/ingest", json={"items": [item]}, headers=auth_headers)
        assert r.status_code == 202
