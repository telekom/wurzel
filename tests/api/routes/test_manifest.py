# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Comprehensive tests for /v1/manifest CRUD + submit routes.

The manifest router uses an in-memory store that is cleared before each test
to guarantee full isolation.
"""

import uuid

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

import wurzel.api.routes.manifest.router as _manifest_router  # noqa: E402


@pytest.fixture(autouse=True)
def clear_store():
    """Reset the in-memory manifest store before and after every test."""
    _manifest_router._store.clear()
    yield
    _manifest_router._store.clear()


# ── helpers ──────────────────────────────────────────────────────────────────


def _create(client, auth_headers, minimal_manifest, *, name: str = "test-pipeline") -> dict:
    """POST a manifest and return the response body."""
    manifest = dict(minimal_manifest)
    manifest["metadata"] = {"name": name}
    r = client.post(
        "/v1/manifest",
        json={"definition": manifest},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


# ── Auth ──────────────────────────────────────────────────────────────────────


class TestManifestAuth:
    @pytest.mark.parametrize(
        "method,path_suffix",
        [
            pytest.param("POST", "", id="create"),
            pytest.param("GET", "", id="list"),
            pytest.param("GET", f"/{uuid.uuid4()}", id="get"),
            pytest.param("PUT", f"/{uuid.uuid4()}", id="update"),
            pytest.param("DELETE", f"/{uuid.uuid4()}", id="delete"),
            pytest.param("POST", f"/{uuid.uuid4()}/submit", id="submit"),
        ],
    )
    def test_missing_key_returns_401(self, client, method, path_suffix):
        r = client.request(method, f"/v1/manifest{path_suffix}", json={})
        assert r.status_code == 401


# ── Create ────────────────────────────────────────────────────────────────────


class TestManifestCreate:
    def test_returns_201(self, client, auth_headers, minimal_manifest):
        r = client.post(
            "/v1/manifest",
            json={"definition": minimal_manifest},
            headers=auth_headers,
        )
        assert r.status_code == 201

    def test_response_has_id(self, client, auth_headers, minimal_manifest):
        r = client.post(
            "/v1/manifest",
            json={"definition": minimal_manifest},
            headers=auth_headers,
        )
        data = r.json()
        uuid.UUID(data["id"])  # validates UUID format

    def test_response_name_matches_definition(self, client, auth_headers, minimal_manifest):
        r = client.post(
            "/v1/manifest",
            json={"definition": minimal_manifest},
            headers=auth_headers,
        )
        assert r.json()["name"] == "test-pipeline"

    def test_initial_run_status_is_pending(self, client, auth_headers, minimal_manifest):
        r = client.post(
            "/v1/manifest",
            json={"definition": minimal_manifest},
            headers=auth_headers,
        )
        assert r.json()["run_status"] == "pending"

    def test_invalid_body_returns_422(self, client, auth_headers):
        r = client.post("/v1/manifest", json={"definition": {}}, headers=auth_headers)
        assert r.status_code == 422

    def test_unknown_backend_returns_422(self, client, auth_headers, minimal_manifest):
        bad = dict(minimal_manifest)
        bad["spec"] = dict(bad["spec"])
        bad["spec"]["backend"] = "not-a-backend"
        r = client.post("/v1/manifest", json={"definition": bad}, headers=auth_headers)
        assert r.status_code == 422


# ── List ──────────────────────────────────────────────────────────────────────


class TestManifestList:
    def test_empty_store_returns_empty_list(self, client, auth_headers):
        r = client.get("/v1/manifest", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_lists_created_manifests(self, client, auth_headers, minimal_manifest):
        _create(client, auth_headers, minimal_manifest)
        _create(client, auth_headers, minimal_manifest, name="second")
        r = client.get("/v1/manifest", headers=auth_headers)
        assert r.json()["total"] == 2

    def test_pagination_offset(self, client, auth_headers, minimal_manifest):
        for i in range(4):
            _create(client, auth_headers, minimal_manifest, name=f"pipeline-{i}")
        r = client.get("/v1/manifest?offset=2&limit=10", headers=auth_headers)
        body = r.json()
        assert body["total"] == 4
        assert len(body["items"]) == 2
        assert body["offset"] == 2

    def test_pagination_limit(self, client, auth_headers, minimal_manifest):
        for i in range(5):
            _create(client, auth_headers, minimal_manifest, name=f"p-{i}")
        r = client.get("/v1/manifest?limit=3", headers=auth_headers)
        body = r.json()
        assert len(body["items"]) == 3
        assert body["limit"] == 3
        assert body["total"] == 5

    def test_pagination_beyond_end_returns_empty(self, client, auth_headers, minimal_manifest):
        _create(client, auth_headers, minimal_manifest)
        r = client.get("/v1/manifest?offset=999", headers=auth_headers)
        assert r.json()["items"] == []


# ── Get ───────────────────────────────────────────────────────────────────────


class TestManifestGet:
    def test_get_existing_returns_200(self, client, auth_headers, minimal_manifest):
        created = _create(client, auth_headers, minimal_manifest)
        r = client.get(f"/v1/manifest/{created['id']}", headers=auth_headers)
        assert r.status_code == 200

    def test_get_returns_same_id(self, client, auth_headers, minimal_manifest):
        created = _create(client, auth_headers, minimal_manifest)
        r = client.get(f"/v1/manifest/{created['id']}", headers=auth_headers)
        assert r.json()["id"] == created["id"]

    def test_get_nonexistent_returns_404(self, client, auth_headers):
        r = client.get(f"/v1/manifest/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404

    def test_get_nonexistent_body_is_problem_json(self, client, auth_headers):
        r = client.get(f"/v1/manifest/{uuid.uuid4()}", headers=auth_headers)
        assert r.headers["content-type"] == "application/problem+json"
        assert r.json()["title"] == "Manifest not found"


# ── Update ────────────────────────────────────────────────────────────────────


class TestManifestUpdate:
    def test_update_name(self, client, auth_headers, minimal_manifest):
        created = _create(client, auth_headers, minimal_manifest)
        updated_def = dict(minimal_manifest)
        updated_def["metadata"] = {"name": "renamed-pipeline"}
        r = client.put(
            f"/v1/manifest/{created['id']}",
            json={"definition": updated_def},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "renamed-pipeline"

    def test_update_persisted(self, client, auth_headers, minimal_manifest):
        created = _create(client, auth_headers, minimal_manifest)
        updated_def = dict(minimal_manifest)
        updated_def["metadata"] = {"name": "persisted-name"}
        client.put(
            f"/v1/manifest/{created['id']}",
            json={"definition": updated_def},
            headers=auth_headers,
        )
        r = client.get(f"/v1/manifest/{created['id']}", headers=auth_headers)
        assert r.json()["name"] == "persisted-name"

    def test_update_nonexistent_returns_404(self, client, auth_headers, minimal_manifest):
        r = client.put(
            f"/v1/manifest/{uuid.uuid4()}",
            json={"definition": minimal_manifest},
            headers=auth_headers,
        )
        assert r.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────


class TestManifestDelete:
    def test_delete_returns_204(self, client, auth_headers, minimal_manifest):
        created = _create(client, auth_headers, minimal_manifest)
        r = client.delete(f"/v1/manifest/{created['id']}", headers=auth_headers)
        assert r.status_code == 204

    def test_deleted_manifest_is_gone(self, client, auth_headers, minimal_manifest):
        created = _create(client, auth_headers, minimal_manifest)
        client.delete(f"/v1/manifest/{created['id']}", headers=auth_headers)
        r = client.get(f"/v1/manifest/{created['id']}", headers=auth_headers)
        assert r.status_code == 404

    def test_delete_reduces_total(self, client, auth_headers, minimal_manifest):
        m1 = _create(client, auth_headers, minimal_manifest, name="a")
        _create(client, auth_headers, minimal_manifest, name="b")
        client.delete(f"/v1/manifest/{m1['id']}", headers=auth_headers)
        r = client.get("/v1/manifest", headers=auth_headers)
        assert r.json()["total"] == 1

    def test_delete_nonexistent_returns_404(self, client, auth_headers):
        r = client.delete(f"/v1/manifest/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404


# ── Submit ────────────────────────────────────────────────────────────────────


class TestManifestSubmit:
    def test_submit_returns_202(self, client, auth_headers, minimal_manifest):
        created = _create(client, auth_headers, minimal_manifest)
        r = client.post(
            f"/v1/manifest/{created['id']}/submit",
            json={"run_now": False},
            headers=auth_headers,
        )
        assert r.status_code == 202

    def test_submit_response_has_manifest_id(self, client, auth_headers, minimal_manifest):
        created = _create(client, auth_headers, minimal_manifest)
        r = client.post(
            f"/v1/manifest/{created['id']}/submit",
            json={"run_now": False},
            headers=auth_headers,
        )
        assert r.json()["manifest_id"] == created["id"]

    def test_submit_run_now_false_stays_pending(self, client, auth_headers, minimal_manifest):
        created = _create(client, auth_headers, minimal_manifest)
        r = client.post(
            f"/v1/manifest/{created['id']}/submit",
            json={"run_now": False},
            headers=auth_headers,
        )
        assert r.json()["run_status"] == "pending"

    @pytest.mark.parametrize(
        "backend",
        [
            pytest.param("inline", id="inline"),
            pytest.param("dvc", id="dvc"),
            pytest.param("argo", id="argo"),
        ],
    )
    def test_submit_accepts_valid_backends(self, client, auth_headers, minimal_manifest, backend):
        created = _create(client, auth_headers, minimal_manifest)
        r = client.post(
            f"/v1/manifest/{created['id']}/submit",
            json={"backend": backend, "run_now": False},
            headers=auth_headers,
        )
        assert r.status_code == 202

    def test_submit_invalid_backend_returns_422(self, client, auth_headers, minimal_manifest):
        created = _create(client, auth_headers, minimal_manifest)
        r = client.post(
            f"/v1/manifest/{created['id']}/submit",
            json={"backend": "kubernetes"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_submit_nonexistent_manifest_returns_404(self, client, auth_headers):
        r = client.post(
            f"/v1/manifest/{uuid.uuid4()}/submit",
            json={"run_now": False},
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_submit_triggers_background_task_on_run_now(
        self, client, auth_headers, minimal_manifest, mocker
    ):
        """When run_now=True the background task must be enqueued."""
        mock = mocker.patch(
            "wurzel.api.routes.manifest.router._execute_manifest",
            return_value=None,
        )
        created = _create(client, auth_headers, minimal_manifest)
        client.post(
            f"/v1/manifest/{created['id']}/submit",
            json={"backend": "inline", "run_now": True},
            headers=auth_headers,
        )
        # TestClient runs background tasks synchronously
        assert mock.called


# ── Full round-trip ───────────────────────────────────────────────────────────


class TestManifestRoundTrip:
    def test_create_list_get_update_delete(self, client, auth_headers, minimal_manifest):
        # Create
        created = _create(client, auth_headers, minimal_manifest)
        manifest_id = created["id"]

        # List
        r = client.get("/v1/manifest", headers=auth_headers)
        assert r.json()["total"] == 1

        # Get
        r = client.get(f"/v1/manifest/{manifest_id}", headers=auth_headers)
        assert r.json()["name"] == "test-pipeline"

        # Update
        updated_def = dict(minimal_manifest)
        updated_def["metadata"] = {"name": "updated"}
        r = client.put(
            f"/v1/manifest/{manifest_id}",
            json={"definition": updated_def},
            headers=auth_headers,
        )
        assert r.json()["name"] == "updated"

        # Delete
        r = client.delete(f"/v1/manifest/{manifest_id}", headers=auth_headers)
        assert r.status_code == 204

        # Confirm gone
        r = client.get("/v1/manifest", headers=auth_headers)
        assert r.json()["total"] == 0
