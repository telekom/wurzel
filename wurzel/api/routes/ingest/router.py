# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Ingest routes.

Routes
------
``POST /v1/ingest``              — submit a bulk-ingest job (async)
``GET  /v1/ingest/{job_id}``     — poll ingest job status
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks
from fastapi import status as http_status

from wurzel.api.dependencies import RequireAPIKey
from wurzel.api.errors import APIError
from wurzel.api.routes.ingest.data import IngestJobResponse, IngestRequest, IngestResponse

router = APIRouter()


def _get_backend():  # type: ignore[return]
    raise APIError(
        status_code=http_status.HTTP_501_NOT_IMPLEMENTED,
        title="Not Implemented",
        detail="No storage backend is configured. Wire up wurzel.api.backends.supabase.",
    )


@router.post("", response_model=IngestResponse, status_code=http_status.HTTP_202_ACCEPTED)
async def submit_ingest(
    body: IngestRequest,
    background_tasks: BackgroundTasks,
    _auth: RequireAPIKey,
) -> IngestResponse:
    """Accept a bulk-ingest job and process it asynchronously.

    Returns immediately with a ``job_id`` that can be polled via
    ``GET /v1/ingest/{job_id}``.
    """
    job = IngestResponse(item_count=len(body.items))

    async def _run() -> None:
        # TODO: replace with real backend call, e.g.:
        # backend = get_backend()
        # await backend.create_job(job.job_id, body)
        pass

    background_tasks.add_task(_run)
    return job


@router.get("/{job_id}", response_model=IngestJobResponse)
async def get_ingest_job(
    job_id: uuid.UUID,
    _auth: RequireAPIKey,
) -> IngestJobResponse:
    """Return the current status of a previously submitted ingest job."""
    raise APIError(
        status_code=http_status.HTTP_501_NOT_IMPLEMENTED,
        title="Not Implemented",
        detail="Backend persistence not yet wired up.",
    )
