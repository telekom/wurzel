# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Branch CRUD + manifest + diff/merge/promote routes.

Routes (all under /v1/projects/{project_id}/branches)
------
``POST   /``                                      — create branch (admin)
``GET    /``                                      — list branches (any member)
``GET    /{branch_name}``                         — get branch metadata (any member)
``PUT    /{branch_name}``                         — update promotes_to (admin)
``DELETE /{branch_name}``                         — delete branch (admin; main blocked)
``POST   /{branch_name}/protect``                 — set is_protected (admin)

``GET    /{branch_name}/manifest``                — get manifest (any member)
``PUT    /{branch_name}/manifest``                — set/update manifest (branch-write guard)
``POST   /{branch_name}/manifest/submit``         — submit for execution (admin or member)

``GET    /{branch_name}/diff/{target_branch}``    — field-level diff (any member)
``POST   /{branch_name}/merge/{target_branch}``   — merge with resolved payload (branch-write guard on target)
``POST   /{branch_name}/promote/{target_branch}`` — verbatim promote (branch-write guard on target)
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from fastapi import status as http_status

from wurzel.api.auth.jwt import CurrentUser
from wurzel.api.auth.permissions import (
    RequireAdmin,
    RequireAnyRole,
    RequireMember,
    _resolve_project_role,
)
from wurzel.api.backends.supabase.client import (
    db_create_branch,
    db_delete_branch,
    db_get_branch,
    db_get_branch_manifest,
    db_list_branches,
    db_patch_manifest_status,
    db_update_branch,
    db_upsert_branch_manifest,
)
from wurzel.api.errors import APIError
from wurzel.api.routes.branch.data import (
    Branch,
    BranchDiff,
    BranchManifest,
    CreateBranchRequest,
    FieldDiff,
    MergeRequest,
    PromoteResponse,
    ProtectBranchRequest,
    UpdateBranchRequest,
)
from wurzel.manifest.models import PipelineManifest

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _row_to_branch(row: dict) -> Branch:
    return Branch(
        id=uuid.UUID(row["id"]),
        project_id=uuid.UUID(row["project_id"]),
        name=row["name"],
        is_protected=row.get("is_protected", False),
        is_default=row.get("is_default", False),
        promotes_to_id=uuid.UUID(row["promotes_to_id"]) if row.get("promotes_to_id") else None,
        promotes_to_name=row.get("promotes_to_name"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def _get_branch_or_404(project_id: uuid.UUID, branch_name: str) -> dict:
    row = await db_get_branch(project_id, branch_name)
    if row is None:
        raise APIError(
            status_code=http_status.HTTP_404_NOT_FOUND,
            title="Branch not found",
            detail=f"No branch '{branch_name}' in project {project_id}",
        )
    return row


def _flatten_dict(obj: Any, prefix: str = "") -> dict[str, Any]:
    """Recursively flatten a dict/list into dot-path keys."""
    result: dict[str, Any] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key
            result.update(_flatten_dict(value, full_key))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            result.update(_flatten_dict(item, f"{prefix}[{i}]"))
    else:
        result[prefix] = obj
    return result


def _compute_diff(
    source: PipelineManifest | None,
    target: PipelineManifest | None,
    source_name: str,
    target_name: str,
) -> BranchDiff:
    """Produce a field-level diff between two manifests."""
    source_flat = _flatten_dict(source.model_dump(mode="json") if source else {})
    target_flat = _flatten_dict(target.model_dump(mode="json") if target else {})

    all_keys = set(source_flat.keys()) | set(target_flat.keys())
    diffs: list[FieldDiff] = []
    has_conflicts = False

    for key in sorted(all_keys):
        sv = source_flat.get(key)
        tv = target_flat.get(key)
        if key not in source_flat:
            status = "added"
        elif key not in target_flat:
            status = "removed"
        elif sv != tv:
            status = "changed"
            has_conflicts = True
        else:
            status = "unchanged"
        if status != "unchanged":
            diffs.append(FieldDiff(path=key, source_value=sv, target_value=tv, status=status))

    return BranchDiff(
        source_branch=source_name,
        target_branch=target_name,
        source_definition=source,
        target_definition=target,
        diffs=diffs,
        has_conflicts=has_conflicts,
    )


async def _ensure_branch_write_allowed(
    project_id: uuid.UUID,
    branch_name: str,
    user: CurrentUser,
) -> None:
    """Raise 403 if the user cannot write to this branch."""
    from wurzel.api.backends.supabase.client import get_branch_protection  # noqa: PLC0415
    from wurzel.api.routes.member.data import ProjectRole  # noqa: PLC0415

    if branch_name == "main":
        raise APIError(
            status_code=http_status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail="The 'main' branch is protected and cannot be modified directly.",
        )

    role = await _resolve_project_role(project_id, user)
    if role is None:
        raise APIError(
            status_code=http_status.HTTP_404_NOT_FOUND,
            title="Project not found",
            detail=f"Project {project_id} does not exist or you are not a member.",
        )

    is_protected = await get_branch_protection(project_id, branch_name)
    if is_protected and role != ProjectRole.ADMIN:
        raise APIError(
            status_code=http_status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail=f"Branch '{branch_name}' is protected. Only admins can write to it.",
        )

    if role not in (ProjectRole.ADMIN, ProjectRole.MEMBER):
        raise APIError(
            status_code=http_status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail="Writing to a branch requires at least the 'member' role.",
        )


async def _execute_manifest_bg(
    branch_id: uuid.UUID,
    definition: PipelineManifest,
    backend_name: str,
) -> None:
    """Background task: execute the manifest and persist the final status."""
    await db_patch_manifest_status(branch_id, "running")
    try:
        if backend_name == "inline":
            from wurzel.executors.base_executor import BaseStepExecutor  # noqa: PLC0415
            from wurzel.manifest.builder import ManifestBuilder  # noqa: PLC0415

            builder = ManifestBuilder(definition)
            step_graph = builder.build_step_graph()
            executor = BaseStepExecutor()
            for step_name in builder.find_terminal_steps():
                executor.execute_step(step_graph[step_name])
        else:
            import tempfile  # noqa: PLC0415

            from wurzel.manifest.generator import ManifestGenerator  # noqa: PLC0415

            with tempfile.TemporaryDirectory() as tmp:
                generator = ManifestGenerator(definition)
                generator.generate(Path(tmp) / str(branch_id))

        await db_patch_manifest_status(branch_id, "succeeded")
    except Exception:
        import logging  # noqa: PLC0415

        logging.getLogger(__name__).exception("Manifest run failed for branch_id=%s", branch_id)
        await db_patch_manifest_status(branch_id, "failed")


# ── Branch CRUD ───────────────────────────────────────────────────────────────


@router.post("", response_model=Branch, status_code=http_status.HTTP_201_CREATED)
async def create_branch(
    project_id: uuid.UUID,
    body: CreateBranchRequest,
    _access: RequireAdmin,
) -> Branch:
    """Create a new branch in the project (admin only)."""
    if body.name == "main":
        raise APIError(
            status_code=http_status.HTTP_409_CONFLICT,
            title="Reserved branch name",
            detail="'main' is created automatically and cannot be created manually.",
        )
    existing = await db_get_branch(project_id, body.name)
    if existing is not None:
        raise APIError(
            status_code=http_status.HTTP_409_CONFLICT,
            title="Branch already exists",
            detail=f"A branch named '{body.name}' already exists in this project.",
        )
    row = await db_create_branch(
        project_id,
        body.name,
        promotes_to_id=body.promotes_to_id,
    )
    return _row_to_branch(row)


@router.get("", response_model=list[Branch])
async def list_branches(
    project_id: uuid.UUID,
    _access: RequireAnyRole,
) -> list[Branch]:
    """List all branches in the project (any member)."""
    rows = await db_list_branches(project_id)
    return [_row_to_branch(r) for r in rows]


@router.get("/{branch_name}", response_model=Branch)
async def get_branch(
    project_id: uuid.UUID,
    branch_name: str,
    _access: RequireAnyRole,
) -> Branch:
    """Return branch metadata (any member)."""
    row = await _get_branch_or_404(project_id, branch_name)
    return _row_to_branch(row)


@router.put("/{branch_name}", response_model=Branch)
async def update_branch(
    project_id: uuid.UUID,
    branch_name: str,
    body: UpdateBranchRequest,
    _access: RequireAdmin,
) -> Branch:
    """Update a branch's promotes_to pointer (admin only)."""
    await _get_branch_or_404(project_id, branch_name)
    fields: dict = {}
    if body.promotes_to_id is not None:
        fields["promotes_to_id"] = str(body.promotes_to_id)
    elif "promotes_to_id" in body.model_fields_set:
        fields["promotes_to_id"] = None
    row = await db_update_branch(project_id, branch_name, fields) if fields else await db_get_branch(project_id, branch_name)
    return _row_to_branch(row)  # type: ignore[arg-type]


@router.delete("/{branch_name}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_branch(
    project_id: uuid.UUID,
    branch_name: str,
    _access: RequireAdmin,
) -> None:
    """Delete a branch (admin only). The 'main' branch cannot be deleted."""
    if branch_name == "main":
        raise APIError(
            status_code=http_status.HTTP_409_CONFLICT,
            title="Cannot delete main",
            detail="The 'main' branch is permanent and cannot be deleted.",
        )
    await _get_branch_or_404(project_id, branch_name)
    await db_delete_branch(project_id, branch_name)


@router.post("/{branch_name}/protect", response_model=Branch)
async def protect_branch(
    project_id: uuid.UUID,
    branch_name: str,
    body: ProtectBranchRequest,
    _access: RequireAdmin,
) -> Branch:
    """Set or clear the protected flag on a branch (admin only).

    The 'main' branch is always protected and cannot be unprotected.
    """
    if branch_name == "main" and not body.is_protected:
        raise APIError(
            status_code=http_status.HTTP_409_CONFLICT,
            title="Cannot unprotect main",
            detail="The 'main' branch must always be protected.",
        )
    await _get_branch_or_404(project_id, branch_name)
    row = await db_update_branch(project_id, branch_name, {"is_protected": body.is_protected})
    return _row_to_branch(row)  # type: ignore[arg-type]


# ── Manifest ──────────────────────────────────────────────────────────────────


@router.get("/{branch_name}/manifest", response_model=BranchManifest)
async def get_branch_manifest(
    project_id: uuid.UUID,
    branch_name: str,
    _access: RequireAnyRole,
) -> BranchManifest:
    """Return the manifest stored on this branch (any member)."""
    branch_row = await _get_branch_or_404(project_id, branch_name)
    branch_id = uuid.UUID(branch_row["id"])
    manifest_row = await db_get_branch_manifest(branch_id)
    definition = None
    updated_at = None
    if manifest_row:
        definition = PipelineManifest.model_validate(manifest_row["definition"])
        updated_at = manifest_row.get("updated_at")
    return BranchManifest(
        branch_id=branch_id,
        branch_name=branch_name,
        definition=definition,
        updated_at=updated_at,
    )


@router.put("/{branch_name}/manifest", response_model=BranchManifest)
async def set_branch_manifest(
    project_id: uuid.UUID,
    branch_name: str,
    body: PipelineManifest,
    user: CurrentUser,
) -> BranchManifest:
    """Store a manifest on this branch.

    Write rules:
    - ``main`` → always 403
    - Protected branch → admin only
    - Unprotected branch → admin or member
    - ``secret_editor`` → only secret-typed fields in the manifest definition are applied
    """
    from wurzel.api.routes.member.data import ProjectRole  # noqa: PLC0415

    role = await _resolve_project_role(project_id, user)
    if role is None:
        raise APIError(
            status_code=http_status.HTTP_404_NOT_FOUND,
            title="Project not found",
            detail=f"Project {project_id} does not exist or you are not a member.",
        )

    await _ensure_branch_write_allowed(project_id, branch_name, user)

    branch_row = await _get_branch_or_404(project_id, branch_name)
    branch_id = uuid.UUID(branch_row["id"])

    if role == ProjectRole.SECRET_EDITOR:
        # Only merge secret fields into the existing manifest
        existing_row = await db_get_branch_manifest(branch_id)
        if existing_row is None:
            raise APIError(
                status_code=http_status.HTTP_409_CONFLICT,
                title="No manifest to patch",
                detail="secret_editor can only patch an existing manifest's secret fields.",
            )
        existing = PipelineManifest.model_validate(existing_row["definition"])
        definition_dict = _apply_secret_fields_only(existing, body)
    else:
        definition_dict = body.model_dump(mode="json")

    row = await db_upsert_branch_manifest(branch_id, definition_dict)
    return BranchManifest(
        branch_id=branch_id,
        branch_name=branch_name,
        definition=PipelineManifest.model_validate(row["definition"]),
        updated_at=row.get("updated_at"),
    )


def _apply_secret_fields_only(existing: PipelineManifest, patch: PipelineManifest) -> dict:
    """Merge only the secret fields from *patch* into *existing* and return the merged dict.

    Uses the step discovery schema to identify which fields are SecretStr.
    """
    from typing import get_args  # noqa: PLC0415

    from pydantic import SecretStr  # noqa: PLC0415

    existing_dict = existing.model_dump(mode="json")
    patch_dict = patch.model_dump(mode="json")

    # Walk steps and merge secret fields
    existing_steps = existing_dict.get("spec", {}).get("steps", [])
    patch_steps = patch_dict.get("spec", {}).get("steps", [])

    for i, patch_step in enumerate(patch_steps):
        if i >= len(existing_steps):
            break
        ex_step = existing_steps[i]
        step_class_path = patch_step.get("class", "")
        try:
            import importlib  # noqa: PLC0415

            parts = step_class_path.rsplit(".", 1)
            if len(parts) == 2:
                mod = importlib.import_module(parts[0])
                step_cls = getattr(mod, parts[1], None)
                if step_cls is not None:
                    from typing import get_type_hints  # noqa: PLC0415

                    hints = get_type_hints(step_cls)
                    for field, annotation in hints.items():
                        is_secret = annotation is SecretStr or SecretStr in get_args(annotation)
                        if is_secret and field in patch_step:
                            ex_step[field] = patch_step[field]
        except Exception:
            pass

    return existing_dict


@router.post("/{branch_name}/manifest/submit", status_code=http_status.HTTP_202_ACCEPTED)
async def submit_branch_manifest(
    project_id: uuid.UUID,
    branch_name: str,
    background_tasks: BackgroundTasks,
    _access: RequireMember,
    backend: str = "inline",
) -> dict:
    """Submit the branch manifest for execution (admin or member)."""
    branch_row = await _get_branch_or_404(project_id, branch_name)
    branch_id = uuid.UUID(branch_row["id"])
    manifest_row = await db_get_branch_manifest(branch_id)
    if manifest_row is None:
        raise APIError(
            status_code=http_status.HTTP_409_CONFLICT,
            title="No manifest",
            detail=f"Branch '{branch_name}' has no manifest to submit.",
        )
    definition = PipelineManifest.model_validate(manifest_row["definition"])
    background_tasks.add_task(_execute_manifest_bg, branch_id, definition, backend)
    return {"branch_name": branch_name, "run_status": "pending", "message": "Manifest submitted"}


# ── Diff / Merge / Promote ────────────────────────────────────────────────────


@router.get("/{branch_name}/diff/{target_branch}", response_model=BranchDiff)
async def diff_branches(
    project_id: uuid.UUID,
    branch_name: str,
    target_branch: str,
    _access: RequireAnyRole,
) -> BranchDiff:
    """Return a field-level diff between the source and target branch manifests (any member)."""
    source_row = await _get_branch_or_404(project_id, branch_name)
    target_row = await _get_branch_or_404(project_id, target_branch)

    source_manifest_row = await db_get_branch_manifest(uuid.UUID(source_row["id"]))
    target_manifest_row = await db_get_branch_manifest(uuid.UUID(target_row["id"]))

    source_def = PipelineManifest.model_validate(source_manifest_row["definition"]) if source_manifest_row else None
    target_def = PipelineManifest.model_validate(target_manifest_row["definition"]) if target_manifest_row else None

    return _compute_diff(source_def, target_def, branch_name, target_branch)


@router.post("/{branch_name}/merge/{target_branch}", response_model=BranchManifest)
async def merge_into_target(
    project_id: uuid.UUID,
    branch_name: str,
    target_branch: str,
    body: MergeRequest,
    user: CurrentUser,
) -> BranchManifest:
    """Write the caller-resolved manifest to the target branch.

    The UI is expected to call ``GET /{source}/diff/{target}`` first,
    present the side-by-side view, and then POST the resolved payload here.
    """
    await _ensure_branch_write_allowed(project_id, target_branch, user)
    await _get_branch_or_404(project_id, branch_name)
    target_row = await _get_branch_or_404(project_id, target_branch)
    target_id = uuid.UUID(target_row["id"])

    definition_dict = body.resolved_definition.model_dump(mode="json")
    row = await db_upsert_branch_manifest(target_id, definition_dict)
    return BranchManifest(
        branch_id=target_id,
        branch_name=target_branch,
        definition=PipelineManifest.model_validate(row["definition"]),
        updated_at=row.get("updated_at"),
    )


@router.post("/{branch_name}/promote/{target_branch}", response_model=PromoteResponse)
async def promote_to_target(
    project_id: uuid.UUID,
    branch_name: str,
    target_branch: str,
    user: CurrentUser,
) -> PromoteResponse:
    """Copy the source branch manifest verbatim to the target branch."""
    await _ensure_branch_write_allowed(project_id, target_branch, user)
    source_row = await _get_branch_or_404(project_id, branch_name)
    target_row = await _get_branch_or_404(project_id, target_branch)

    source_manifest_row = await db_get_branch_manifest(uuid.UUID(source_row["id"]))
    if source_manifest_row is None:
        raise APIError(
            status_code=http_status.HTTP_409_CONFLICT,
            title="No manifest to promote",
            detail=f"Branch '{branch_name}' has no manifest.",
        )

    target_id = uuid.UUID(target_row["id"])
    row = await db_upsert_branch_manifest(target_id, source_manifest_row["definition"])
    return PromoteResponse(
        source_branch=branch_name,
        target_branch=target_branch,
        manifest_id=uuid.UUID(row["id"]),
    )
