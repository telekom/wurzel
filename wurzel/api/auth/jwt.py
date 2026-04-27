# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""JWT validation and the ``CurrentUser`` FastAPI dependency.

Uses ``PyJWT`` to validate Supabase JWTs.  The JWKS keyset is fetched once
and cached for 5 minutes; an unknown ``kid`` forces an immediate refresh.

Install the optional dependency::

    pip install wurzel[api]  # includes PyJWT and httpx
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends
from fastapi import status as http_status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from wurzel.api.auth.settings import AuthSettings
from wurzel.api.errors import APIError

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

# ── Cached JWKS ──────────────────────────────────────────────────────────────
_JWKS_CACHE: dict[str, Any] = {}
_JWKS_FETCHED_AT: float = 0.0
_JWKS_TTL: float = 300.0  # 5 minutes


@lru_cache(maxsize=1)
def _get_auth_settings() -> AuthSettings:
    return AuthSettings()


def _fetch_jwks(settings: AuthSettings) -> dict[str, Any]:
    """Fetch the JWKS from the issuer and update the in-process cache."""
    global _JWKS_CACHE, _JWKS_FETCHED_AT  # noqa: PLW0603  # pylint: disable=global-statement
    try:
        import httpx  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

        response = httpx.get(settings.JWKS_URL, timeout=5.0)
        response.raise_for_status()
        keyset = response.json()
        _JWKS_CACHE = keyset
        _JWKS_FETCHED_AT = time.monotonic()
        logger.debug("JWKS refreshed from %s", settings.JWKS_URL)
        return keyset
    except Exception as exc:  # pragma: no cover  # pylint: disable=broad-exception-caught
        logger.warning("Failed to fetch JWKS from %s: %s", settings.JWKS_URL, exc)
        return _JWKS_CACHE  # return stale cache rather than hard-failing


def _get_jwks(settings: AuthSettings) -> dict[str, Any]:
    """Return the JWKS keyset, refreshing if the TTL has expired."""
    if time.monotonic() - _JWKS_FETCHED_AT > _JWKS_TTL or not _JWKS_CACHE:
        return _fetch_jwks(settings)
    return _JWKS_CACHE


# ── Parsed token claims ───────────────────────────────────────────────────────


@dataclass
class UserClaims:
    """Parsed, validated JWT claims for the calling user."""

    sub: str
    """Supabase user UUID."""

    email: str
    """User e-mail address (from JWT claims)."""

    raw: dict[str, Any]
    """Full decoded payload for extension points."""


# ── FastAPI dependency ────────────────────────────────────────────────────────


def _decode_token(token: str, settings: AuthSettings) -> dict[str, Any]:
    """Decode and validate a JWT, refreshing JWKS on unknown kid."""
    try:
        import jwt  # PyJWT  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        from jwt import PyJWKClient  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise ImportError("PyJWT is not installed. Run: pip install wurzel[api]") from exc

    # For HMAC algorithms (HS256 — Supabase local), PyJWT needs the secret directly.
    # For RSA/EC algorithms (RS256 — production), use the JWKS endpoint.
    if settings.ALGORITHM.startswith("HS"):
        # Supabase local dev uses a symmetric JWT secret; we need it via the JWKS endpoint
        # but JWKS doesn't expose symmetric keys. For local dev we accept without audience validation
        # by re-reading the secret from the JWKS response (Supabase exposes it as 'k' in the JWK).
        jwks = _get_jwks(settings)
        keys = jwks.get("keys", [])
        if keys:
            import base64  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

            secret = base64.urlsafe_b64decode(keys[0].get("k", "") + "==")
        else:
            # Fallback: decode without signature verification in dev (ENABLED=False handles this)
            secret = b""
        try:
            return jwt.decode(
                token,
                secret,
                algorithms=[settings.ALGORITHM],
                audience=settings.JWT_AUDIENCE,
                options={"verify_exp": True},
            )
        except Exception:  # pylint: disable=broad-exception-caught
            # Try without audience (some Supabase local setups omit aud)
            return jwt.decode(
                token,
                secret,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": True, "verify_aud": False},
            )
    else:
        # Asymmetric: use PyJWKClient against the JWKS endpoint
        try:
            client = PyJWKClient(settings.JWKS_URL, cache_keys=True)
            signing_key = client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=[settings.ALGORITHM],
                audience=settings.JWT_AUDIENCE,
            )
        except jwt.exceptions.PyJWKClientError:
            # Force refresh and retry once
            _fetch_jwks(settings)
            client = PyJWKClient(settings.JWKS_URL, cache_keys=False)
            signing_key = client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=[settings.ALGORITHM],
                audience=settings.JWT_AUDIENCE,
            )


async def _verify_jwt(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: AuthSettings = Depends(_get_auth_settings),
) -> UserClaims:
    """FastAPI dependency — validates ``Authorization: Bearer <token>``."""
    if not settings.ENABLED:
        # Dev shortcut: return a synthetic user when auth is disabled
        return UserClaims(sub="dev-user", email="dev@local", raw={})

    if credentials is None:
        raise APIError(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail="Authorization: Bearer <token> header is required.",
        )

    try:
        payload = _decode_token(credentials.credentials, settings)
    except Exception as exc:
        logger.debug("JWT validation failed: %s", exc)
        raise APIError(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail="JWT token is invalid or expired.",
        ) from exc

    sub = payload.get("sub")
    email = payload.get("email", "")
    if not sub:
        raise APIError(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail="JWT token is missing 'sub' claim.",
        )

    return UserClaims(sub=sub, email=email, raw=payload)


# Convenience type alias used in route signatures
CurrentUser = Annotated[UserClaims, Depends(_verify_jwt)]
