# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Search route.

Routes
------
``POST /v1/search`` — semantic / full-text search over knowledge items
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import status as http_status

from wurzel.api.dependencies import RequireAPIKey
from wurzel.api.errors import APIError
from wurzel.api.routes.search.data import SearchRequest, SearchResponse

router = APIRouter()


@router.post("", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    _auth: RequireAPIKey,
) -> SearchResponse:
    """Perform a semantic or full-text search over knowledge items."""
    raise APIError(
        status_code=http_status.HTTP_501_NOT_IMPLEMENTED,
        title="Not Implemented",
        detail="Search backend not yet wired up.",
    )
