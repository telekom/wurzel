# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Shared FastAPI dependencies: authentication and pagination."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Query
from fastapi import status as http_status
from pydantic import BaseModel

from wurzel.api.errors import APIError
from wurzel.api.settings import APISettings

_settings: APISettings | None = None  # pylint: disable=invalid-name


def _get_settings() -> APISettings:
    global _settings  # noqa: PLW0603  # pylint: disable=global-statement
    if _settings is None:
        _settings = APISettings()
    return _settings


async def verify_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    settings: APISettings = Depends(_get_settings),
) -> None:
    """FastAPI dependency — validates the ``X-API-Key`` request header."""
    if x_api_key is None or x_api_key != settings.API_KEY.get_secret_value():
        raise APIError(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail="A valid X-API-Key header is required.",
        )


# Convenience type alias for route signatures
RequireAPIKey = Annotated[None, Depends(verify_api_key)]

_MAX_PAGE_SIZE = 200


class PaginationParams(BaseModel):
    """Query-parameter pagination extracted as a dependency."""

    offset: int = 0
    limit: int = 50

    @classmethod
    def as_dependency(
        cls,
        offset: Annotated[int, Query(ge=0, description="Number of items to skip")] = 0,
        limit: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE, description="Maximum items to return")] = 50,
    ) -> PaginationParams:
        """FastAPI dependency factory — parse ``offset`` and ``limit`` query params."""
        return cls(offset=offset, limit=limit)


Pagination = Annotated[PaginationParams, Depends(PaginationParams.as_dependency)]
