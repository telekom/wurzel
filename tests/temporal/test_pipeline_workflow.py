# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

pytest.importorskip("temporalio")

pytestmark = pytest.mark.skipif(
    os.environ.get("WURZEL_TEST_TEMPORAL") != "1",
    reason="Embedded Temporal tests: set WURZEL_TEST_TEMPORAL=1 (may download test server on first run).",
)

from temporalio.testing import WorkflowEnvironment  # pylint: disable=wrong-import-position
from temporalio.worker import Worker  # pylint: disable=wrong-import-position

from wurzel.steps.duplication import DropDuplicationStep  # pylint: disable=wrong-import-position
from wurzel.steps.manual_markdown import ManualMarkdownStep  # pylint: disable=wrong-import-position
from wurzel.temporal_worker.activities import execute_wurzel_node  # pylint: disable=wrong-import-position
from wurzel.temporal_worker.workflows import WurzelPipelineWorkflow  # pylint: disable=wrong-import-position


@pytest.mark.asyncio
async def test_linear_markdown_pipeline_time_skipping():
    with tempfile.TemporaryDirectory() as tmp:
        md = Path(tmp) / "a.md"
        md.write_text("---\nkeywords: k\nurl: u\n---\n# Hello\n", encoding="utf-8")

        mm_key = f"{ManualMarkdownStep.__module__}.{ManualMarkdownStep.__name__}"
        dd_key = f"{DropDuplicationStep.__module__}.{DropDuplicationStep.__name__}"

        payload = {
            "dag_json": {
                "nodes": [
                    {
                        "id": "n1",
                        "step_key": mm_key,
                        "settings": {"FOLDER_PATH": str(tmp)},
                    },
                    {"id": "n2", "step_key": dd_key, "settings": {"DROP_BY_FIELDS": ["md"]}},
                ],
                "edges": [{"source": "n1", "target": "n2"}],
            },
            "pipeline_run_id": "test-run",
        }

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="wurzel-test-tq",
                workflows=[WurzelPipelineWorkflow],
                activities=[execute_wurzel_node],
                activity_executor=ThreadPoolExecutor(max_workers=4),
            ):
                result = await env.client.execute_workflow(
                    WurzelPipelineWorkflow.run,
                    payload,
                    id="test-wurzel-pipeline-1",
                    task_queue="wurzel-test-tq",
                )

        assert result["pipeline_run_id"] == "test-run"
        n2_out = result["node_results"]["n2"]
        assert isinstance(n2_out, list)
        assert len(n2_out) >= 1
