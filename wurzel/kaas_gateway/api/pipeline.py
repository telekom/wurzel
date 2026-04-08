# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError

from wurzel.kaas_gateway.deps import (
    create_service_supabase,
    create_user_supabase,
    get_settings_dep,
    verify_internal_secret,
)
from wurzel.kaas_gateway.models import StartPipelineRequest, StartPipelineResponse
from wurzel.kaas_gateway.settings import Settings

router = APIRouter(prefix="/api/v1", tags=["pipeline"])


@router.post(
    "/pipeline-runs/start",
    response_model=StartPipelineResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def start_pipeline_run(
    request: Request,
    body: StartPipelineRequest,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    authorization: Annotated[str | None, Header()] = None,
) -> StartPipelineResponse | JSONResponse:
    if not authorization:
        return JSONResponse(status_code=401, content={"error": "Missing Authorization"})
    temporal = getattr(request.app.state, "temporal_client", None)
    if temporal is None:
        return JSONResponse(status_code=503, content={"error": "Temporal client not initialized"})

    user_sb = create_user_supabase(settings, authorization)

    try:
        rev_resp = user_sb.from_("config_revisions").select("id,dag_json").eq("id", body.config_revision_id).single().execute()
    except APIError as e:
        if getattr(e, "code", None) == "PGRST116":
            return JSONResponse(
                status_code=404,
                content={"error": e.message or "revision not found"},
            )
        return JSONResponse(
            status_code=404,
            content={"error": e.message or "revision not found"},
        )

    rev = rev_resp.data
    if not rev or not isinstance(rev, dict):
        return JSONResponse(status_code=404, content={"error": "revision not found"})

    try:
        run_resp = user_sb.rpc(
            "register_pipeline_run",
            {"p_config_revision_id": body.config_revision_id},
        ).execute()
    except APIError as e:
        return JSONResponse(
            status_code=400,
            content={"error": e.message or "could not register run"},
        )

    run_id = run_resp.data
    if run_id is None:
        return JSONResponse(status_code=400, content={"error": "could not register run"})

    run_id_str = str(run_id)

    try:
        handle = await temporal.start_workflow(
            "WurzelPipelineWorkflow",
            {"dag_json": rev.get("dag_json"), "pipeline_run_id": run_id_str},
            id=f"wurzel-pipeline-{run_id_str}",
            task_queue=settings.WURZEL_TEMPORAL_TASK_QUEUE,
        )
        workflow_id = handle.id
    except Exception as e:  # pylint: disable=broad-exception-caught
        return JSONResponse(
            status_code=502,
            content={"error": "Temporal start failed", "detail": str(e)},
        )

    svc = create_service_supabase(settings)
    try:
        svc.rpc(
            "update_pipeline_run_temporal",
            {
                "p_run_id": run_id_str,
                "p_temporal_workflow_id": workflow_id,
                "p_temporal_run_id": None,
                "p_status": "running",
            },
        ).execute()
    except APIError as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Run started but DB update failed", "detail": e.message},
        )

    return StartPipelineResponse(pipeline_run_id=run_id_str, temporal_workflow_id=workflow_id)
