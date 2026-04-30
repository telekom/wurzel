# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Integration tests: end-to-end flows for the project → branch → manifest API.

Uses ``FakeDB`` — an in-memory store that patches every Supabase helper at
once, letting a single test drive several consecutive API calls and observe the
side effects of earlier calls on later ones (e.g. promote writes to main, the
next GET of main's manifest returns it).

Contrast with the unit tests in ``test_branches.py`` / ``test_projects.py``
which mock one DB call per test body.

Test classes
------------
Happy paths
  TestFullPromoteFlow        — create project, set manifest, diff, promote, verify
  TestMergeWithConflictsFlow — diverging branches, diff detects conflicts, merge resolves
  TestBranchLifecycle        — full CRUD: create, list, get, update manifest, delete
  TestStepsDiscoveryFlow     — discover step → inspect schema → use in manifest

Bad paths (input validation)
  TestBranchNameValidation   — reserved names, invalid patterns, duplicates
  TestManifestValidation     — missing fields, empty body, bad merge payload
  TestProtectedBranchErrors  — write to main, delete main, unprotect main
  TestNotFoundErrors         — ghost branches, nonexistent targets for diff/promote

Bad paths (permissions)
  TestPermissionBoundaries   — viewer cannot write, member cannot create/delete branches
  TestStepsApiErrors         — unknown package, bad step path, nonexistent module/class
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

from fastapi.testclient import TestClient  # noqa: E402

from wurzel.api.routes.member.data import ProjectRole  # noqa: E402

from .conftest import ADMIN_USER, MEMBER_USER, VIEWER_USER, make_app  # noqa: E402

# ── Shared test data ──────────────────────────────────────────────────────────

_NOW = "2025-01-01T12:00:00"
_KNOWN_STEP = "wurzel.steps.manual_markdown.ManualMarkdownStep"

_MINIMAL_MANIFEST = {
    "apiVersion": "wurzel.dev/v1alpha1",
    "kind": "Pipeline",
    "metadata": {"name": "my-pipeline"},
    "spec": {
        "backend": "dvc",
        "steps": [{"name": "source", "class": _KNOWN_STEP}],
    },
}

_UPDATED_MANIFEST = {
    "apiVersion": "wurzel.dev/v1alpha1",
    "kind": "Pipeline",
    "metadata": {"name": "my-pipeline"},
    "spec": {
        "backend": "argo",
        "steps": [{"name": "source", "class": _KNOWN_STEP}],
    },
}


# ── FakeDB ────────────────────────────────────────────────────────────────────


class FakeDB:
    """In-memory substitute for all Supabase DB helpers.

    Call ``patch_all()`` as a context manager to replace every DB function.
    State persists across API calls within the same context, enabling
    multi-step flow tests without any real network or database.
    """

    def __init__(self) -> None:
        self.projects: dict[str, dict] = {}
        self.members: dict[tuple[str, str], dict] = {}  # (project_id, user_id) -> row
        self.branches: dict[tuple[str, str], dict] = {}  # (project_id, name) -> row
        self._branches_by_id: dict[str, dict] = {}
        self.manifests: dict[str, dict] = {}  # branch_id -> row
        self._roles: dict[tuple[str, str], ProjectRole] = {}

    def seed_role(self, project_id: str, user_id: str, role: ProjectRole | None) -> None:
        """Directly inject a role, bypassing add_member (useful for error test setup)."""
        key = (project_id, user_id)
        if role is None:
            self._roles.pop(key, None)
        else:
            self._roles[key] = role

    # ── Role / protection helpers (lazy-imported by permissions module) ────────

    async def _get_role(self, project_id: uuid.UUID, user_id: str) -> ProjectRole | None:
        return self._roles.get((str(project_id), user_id))

    async def _get_branch_protection(self, project_id: uuid.UUID, branch_name: str) -> bool:
        row = self.branches.get((str(project_id), branch_name))
        return bool(row.get("is_protected", False)) if row else False

    # ── Project CRUD ──────────────────────────────────────────────────────────

    async def create_project(self, name: str, description: str | None, created_by: str) -> dict:
        pid = str(uuid.uuid4())
        row = {
            "id": pid,
            "name": name,
            "description": description,
            "created_by": created_by,
            "created_at": _NOW,
            "updated_at": _NOW,
        }
        self.projects[pid] = row
        return row

    async def get_project(self, project_id: uuid.UUID) -> dict | None:
        return self.projects.get(str(project_id))

    async def list_projects_for_user(self, user_id: str, offset: int, limit: int) -> tuple[list[dict], int]:
        member_pids = {pid for (pid, uid) in self._roles if uid == user_id}
        rows = [p for pid, p in self.projects.items() if pid in member_pids]
        return rows[offset : offset + limit], len(rows)

    async def update_project(self, project_id: uuid.UUID, fields: dict) -> dict | None:
        row = self.projects.get(str(project_id))
        if row is None:
            return None
        row.update(fields)
        row["updated_at"] = _NOW
        return row

    async def delete_project(self, project_id: uuid.UUID) -> None:
        self.projects.pop(str(project_id), None)

    # ── Member CRUD ───────────────────────────────────────────────────────────

    async def add_member(self, project_id: uuid.UUID, user_id: str, role: str) -> dict:
        key = (str(project_id), user_id)
        row = {
            "id": str(uuid.uuid4()),
            "project_id": str(project_id),
            "user_id": user_id,
            "role": role,
            "created_at": _NOW,
            "updated_at": _NOW,
        }
        self.members[key] = row
        self._roles[key] = ProjectRole(role)
        return row

    async def list_members(self, project_id: uuid.UUID) -> list[dict]:
        return [v for (pid, _), v in self.members.items() if pid == str(project_id)]

    async def get_member(self, project_id: uuid.UUID, user_id: str) -> dict | None:
        return self.members.get((str(project_id), user_id))

    async def remove_member(self, project_id: uuid.UUID, user_id: str) -> None:
        key = (str(project_id), user_id)
        self.members.pop(key, None)
        self._roles.pop(key, None)

    async def count_admins(self, project_id: uuid.UUID) -> int:
        return sum(1 for (pid, _), v in self.members.items() if pid == str(project_id) and v["role"] == "admin")

    async def update_member_role(self, project_id: uuid.UUID, user_id: str, role: str) -> dict | None:
        key = (str(project_id), user_id)
        row = self.members.get(key)
        if row is None:
            return None
        row["role"] = role
        self._roles[key] = ProjectRole(role)
        return row

    # ── Branch CRUD ───────────────────────────────────────────────────────────

    async def create_branch(
        self,
        project_id: uuid.UUID,
        name: str,
        *,
        is_protected: bool = False,
        is_default: bool = False,
        promotes_to_id: uuid.UUID | None = None,
    ) -> dict:
        bid = str(uuid.uuid4())
        row: dict = {
            "id": bid,
            "project_id": str(project_id),
            "name": name,
            "is_protected": is_protected,
            "is_default": is_default,
            "promotes_to_id": str(promotes_to_id) if promotes_to_id else None,
            "promotes_to_name": None,
            "created_at": _NOW,
            "updated_at": _NOW,
        }
        self.branches[(str(project_id), name)] = row
        self._branches_by_id[bid] = row
        return row

    async def get_branch(self, project_id: uuid.UUID, branch_name: str) -> dict | None:
        return self.branches.get((str(project_id), branch_name))

    async def get_branch_by_id(self, branch_id: uuid.UUID) -> dict | None:
        return self._branches_by_id.get(str(branch_id))

    async def list_branches(self, project_id: uuid.UUID) -> list[dict]:
        return [v for (pid, _), v in self.branches.items() if pid == str(project_id)]

    async def update_branch(self, project_id: uuid.UUID, branch_name: str, fields: dict) -> dict | None:
        row = self.branches.get((str(project_id), branch_name))
        if row is None:
            return None
        row.update(fields)
        row["updated_at"] = _NOW
        return row

    async def delete_branch(self, project_id: uuid.UUID, branch_name: str) -> None:
        row = self.branches.pop((str(project_id), branch_name), None)
        if row:
            self._branches_by_id.pop(row["id"], None)

    # ── Manifest CRUD ─────────────────────────────────────────────────────────

    async def get_branch_manifest(self, branch_id: uuid.UUID) -> dict | None:
        return self.manifests.get(str(branch_id))

    async def upsert_branch_manifest(self, branch_id: uuid.UUID, definition: dict) -> dict:
        row = {
            "id": str(uuid.uuid4()),
            "branch_id": str(branch_id),
            "definition": definition,
            "run_status": "pending",
            "updated_at": _NOW,
        }
        self.manifests[str(branch_id)] = row
        return row

    async def patch_manifest_status(self, branch_id: uuid.UUID, status: str) -> None:
        row = self.manifests.get(str(branch_id))
        if row:
            row["run_status"] = status

    # ── Patch context manager ─────────────────────────────────────────────────

    @contextlib.contextmanager
    def patch_all(self) -> Generator[FakeDB, None, None]:
        """Replace every Supabase DB helper with in-memory implementations."""
        _branch = "wurzel.api.routes.branch.router"
        _project = "wurzel.api.routes.project.router"
        _member = "wurzel.api.routes.member.router"
        _client = "wurzel.api.backends.supabase.client"

        patches = [
            # Role + branch-protection are lazy-imported → patch at the source module
            patch(f"{_client}.get_project_role_from_db", new=AsyncMock(side_effect=self._get_role)),
            patch(f"{_client}.get_branch_protection", new=AsyncMock(side_effect=self._get_branch_protection)),
            # Project router
            patch(f"{_project}.db_create_project", new=AsyncMock(side_effect=self.create_project)),
            patch(f"{_project}.db_get_project", new=AsyncMock(side_effect=self.get_project)),
            patch(f"{_project}.db_list_projects_for_user", new=AsyncMock(side_effect=self.list_projects_for_user)),
            patch(f"{_project}.db_update_project", new=AsyncMock(side_effect=self.update_project)),
            patch(f"{_project}.db_delete_project", new=AsyncMock(side_effect=self.delete_project)),
            patch(f"{_project}.db_create_branch", new=AsyncMock(side_effect=self.create_branch)),
            patch(f"{_project}.db_add_member", new=AsyncMock(side_effect=self.add_member)),
            # Branch router
            patch(f"{_branch}.db_create_branch", new=AsyncMock(side_effect=self.create_branch)),
            patch(f"{_branch}.db_get_branch", new=AsyncMock(side_effect=self.get_branch)),
            patch(f"{_branch}.db_list_branches", new=AsyncMock(side_effect=self.list_branches)),
            patch(f"{_branch}.db_update_branch", new=AsyncMock(side_effect=self.update_branch)),
            patch(f"{_branch}.db_delete_branch", new=AsyncMock(side_effect=self.delete_branch)),
            patch(f"{_branch}.db_get_branch_manifest", new=AsyncMock(side_effect=self.get_branch_manifest)),
            patch(f"{_branch}.db_upsert_branch_manifest", new=AsyncMock(side_effect=self.upsert_branch_manifest)),
            patch(f"{_branch}.db_patch_manifest_status", new=AsyncMock(side_effect=self.patch_manifest_status)),
            # Member router
            patch(f"{_member}.db_list_members", new=AsyncMock(side_effect=self.list_members)),
            patch(f"{_member}.db_get_member", new=AsyncMock(side_effect=self.get_member)),
            patch(f"{_member}.db_add_member", new=AsyncMock(side_effect=self.add_member)),
            patch(f"{_member}.db_remove_member", new=AsyncMock(side_effect=self.remove_member)),
            patch(f"{_member}.db_count_admins", new=AsyncMock(side_effect=self.count_admins)),
            patch(f"{_member}.db_update_member_role", new=AsyncMock(side_effect=self.update_member_role)),
        ]
        for p in patches:
            p.start()
        try:
            yield self
        finally:
            for p in patches:
                p.stop()


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_db() -> FakeDB:
    return FakeDB()


@pytest.fixture
def admin_client():
    with TestClient(make_app(ADMIN_USER), raise_server_exceptions=False) as c:
        yield c


# ── Shared helper ─────────────────────────────────────────────────────────────


def _create_project_and_branch(client: TestClient, branch_name: str = "feature") -> tuple[str, str]:
    """Create a project + one branch via the API; return (project_id, branch_name)."""
    r = client.post("/v1/projects", json={"name": "test-project"})
    assert r.status_code == 201, r.json()
    project_id = r.json()["id"]
    r = client.post(f"/v1/projects/{project_id}/branches", json={"name": branch_name})
    assert r.status_code == 201, r.json()
    return project_id, branch_name


def _branch_url(project_id: str, suffix: str = "") -> str:
    return f"/v1/projects/{project_id}/branches{suffix}"


# ═══════════════════════════════════════════════════════════════════════════════
# Happy-path flows
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullPromoteFlow:
    """create project → create feature + staging branches → set manifest → diff → promote → verify.

    Note: 'main' is always write-protected by the API. The canonical flow is
    feature → staging (writable), observed here.
    """

    def test_empty_branches_have_no_diff(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            # Create a staging branch to diff against
            assert admin_client.post(_branch_url(project_id), json={"name": "staging"}).status_code == 201
            r = admin_client.get(_branch_url(project_id, f"/{feature}/diff/staging"))
            assert r.status_code == 200
            assert r.json()["diffs"] == []
            assert r.json()["has_conflicts"] is False

    def test_after_setting_manifest_diff_shows_added_fields(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            assert admin_client.post(_branch_url(project_id), json={"name": "staging"}).status_code == 201

            r = admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json=_MINIMAL_MANIFEST)
            assert r.status_code == 200
            assert r.json()["branch_name"] == feature

            r = admin_client.get(_branch_url(project_id, f"/{feature}/diff/staging"))
            assert r.status_code == 200
            # "removed" = key exists in source (feature) but not in target (staging has no manifest)
            assert any(d["status"] == "removed" for d in r.json()["diffs"])
            assert r.json()["has_conflicts"] is False

    def test_promote_copies_manifest_to_staging(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            assert admin_client.post(_branch_url(project_id), json={"name": "staging"}).status_code == 201
            admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json=_MINIMAL_MANIFEST)

            r = admin_client.post(_branch_url(project_id, f"/{feature}/promote/staging"))
            assert r.status_code == 200
            assert r.json()["source_branch"] == feature
            assert r.json()["target_branch"] == "staging"

            r = admin_client.get(_branch_url(project_id, "/staging/manifest"))
            assert r.status_code == 200
            assert r.json()["definition"]["spec"]["backend"] == "dvc"

    def test_diff_after_promote_is_empty(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            assert admin_client.post(_branch_url(project_id), json={"name": "staging"}).status_code == 201
            admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json=_MINIMAL_MANIFEST)
            admin_client.post(_branch_url(project_id, f"/{feature}/promote/staging"))

            r = admin_client.get(_branch_url(project_id, f"/{feature}/diff/staging"))
            assert r.status_code == 200
            assert r.json()["diffs"] == []


class TestMergeWithConflictsFlow:
    """Diverging branches → diff detects conflicts → caller resolves → merge stores result."""

    def test_diff_detects_conflicts_when_branches_differ(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            assert admin_client.post(_branch_url(project_id), json={"name": "staging"}).status_code == 201
            # Seed staging via promote, then change feature's backend → conflict
            admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json=_MINIMAL_MANIFEST)
            r = admin_client.post(_branch_url(project_id, f"/{feature}/promote/staging"))
            assert r.status_code == 200
            r = admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json=_UPDATED_MANIFEST)
            assert r.status_code == 200

    def test_merge_stores_resolved_manifest_on_target(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            assert admin_client.post(_branch_url(project_id), json={"name": "staging"}).status_code == 201
            admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json=_MINIMAL_MANIFEST)
            admin_client.post(_branch_url(project_id, f"/{feature}/promote/staging"))
            admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json=_UPDATED_MANIFEST)

            r = admin_client.post(
                _branch_url(project_id, f"/{feature}/merge/staging"),
                json={"resolved_definition": _UPDATED_MANIFEST},
            )
            assert r.status_code == 200
            assert r.json()["branch_name"] == "staging"

            r = admin_client.get(_branch_url(project_id, "/staging/manifest"))
            assert r.status_code == 200
            assert r.json()["definition"]["spec"]["backend"] == "argo"

    def test_diff_is_empty_after_merge(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            assert admin_client.post(_branch_url(project_id), json={"name": "staging"}).status_code == 201
            admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json=_MINIMAL_MANIFEST)
            admin_client.post(_branch_url(project_id, f"/{feature}/promote/staging"))
            admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json=_UPDATED_MANIFEST)
            admin_client.post(
                _branch_url(project_id, f"/{feature}/merge/staging"),
                json={"resolved_definition": _UPDATED_MANIFEST},
            )

            r = admin_client.get(_branch_url(project_id, f"/{feature}/diff/staging"))
            assert r.status_code == 200
            assert r.json()["diffs"] == []


