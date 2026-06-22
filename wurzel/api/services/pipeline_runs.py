# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Service layer for branch pipeline run creation and execution."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from wurzel.api.backends.supabase.client import (
    db_create_branch_pipeline_run,
    db_get_branch_pipeline_run,
    db_patch_manifest_status,
    db_update_branch_pipeline_run,
)
from wurzel.api.services.pipeline_backends import get_pipeline_run_adapter
from wurzel.manifest.models import PipelineManifest

logger = logging.getLogger(__name__)


def _iso_now() -> str:
    return datetime.now(tz=UTC).isoformat()


async def create_pipeline_run_from_manifest_row(
    *,
    branch_id: uuid.UUID,
    manifest_row: dict,
    created_by: str,
    rerun_of_id: uuid.UUID | None = None,
) -> dict:
    """Create a queued run row from the current branch manifest row."""
    manifest = PipelineManifest.model_validate(manifest_row["definition"])
    manifest_id = uuid.UUID(manifest_row["id"]) if manifest_row.get("id") else None
    return await db_create_branch_pipeline_run(
        branch_id=branch_id,
        manifest_id=manifest_id,
        manifest_snapshot=manifest.model_dump(mode="json"),
        backend_name=manifest.spec.backend,
        created_by=created_by,
        rerun_of_id=rerun_of_id,
    )


async def create_pipeline_run_from_snapshot_row(
    *,
    branch_id: uuid.UUID,
    source_run_row: dict,
    created_by: str,
) -> dict:
    """Create a queued rerun row from an existing run snapshot."""
    snapshot = source_run_row["manifest_snapshot"]
    manifest = PipelineManifest.model_validate(snapshot)
    source_run_id = uuid.UUID(source_run_row["id"])
    return await db_create_branch_pipeline_run(
        branch_id=branch_id,
        manifest_id=uuid.UUID(source_run_row["manifest_id"]) if source_run_row.get("manifest_id") else None,
        manifest_snapshot=manifest.model_dump(mode="json"),
        backend_name=manifest.spec.backend,
        created_by=created_by,
        rerun_of_id=source_run_id,
    )


async def execute_pipeline_run_bg(run_id: uuid.UUID) -> None:
    """Execute one run in the background and persist run state transitions."""
    run_row = await db_get_branch_pipeline_run(run_id)
    if run_row is None:
        logger.error("Pipeline run %s no longer exists.", run_id)
        return

    branch_id = uuid.UUID(run_row["branch_id"])
    await db_update_branch_pipeline_run(
        run_id,
        {
            "status": "running",
            "started_at": _iso_now(),
            "error_message": None,
        },
    )
    await db_patch_manifest_status(branch_id, "running")

    try:
        manifest = PipelineManifest.model_validate(run_row["manifest_snapshot"])
        adapter = get_pipeline_run_adapter(run_row["backend_name"])
        result = await adapter.execute(manifest, run_id)
    except (ValueError, TypeError, RuntimeError, OSError, ImportError) as exc:
        logger.exception("Pipeline run %s failed: %s", run_id, exc)
        await db_update_branch_pipeline_run(
            run_id,
            {
                "status": "failed",
                "finished_at": _iso_now(),
                "error_message": str(exc),
            },
        )
        await db_patch_manifest_status(branch_id, "failed")
        return

    await db_update_branch_pipeline_run(
        run_id,
        {
            "status": "succeeded",
            "backend_run_id": result.backend_run_id,
            "logs_url": result.logs_url,
            "artifacts_url": result.artifacts_url,
            "finished_at": _iso_now(),
            "error_message": None,
        },
    )
    await db_patch_manifest_status(branch_id, "succeeded")
