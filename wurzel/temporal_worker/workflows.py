# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow  # pylint: disable=import-error


@workflow.defn(name="WurzelPipelineWorkflow")
class WurzelPipelineWorkflow:
    """Execute a DAG of Wurzel steps (MVP: single predecessor per node)."""

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        with workflow.unsafe.imports_passed_through():
            from wurzel.temporal_worker.dag_util import topological_node_ids

        dag = payload.get("dag_json") or {}
        nodes: list[dict[str, Any]] = dag.get("nodes") or []
        edges: list[dict[str, str]] = dag.get("edges") or []
        order = topological_node_ids(nodes, edges)
        node_map = {n["id"]: n for n in nodes}
        results: dict[str, Any] = {}

        for nid in order:
            node = node_map[nid]
            preds = [e["source"] for e in edges if e["target"] == nid]
            if not preds:
                in_payload = None
            elif len(preds) == 1:
                in_payload = results[preds[0]]
            else:
                raise workflow.ApplicationError("MVP supports at most one incoming edge per node")

            activity_req = {
                "step_key": node["step_key"],
                "settings": node.get("settings") or {},
                "input_payload": in_payload,
            }
            results[nid] = await workflow.execute_activity(
                "execute_wurzel_node",
                activity_req,
                start_to_close_timeout=timedelta(hours=2),
            )

        return {"node_results": results, "pipeline_run_id": payload.get("pipeline_run_id")}