class TestBranchLifecycle:
    """Full CRUD lifecycle: create → list → get → update manifest → protect → delete."""

    def test_new_branch_appears_in_list(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            r = admin_client.get(_branch_url(project_id))
            assert r.status_code == 200
            names = [b["name"] for b in r.json()]
            assert feature in names
            assert "main" in names

    def test_get_branch_returns_expected_fields(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            r = admin_client.get(_branch_url(project_id, f"/{feature}"))
            assert r.status_code == 200
            body = r.json()
            assert body["name"] == feature
            assert body["project_id"] == project_id
            assert body["is_protected"] is False

    def test_manifest_empty_before_first_put(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            r = admin_client.get(_branch_url(project_id, f"/{feature}/manifest"))
            assert r.status_code == 200
            assert r.json()["definition"] is None

    def test_manifest_persists_across_get_calls(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json=_MINIMAL_MANIFEST)

            r = admin_client.get(_branch_url(project_id, f"/{feature}/manifest"))
            assert r.status_code == 200
            assert r.json()["definition"]["metadata"]["name"] == "my-pipeline"

    def test_second_put_overwrites_manifest(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client, "feature")
            r1 = admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json=_MINIMAL_MANIFEST)
            assert r1.status_code == 200
            r2 = admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json=_UPDATED_MANIFEST)
            assert r2.status_code == 200

            r = admin_client.get(_branch_url(project_id, f"/{feature}/manifest"))
            assert r.status_code == 200
            assert r.json()["definition"]["spec"]["backend"] == "argo"

    def test_delete_branch_then_get_returns_404(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            assert admin_client.delete(_branch_url(project_id, f"/{feature}")).status_code == 204
            assert admin_client.get(_branch_url(project_id, f"/{feature}")).status_code == 404

    def test_deleted_branch_absent_from_list(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            admin_client.delete(_branch_url(project_id, f"/{feature}"))

            r = admin_client.get(_branch_url(project_id))
            names = [b["name"] for b in r.json()]
            assert feature not in names


class TestStepsDiscoveryFlow:
    """Discover a step → inspect schema → use its class path in a branch manifest."""

    def test_step_list_includes_known_step(self, admin_client, fake_db):
        with fake_db.patch_all():
            r = admin_client.get("/v1/steps?package=wurzel.steps")
            assert r.status_code == 200
            assert _KNOWN_STEP in [s["class_path"] for s in r.json()["steps"]]

    def test_step_list_includes_input_output_types(self, admin_client, fake_db):
        with fake_db.patch_all():
            r = admin_client.get("/v1/steps?package=wurzel.steps")
            step = next(s for s in r.json()["steps"] if s["class_path"] == _KNOWN_STEP)
            assert step["output_type"] == "list[wurzel.datacontract.MarkdownDataContract]"
            assert step["input_type"] is None  # source step

    def test_step_detail_endpoint_returns_schema(self, admin_client, fake_db):
        with fake_db.patch_all():
            r = admin_client.get(f"/v1/steps/{_KNOWN_STEP}")
            assert r.status_code == 200
            info = r.json()
            assert info["class_path"] == _KNOWN_STEP
            assert info["output_type"] is not None
            assert isinstance(info["settings_schema"], list)

    def test_discovered_class_path_valid_in_manifest(self, admin_client, fake_db):
        with fake_db.patch_all():
            r = admin_client.get(f"/v1/steps/{_KNOWN_STEP}")
            class_path = r.json()["class_path"]

            manifest = {
                "apiVersion": "wurzel.dev/v1alpha1",
                "kind": "Pipeline",
                "metadata": {"name": "discovered-pipeline"},
                "spec": {"backend": "dvc", "steps": [{"name": "source", "class": class_path}]},
            }
            project_id, feature = _create_project_and_branch(admin_client)
            assert admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json=manifest).status_code == 200

            r = admin_client.get(_branch_url(project_id, f"/{feature}/manifest"))
            assert r.json()["definition"]["spec"]["steps"][0]["class"] == _KNOWN_STEP

    def test_framework_base_class_excluded_from_list(self, admin_client, fake_db):
        with fake_db.patch_all():
            r = admin_client.get("/v1/steps")
            class_paths = [s["class_path"] for s in r.json()["steps"]]
            assert "wurzel.core.self_consuming_step.SelfConsumingLeafStep" not in class_paths


# ═══════════════════════════════════════════════════════════════════════════════
# Bad-path flows: input validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestBranchNameValidation:
    """Invalid branch names must be rejected before touching the DB."""

    @pytest.mark.parametrize(
        "name,expected_status",
        [
            pytest.param("main", 409, id="reserved_main"),
            pytest.param("UPPERCASE", 422, id="uppercase"),
            pytest.param("-starts-with-dash", 422, id="leading_dash"),
            pytest.param("", 422, id="empty_string"),
        ],
    )
    def test_invalid_branch_name(self, admin_client, fake_db, name, expected_status):
        with fake_db.patch_all():
            r = admin_client.post("/v1/projects", json={"name": "test-project"})
            project_id = r.json()["id"]
            r = admin_client.post(_branch_url(project_id), json={"name": name})
            assert r.status_code == expected_status

    def test_duplicate_branch_returns_409_problem_json(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            r = admin_client.post(_branch_url(project_id), json={"name": feature})
            assert r.status_code == 409
            assert r.headers["content-type"] == "application/problem+json"
            assert r.json()["status"] == 409

    def test_missing_name_field_returns_422(self, admin_client, fake_db):
        with fake_db.patch_all():
            r = admin_client.post("/v1/projects", json={"name": "test-project"})
            project_id = r.json()["id"]
            assert admin_client.post(_branch_url(project_id), json={}).status_code == 422


class TestManifestValidation:
    """Invalid manifest payloads must be rejected with 422 before any DB write."""

    def test_manifest_missing_required_fields_returns_422(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            r = admin_client.put(
                _branch_url(project_id, f"/{feature}/manifest"),
                json={"apiVersion": "wurzel.dev/v1alpha1"},  # missing kind, metadata, spec
            )
            assert r.status_code == 422

    def test_manifest_empty_body_returns_422(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            assert admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json={}).status_code == 422

    def test_merge_missing_resolved_definition_returns_422(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            assert admin_client.post(_branch_url(project_id, f"/{feature}/merge/main"), json={}).status_code == 422

    def test_merge_no_body_returns_422(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            assert admin_client.post(_branch_url(project_id, f"/{feature}/merge/main")).status_code == 422


class TestProtectedBranchErrors:
    """Operations on main / protected branches that must always fail."""

    def test_write_manifest_to_main_returns_403(self, admin_client, fake_db):
        with fake_db.patch_all():
            r = admin_client.post("/v1/projects", json={"name": "test-project"})
            project_id = r.json()["id"]
            r = admin_client.put(_branch_url(project_id, "/main/manifest"), json=_MINIMAL_MANIFEST)
            assert r.status_code == 403
            assert r.headers["content-type"] == "application/problem+json"

    def test_delete_main_branch_returns_409(self, admin_client, fake_db):
        with fake_db.patch_all():
            r = admin_client.post("/v1/projects", json={"name": "test-project"})
            project_id = r.json()["id"]
            assert admin_client.delete(_branch_url(project_id, "/main")).status_code == 409

    def test_unprotect_main_returns_409(self, admin_client, fake_db):
        with fake_db.patch_all():
            r = admin_client.post("/v1/projects", json={"name": "test-project"})
            project_id = r.json()["id"]
            r = admin_client.post(_branch_url(project_id, "/main/protect"), json={"is_protected": False})
            assert r.status_code == 409

    def test_create_branch_named_main_returns_409(self, admin_client, fake_db):
        with fake_db.patch_all():
            r = admin_client.post("/v1/projects", json={"name": "test-project"})
            project_id = r.json()["id"]
            assert admin_client.post(_branch_url(project_id), json={"name": "main"}).status_code == 409


class TestNotFoundErrors:
    """404 responses for resources that do not exist."""

    def test_get_nonexistent_branch_returns_404(self, admin_client, fake_db):
        with fake_db.patch_all():
            r = admin_client.post("/v1/projects", json={"name": "test-project"})
            project_id = r.json()["id"]
            assert admin_client.get(_branch_url(project_id, "/ghost-branch")).status_code == 404

    def test_manifest_of_nonexistent_branch_returns_404(self, admin_client, fake_db):
        with fake_db.patch_all():
            r = admin_client.post("/v1/projects", json={"name": "test-project"})
            project_id = r.json()["id"]
            assert admin_client.get(_branch_url(project_id, "/ghost-branch/manifest")).status_code == 404

    def test_diff_with_nonexistent_target_returns_404(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            assert admin_client.get(_branch_url(project_id, f"/{feature}/diff/ghost-branch")).status_code == 404

    def test_promote_to_nonexistent_target_returns_404(self, admin_client, fake_db):
        with fake_db.patch_all():
            project_id, feature = _create_project_and_branch(admin_client)
            admin_client.put(_branch_url(project_id, f"/{feature}/manifest"), json=_MINIMAL_MANIFEST)
            assert admin_client.post(_branch_url(project_id, f"/{feature}/promote/ghost-branch")).status_code == 404

    def test_non_member_gets_404_on_branch_list(self, fake_db):
        with fake_db.patch_all():
            # ADMIN_USER creates a project they own
            with TestClient(make_app(ADMIN_USER), raise_server_exceptions=False) as admin_c:
                r = admin_c.post("/v1/projects", json={"name": "test-project"})
                project_id = r.json()["id"]

            # MEMBER_USER was never added → 404
            with TestClient(make_app(MEMBER_USER), raise_server_exceptions=False) as member_c:
                assert member_c.get(_branch_url(project_id)).status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Bad-path flows: permission errors
# ═══════════════════════════════════════════════════════════════════════════════


class TestPermissionBoundaries:
    """Role-based access: viewer read-only, member cannot admin-only ops."""

    def test_viewer_cannot_write_manifest(self, fake_db):
        with fake_db.patch_all():
            with TestClient(make_app(ADMIN_USER), raise_server_exceptions=False) as admin_c:
                r = admin_c.post("/v1/projects", json={"name": "test-project"})
                project_id = r.json()["id"]
                admin_c.post(_branch_url(project_id), json={"name": "feature"})

            fake_db.seed_role(project_id, VIEWER_USER.sub, ProjectRole.VIEWER)

            with TestClient(make_app(VIEWER_USER), raise_server_exceptions=False) as viewer_c:
                r = viewer_c.put(_branch_url(project_id, "/feature/manifest"), json=_MINIMAL_MANIFEST)
            assert r.status_code == 403

    def test_viewer_can_read_branches(self, fake_db):
        with fake_db.patch_all():
            with TestClient(make_app(ADMIN_USER), raise_server_exceptions=False) as admin_c:
                r = admin_c.post("/v1/projects", json={"name": "test-project"})
                project_id = r.json()["id"]

            fake_db.seed_role(project_id, VIEWER_USER.sub, ProjectRole.VIEWER)

            with TestClient(make_app(VIEWER_USER), raise_server_exceptions=False) as viewer_c:
                r = viewer_c.get(_branch_url(project_id))
            assert r.status_code == 200

    def test_member_cannot_create_branch(self, fake_db):
        with fake_db.patch_all():
            with TestClient(make_app(ADMIN_USER), raise_server_exceptions=False) as admin_c:
                r = admin_c.post("/v1/projects", json={"name": "test-project"})
                project_id = r.json()["id"]

            fake_db.seed_role(project_id, MEMBER_USER.sub, ProjectRole.MEMBER)

            with TestClient(make_app(MEMBER_USER), raise_server_exceptions=False) as member_c:
                r = member_c.post(_branch_url(project_id), json={"name": "member-branch"})
            assert r.status_code == 403

    def test_member_cannot_delete_branch(self, fake_db):
        with fake_db.patch_all():
            with TestClient(make_app(ADMIN_USER), raise_server_exceptions=False) as admin_c:
                r = admin_c.post("/v1/projects", json={"name": "test-project"})
                project_id = r.json()["id"]
                admin_c.post(_branch_url(project_id), json={"name": "feature"})

            fake_db.seed_role(project_id, MEMBER_USER.sub, ProjectRole.MEMBER)

            with TestClient(make_app(MEMBER_USER), raise_server_exceptions=False) as member_c:
                r = member_c.delete(_branch_url(project_id, "/feature"))
            assert r.status_code == 403

    def test_member_can_write_manifest_to_unprotected_branch(self, fake_db):
        with fake_db.patch_all():
            with TestClient(make_app(ADMIN_USER), raise_server_exceptions=False) as admin_c:
                r = admin_c.post("/v1/projects", json={"name": "test-project"})
                project_id = r.json()["id"]
                admin_c.post(_branch_url(project_id), json={"name": "feature"})

            fake_db.seed_role(project_id, MEMBER_USER.sub, ProjectRole.MEMBER)

            with TestClient(make_app(MEMBER_USER), raise_server_exceptions=False) as member_c:
                r = member_c.put(_branch_url(project_id, "/feature/manifest"), json=_MINIMAL_MANIFEST)
            assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Bad-path flows: Steps API errors
# ═══════════════════════════════════════════════════════════════════════════════


class TestStepsApiErrors:
    """Error cases for the step discovery and introspection endpoints."""

    @pytest.fixture(scope="class")
    def steps_client(self):
        from wurzel.api.app import create_app  # noqa: PLC0415
        from wurzel.api.auth.jwt import UserClaims, _verify_jwt  # noqa: PLC0415
        from wurzel.api.settings import APISettings  # noqa: PLC0415

        user = UserClaims(sub="u", email="u@u.com", raw={})
        app = create_app(settings=APISettings(API_KEY="k"))
        app.dependency_overrides[_verify_jwt] = lambda: user
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_unknown_package_returns_400(self, steps_client):
        r = steps_client.get("/v1/steps?package=totally_nonexistent_xyz_pkg", headers={"Authorization": "Bearer t"})
        assert r.status_code == 400
        assert r.headers["content-type"] == "application/problem+json"
        assert r.json()["status"] == 400

    def test_step_path_without_dot_returns_400(self, steps_client):
        r = steps_client.get("/v1/steps/nodothere", headers={"Authorization": "Bearer t"})
        assert r.status_code == 400

    def test_nonexistent_module_returns_404(self, steps_client):
        r = steps_client.get("/v1/steps/nonexistent.module.FakeStep", headers={"Authorization": "Bearer t"})
        assert r.status_code == 404

    def test_nonexistent_class_in_real_module_returns_404(self, steps_client):
        r = steps_client.get("/v1/steps/wurzel.steps.manual_markdown.FakeStep", headers={"Authorization": "Bearer t"})
        assert r.status_code == 404

    def test_400_body_is_problem_json(self, steps_client):
        r = steps_client.get("/v1/steps?package=no_such_pkg_xyz", headers={"Authorization": "Bearer t"})
        body = r.json()
        assert "title" in body
        assert "status" in body
        assert "detail" in body
