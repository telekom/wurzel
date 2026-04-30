# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""RFC 7807 error models and FastAPI exception handlers."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details for HTTP APIs."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    extensions: dict[str, Any] | None = None

    model_config = {"extra": "ignore"}


def _problem_response(
    status_code: int,
    title: str,
    detail: str | None = None,
    instance: str | None = None,
    extensions: dict[str, Any] | None = None,
) -> JSONResponse:
    body = ProblemDetail(
        title=title,
        status=status_code,
        detail=detail,
        instance=instance,
        extensions=extensions,
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )


class APIError(Exception):
    """Raise this inside route handlers to produce an RFC 7807 response."""

    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.extensions = extensions
        super().__init__(detail or title)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to *app*."""

    @app.exception_handler(APIError)
    async def _api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        return _problem_response(
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            instance=str(request.url),
            extensions=exc.extensions,
        )

    @app.exception_handler(status.HTTP_404_NOT_FOUND)
    async def _not_found_handler(request: Request, _exc: Exception) -> JSONResponse:
        return _problem_response(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Not Found",
            instance=str(request.url),
        )

    @app.exception_handler(status.HTTP_422_UNPROCESSABLE_CONTENT)
    async def _validation_handler(request: Request, exc: Exception) -> JSONResponse:
        return _problem_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            title="Unprocessable Entity",
            detail=str(exc),
            instance=str(request.url),
        )

    @app.exception_handler(Exception)
    async def _generic_handler(request: Request, exc: Exception) -> JSONResponse:
        return _problem_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail=str(exc),
            instance=str(request.url),
        )
