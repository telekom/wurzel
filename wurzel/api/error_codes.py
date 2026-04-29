# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Standardized error codes for the Wurzel API.

This module defines all error conditions that can occur in the API, with
standardized HTTP status codes and error messages.

Usage in route handlers::

    from wurzel.api.error_codes import ErrorCode

    if not found:
        raise ErrorCode.KNOWLEDGE_ITEM_NOT_FOUND.error(
            detail=f"Item {item_id} does not exist"
        )
"""

from __future__ import annotations

from enum import Enum

from fastapi import status as http_status

from wurzel.api.errors import APIError


class ErrorCode(str, Enum):
    """Standardized error codes for the Wurzel API.

    Maps business logic errors to RFC 7807 Problem Detail responses.
    """

    # ──────────────────────────────────────────────────────────────────
    # 400 Bad Request
    # ──────────────────────────────────────────────────────────────────

    INVALID_REQUEST = "INVALID_REQUEST"
    """The request body or parameters are invalid."""

    # ──────────────────────────────────────────────────────────────────
    # 401 Unauthorized
    # ──────────────────────────────────────────────────────────────────

    INVALID_API_KEY = "INVALID_API_KEY"  # pragma: allowlist secret
    """The X-API-Key header is missing or invalid."""

    INVALID_TOKEN = "INVALID_TOKEN"  # pragma: allowlist secret
    """The JWT token is missing, malformed, or expired."""  # pragma: allowlist secret

    TOKEN_VERIFICATION_FAILED = "TOKEN_VERIFICATION_FAILED"
    """The JWT token signature could not be verified."""  # pragma: allowlist secret

    # ──────────────────────────────────────────────────────────────────
    # 403 Forbidden
    # ──────────────────────────────────────────────────────────────────

    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    """The user does not have the required role or permissions."""

    # ──────────────────────────────────────────────────────────────────
    # 404 Not Found
    # ──────────────────────────────────────────────────────────────────

    KNOWLEDGE_ITEM_NOT_FOUND = "KNOWLEDGE_ITEM_NOT_FOUND"
    """The requested knowledge item does not exist."""

    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    """The requested project does not exist or the user is not a member."""

    PROJECT_MEMBER_NOT_FOUND = "PROJECT_MEMBER_NOT_FOUND"
    """The requested project member does not exist."""

    BRANCH_NOT_FOUND = "BRANCH_NOT_FOUND"
    """The requested branch does not exist."""

    INGEST_JOB_NOT_FOUND = "INGEST_JOB_NOT_FOUND"
    """The requested ingest job does not exist."""

    # ──────────────────────────────────────────────────────────────────
    # 409 Conflict
    # ──────────────────────────────────────────────────────────────────

    BRANCH_PROTECTED = "BRANCH_PROTECTED"
    """The branch is protected and cannot be deleted."""

    # ──────────────────────────────────────────────────────────────────
    # 501 Not Implemented
    # ──────────────────────────────────────────────────────────────────

    BACKEND_NOT_CONFIGURED = "BACKEND_NOT_CONFIGURED"
    """The storage backend is not configured or not available."""

    # ──────────────────────────────────────────────────────────────────
    # 503 Service Unavailable
    # ──────────────────────────────────────────────────────────────────

    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    """The service is temporarily unavailable (e.g., database down)."""

    JWKS_FETCH_FAILED = "JWKS_FETCH_FAILED"
    """Failed to fetch JWKS from the authentication provider."""

    def error(
        self,
        detail: str | None = None,
        extensions: dict | None = None,
    ) -> APIError:
        """Create an APIError with the standard title and status code for this error.

        Args:
            detail: Optional additional detail explaining the specific error instance.
            extensions: Optional RFC 7807 extensions (e.g., field names, resource IDs).

        Returns:
            An APIError ready to raise from a route handler.
        """
        status_code, title = self._status_and_title()
        return APIError(
            status_code=status_code,
            title=title,
            detail=detail,
            extensions=extensions,
        )

    def _status_and_title(self) -> tuple[int, str]:
        """Map error code to HTTP status and human-readable title."""
        mapping = {
            # 400
            ErrorCode.INVALID_REQUEST: (http_status.HTTP_400_BAD_REQUEST, "Invalid Request"),
            # 401
            ErrorCode.INVALID_API_KEY: (http_status.HTTP_401_UNAUTHORIZED, "Invalid API Key"),
            ErrorCode.INVALID_TOKEN: (http_status.HTTP_401_UNAUTHORIZED, "Invalid Token"),
            ErrorCode.TOKEN_VERIFICATION_FAILED: (
                http_status.HTTP_401_UNAUTHORIZED,
                "Token Verification Failed",
            ),
            # 403
            ErrorCode.INSUFFICIENT_PERMISSIONS: (http_status.HTTP_403_FORBIDDEN, "Insufficient Permissions"),
            # 404
            ErrorCode.KNOWLEDGE_ITEM_NOT_FOUND: (http_status.HTTP_404_NOT_FOUND, "Knowledge Item Not Found"),
            ErrorCode.PROJECT_NOT_FOUND: (http_status.HTTP_404_NOT_FOUND, "Project Not Found"),
            ErrorCode.PROJECT_MEMBER_NOT_FOUND: (http_status.HTTP_404_NOT_FOUND, "Project Member Not Found"),
            ErrorCode.BRANCH_NOT_FOUND: (http_status.HTTP_404_NOT_FOUND, "Branch Not Found"),
            ErrorCode.INGEST_JOB_NOT_FOUND: (http_status.HTTP_404_NOT_FOUND, "Ingest Job Not Found"),
            # 409
            ErrorCode.BRANCH_PROTECTED: (http_status.HTTP_409_CONFLICT, "Branch Is Protected"),
            # 501
            ErrorCode.BACKEND_NOT_CONFIGURED: (
                http_status.HTTP_501_NOT_IMPLEMENTED,
                "Backend Not Configured",
            ),
            # 503
            ErrorCode.SERVICE_UNAVAILABLE: (http_status.HTTP_503_SERVICE_UNAVAILABLE, "Service Unavailable"),
            ErrorCode.JWKS_FETCH_FAILED: (http_status.HTTP_503_SERVICE_UNAVAILABLE, "JWKS Fetch Failed"),
        }
        return mapping[self]
