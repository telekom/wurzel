# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.supabase_e2e


@pytest.mark.parametrize(
    "role,expected_status",
    [
        ("admin", 200),
        ("member", 200),
        ("secret_editor", 200),
        ("viewer", 200),
        ("no_role", 404),
    ],
)
def test_get_project_role_matrix(client, role_headers, project_context, role, expected_status):
    project_id = project_context["project_id"]
    response = client.get(f"/v1/projects/{project_id}", headers=role_headers[role])
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "role,expected_status",
    [
        ("admin", 200),
        ("member", 403),
        ("secret_editor", 403),
        ("viewer", 403),
        ("no_role", 404),
    ],
)
def test_update_project_role_matrix(client, role_headers, project_context, role, expected_status):
    project_id = project_context["project_id"]
    response = client.put(
        f"/v1/projects/{project_id}",
        json={"description": f"updated-by-{role}"},
        headers=role_headers[role],
    )
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "role,expected_status",
    [
        ("admin", 200),
        ("member", 200),
        ("secret_editor", 200),
        ("viewer", 200),
        ("no_role", 404),
    ],
)
def test_list_members_role_matrix(client, role_headers, project_context, role, expected_status):
    project_id = project_context["project_id"]
    response = client.get(f"/v1/projects/{project_id}/members", headers=role_headers[role])
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "role,expected_status",
    [
        ("admin", 201),
        ("member", 403),
        ("secret_editor", 403),
        ("viewer", 403),
        ("no_role", 404),
    ],
)
def test_create_branch_role_matrix(client, role_headers, project_context, role, expected_status):
    project_id = project_context["project_id"]
    response = client.post(
        f"/v1/projects/{project_id}/branches",
        json={"name": f"b-{role}-{uuid.uuid4().hex[:4]}"},
        headers=role_headers[role],
    )
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "role,expected_status",
    [
        ("admin", 200),
        ("member", 200),
        ("secret_editor", 403),
        ("viewer", 403),
        ("no_role", 404),
    ],
)
def test_set_branch_manifest_role_matrix(client, role_headers, project_context, role, expected_status):
    project_id = project_context["project_id"]
    branch_name = project_context["feature_branch"]
    body = {
        "apiVersion": "wurzel.dev/v1alpha1",
        "kind": "Pipeline",
        "metadata": {"name": f"manifest-{role}"},
        "spec": {
            "backend": "argo",
            "steps": [{"name": "source", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"}],
        },
    }
    response = client.put(
        f"/v1/projects/{project_id}/branches/{branch_name}/manifest",
        json=body,
        headers=role_headers[role],
    )
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "role,expected_status",
    [
        ("admin", 200),
        ("member", 200),
        ("secret_editor", 200),
        ("viewer", 200),
        ("no_role", 404),
    ],
)
def test_diff_branches_role_matrix(client, role_headers, project_context, role, expected_status):
    project_id = project_context["project_id"]
    create_target = client.post(
        f"/v1/projects/{project_id}/branches",
        json={"name": "feature-b"},
        headers=role_headers["admin"],
    )
    assert create_target.status_code == 201

    response = client.get(
        f"/v1/projects/{project_id}/branches/feature-a/diff/feature-b",
        headers=role_headers[role],
    )
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "role,expected_status",
    [
        ("admin", 200),
        ("member", 200),
        ("secret_editor", 403),
        ("viewer", 403),
        ("no_role", 404),
    ],
)
def test_promote_role_matrix(client, role_headers, project_context, role, expected_status):
    project_id = project_context["project_id"]
    create_target = client.post(
        f"/v1/projects/{project_id}/branches",
        json={"name": "feature-c"},
        headers=role_headers["admin"],
    )
    assert create_target.status_code == 201

    response = client.post(
        f"/v1/projects/{project_id}/branches/feature-a/promote/feature-c",
        headers=role_headers[role],
    )
    assert response.status_code == expected_status


def test_branch_admin_happy_and_error_paths(client, role_headers, project_context):
    project_id = project_context["project_id"]

    reserved_main = client.post(
        f"/v1/projects/{project_id}/branches",
        json={"name": "main"},
        headers=role_headers["admin"],
    )
    assert reserved_main.status_code == 409

    invalid_name = client.post(
        f"/v1/projects/{project_id}/branches",
        json={"name": "Invalid Name With Spaces"},
        headers=role_headers["admin"],
    )
    assert invalid_name.status_code == 422

    protect_feature = client.post(
        f"/v1/projects/{project_id}/branches/feature-a/protect",
        json={"is_protected": True},
        headers=role_headers["admin"],
    )
    assert protect_feature.status_code == 200

    unprotect_main = client.post(
        f"/v1/projects/{project_id}/branches/main/protect",
        json={"is_protected": False},
        headers=role_headers["admin"],
    )
    assert unprotect_main.status_code == 409

    delete_main = client.delete(
        f"/v1/projects/{project_id}/branches/main",
        headers=role_headers["admin"],
    )
    assert delete_main.status_code == 409


def test_manifest_submit_happy_and_error_paths(client, role_headers, project_context):
    project_id = project_context["project_id"]

    create_no_manifest = client.post(
        f"/v1/projects/{project_id}/branches",
        json={"name": "feature-no-manifest"},
        headers=role_headers["admin"],
    )
    assert create_no_manifest.status_code == 201

    submit_missing_manifest = client.post(
        f"/v1/projects/{project_id}/branches/feature-no-manifest/manifest/submit",
        headers=role_headers["admin"],
    )
    assert submit_missing_manifest.status_code == 409

    submit_as_member = client.post(
        f"/v1/projects/{project_id}/branches/feature-a/manifest/submit",
        headers=role_headers["member"],
    )
    assert submit_as_member.status_code == 202
    assert submit_as_member.json()["run_status"] == "pending"


def test_merge_and_promote_error_paths(client, role_headers, project_context):
    project_id = project_context["project_id"]

    create_target = client.post(
        f"/v1/projects/{project_id}/branches",
        json={"name": "feature-target"},
        headers=role_headers["admin"],
    )
    assert create_target.status_code == 201

    merge_body = {
        "resolved_definition": {
            "apiVersion": "wurzel.dev/v1alpha1",
            "kind": "Pipeline",
            "metadata": {"name": "merged-manifest"},
            "spec": {
                "backend": "dvc",
                "steps": [{"name": "source", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep"}],
            },
        }
    }
    merge_ok = client.post(
        f"/v1/projects/{project_id}/branches/feature-a/merge/feature-target",
        json=merge_body,
        headers=role_headers["admin"],
    )
    assert merge_ok.status_code == 200

    create_empty = client.post(
        f"/v1/projects/{project_id}/branches",
        json={"name": "feature-empty"},
        headers=role_headers["admin"],
    )
    assert create_empty.status_code == 201

    promote_missing = client.post(
        f"/v1/projects/{project_id}/branches/feature-empty/promote/feature-target",
        headers=role_headers["admin"],
    )
    assert promote_missing.status_code == 409
