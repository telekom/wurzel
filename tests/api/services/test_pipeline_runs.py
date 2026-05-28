# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for pipeline run service helpers."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

from wurzel.api.services.pipeline_backends import BackendExecutionResult
from wurzel.api.services.pipeline_runs import (
    create_pipeline_run_from_manifest_row,
    create_pipeline_run_from_snapshot_row,
    execute_pipeline_run_bg,
)

_BRANCH_ID = uuid.uuid4()
_RUN_ID = uuid.uuid4()
_NOW = datetime(2025, 1, 1, 12, 0, 0).isoformat()
_MANIFEST = {
    "apiVersion": "wurzel.dev/v1alpha1",
    "kind": "Pipeline",
    "metadata": {"name": "test-pipeline"},
    "spec": {
        "backend": "dvc",
        "steps": [
            {
                "name": "source",
                "class": "wurzel.steps.manual_markdown.ManualMarkdownStep",
            }
        ],
    },
}


def test_create_pipeline_run_from_manifest_row_uses_manifest_backend():
    manifest_row = {
        "id": str(uuid.uuid4()),
        "branch_id": str(_BRANCH_ID),
        "definition": _MANIFEST,
    }
    with patch(
        "wurzel.api.services.pipeline_runs.db_create_branch_pipeline_run",
        new_callable=AsyncMock,
        return_value={"id": str(_RUN_ID), "backend_name": "dvc"},
    ) as mock_create:
        row = asyncio.run(
            create_pipeline_run_from_manifest_row(
                branch_id=_BRANCH_ID,
                manifest_row=manifest_row,
                created_by="user-1",
            )
        )

    assert row["id"] == str(_RUN_ID)
    assert mock_create.await_args.kwargs["backend_name"] == "dvc"


def test_create_pipeline_run_from_snapshot_row_tracks_rerun_origin():
    source_run = {
        "id": str(_RUN_ID),
        "manifest_id": str(uuid.uuid4()),
        "manifest_snapshot": _MANIFEST,
    }
    with patch(
        "wurzel.api.services.pipeline_runs.db_create_branch_pipeline_run",
        new_callable=AsyncMock,
        return_value={"id": str(uuid.uuid4())},
    ) as mock_create:
        asyncio.run(
            create_pipeline_run_from_snapshot_row(
                branch_id=_BRANCH_ID,
                source_run_row=source_run,
                created_by="user-2",
            )
        )

    assert mock_create.await_args.kwargs["rerun_of_id"] == _RUN_ID


def test_execute_pipeline_run_bg_marks_successful_run():
    run_row = {
        "id": str(_RUN_ID),
        "branch_id": str(_BRANCH_ID),
        "manifest_snapshot": _MANIFEST,
        "backend_name": "dvc",
        "created_at": _NOW,
    }

    class _Adapter:
        async def execute(self, manifest, run_id):  # noqa: ANN001
            _ = manifest
            _ = run_id
            return BackendExecutionResult(
                backend_run_id="backend-123",
                logs_url="file:///tmp/run.log",
                artifacts_url="file:///tmp/artifact.yaml",
            )

    with (
        patch("wurzel.api.services.pipeline_runs.db_get_branch_pipeline_run", new_callable=AsyncMock, return_value=run_row),
        patch("wurzel.api.services.pipeline_runs.db_update_branch_pipeline_run", new_callable=AsyncMock) as mock_update,
        patch("wurzel.api.services.pipeline_runs.db_patch_manifest_status", new_callable=AsyncMock),
        patch("wurzel.api.services.pipeline_runs.get_pipeline_run_adapter", return_value=_Adapter()),
    ):
        asyncio.run(execute_pipeline_run_bg(_RUN_ID))

    last_update_fields = mock_update.await_args_list[-1].args[1]
    assert last_update_fields["status"] == "succeeded"
    assert last_update_fields["backend_run_id"] == "backend-123"


def test_execute_pipeline_run_bg_marks_failed_run_on_adapter_error():
    run_row = {
        "id": str(_RUN_ID),
        "branch_id": str(_BRANCH_ID),
        "manifest_snapshot": _MANIFEST,
        "backend_name": "dvc",
        "created_at": _NOW,
    }

    class _Adapter:
        async def execute(self, manifest, run_id):  # noqa: ANN001
            _ = manifest
            _ = run_id
            raise RuntimeError("boom")

    with (
        patch("wurzel.api.services.pipeline_runs.db_get_branch_pipeline_run", new_callable=AsyncMock, return_value=run_row),
        patch("wurzel.api.services.pipeline_runs.db_update_branch_pipeline_run", new_callable=AsyncMock) as mock_update,
        patch("wurzel.api.services.pipeline_runs.db_patch_manifest_status", new_callable=AsyncMock),
        patch("wurzel.api.services.pipeline_runs.get_pipeline_run_adapter", return_value=_Adapter()),
    ):
        asyncio.run(execute_pipeline_run_bg(_RUN_ID))

    last_update_fields = mock_update.await_args_list[-1].args[1]
    assert last_update_fields["status"] == "failed"
    assert "boom" in last_update_fields["error_message"]


def test_execute_pipeline_run_bg_returns_when_run_missing():
    with patch(
        "wurzel.api.services.pipeline_runs.db_get_branch_pipeline_run",
        new_callable=AsyncMock,
        return_value=None,
    ):
        asyncio.run(execute_pipeline_run_bg(_RUN_ID))
