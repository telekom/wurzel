# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from wurzel.kaas_gateway.deps import verify_internal_secret
from wurzel.kaas_gateway.models import SearchRequest

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.post("/search", dependencies=[Depends(verify_internal_secret)])
def search_placeholder(_body: SearchRequest) -> None:
    """Reserved for future vector / catalog search (see search_service layout)."""
    raise HTTPException(
        status_code=501,
        detail="Search is not implemented yet. Use this route as the future search endpoint.",
    )
