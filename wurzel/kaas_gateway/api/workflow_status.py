# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError
from temporalio.service import RPCError

from wurzel.kaas_gateway.deps import (
    create_user_supabase,
    get_settings_dep,
    verify_internal_secret,
)
from wurzel.kaas_gateway.models import WorkflowStatusResponse
from wurzel.kaas_gateway.settings import Settings

router = APIRouter(prefix="/api/v1", tags=["workflow"])


@router.get(
    "/workflow-status",
    response_model=WorkflowStatusResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def workflow_status(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    workflow_id: Annotated[str, Query(min_length=1)],
    authorization: Annotated[str | None, Header()] = None,
) -> WorkflowStatusResponse | JSONResponse:
    """Return Temporal execution status for a workflow the caller may access via RLS."""
    if not authorization:
        return JSONResponse(status_code=401, content={"error": "Missing Authorization"})

    temporal = getattr(request.app.state, "temporal_client", None)
    if temporal is None:
        return JSONResponse(status_code=503, content={"error": "Temporal client not initialized"})

    user_sb = create_user_supabase(settings, authorization)
    try:
        row_resp = user_sb.from_("pipeline_runs").select("id,status").eq("temporal_workflow_id", workflow_id).single().execute()
    except APIError as e:
        if getattr(e, "code", None) == "PGRST116":
            return JSONResponse(status_code=404, content={"error": "pipeline run not found"})
        return JSONResponse(
            status_code=404,
            content={"error": e.message or "pipeline run not found"},
        )

    row = row_resp.data
    if not row or not isinstance(row, dict):
        return JSONResponse(status_code=404, content={"error": "pipeline run not found"})

    run_id = str(row["id"])
    db_status = str(row.get("status") or "")

    handle = temporal.get_workflow_handle(workflow_id)
    try:
        desc = await handle.describe()
    except RPCError as e:
        return JSONResponse(
            status_code=502,
            content={"error": "Temporal describe failed", "detail": str(e)},
        )

    st = desc.status
    temporal_name = st.name if st is not None else "UNKNOWN"

    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        pipeline_run_id=run_id,
        temporal_status=temporal_name,
        db_status=db_status,
    )
