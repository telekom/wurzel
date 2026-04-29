# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""JWT validation and the ``CurrentUser`` FastAPI dependency.

Uses ``PyJWT`` to validate Supabase JWTs.  The JWKS keyset is fetched and
cached with a TTL; an unknown ``kid`` triggers an immediate refresh.

Install the optional dependency::

    pip install wurzel[api]  # includes PyJWT and httpx

Note:
    Global state (JWKS cache) is managed by JWKSCache class, which is
    instantiated once per FastAPI app lifetime via dependency injection.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from wurzel.api.auth.domain import UserClaims
from wurzel.api.auth.settings import AuthSettings
from wurzel.api.error_codes import ErrorCode

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

# ── JWKS Cache (stateful, injected via DI) ───────────────────────────────────
_JWKS_TTL: float = 300.0  # 5 minutes


class JWKSCache:
    """In-process TTL cache for JWKS keyset.

    Injected into JWT verification via FastAPI dependency injection.
    Can be overridden in tests via ``app.dependency_overrides``.

    Example (testing)::

        class MockJWKSCache:
            async def get_keys(self, settings: AuthSettings) -> dict[str, Any]:
                return {"keys": [{"k": "..."}]}

        app.dependency_overrides[get_jwks_cache] = lambda: MockJWKSCache()
    """

    def __init__(self, ttl: float = _JWKS_TTL) -> None:
        self._ttl = ttl
        self._cache: dict[str, Any] = {}
        self._fetched_at: float = 0.0

    async def get_keys(self, settings: AuthSettings) -> dict[str, Any]:
        """Return cached JWKS, fetching if TTL expired."""
        if time.monotonic() - self._fetched_at > self._ttl or not self._cache:
            await self._fetch(settings)
        return self._cache

    async def _fetch(self, settings: AuthSettings) -> None:
        """Fetch JWKS from issuer and update cache."""
        try:
            import httpx  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

            response = httpx.get(settings.JWKS_URL, timeout=5.0)
            response.raise_for_status()
            self._cache = response.json()
            self._fetched_at = time.monotonic()
            logger.debug("JWKS refreshed from %s", settings.JWKS_URL)
        except Exception as exc:  # pragma: no cover  # pylint: disable=broad-exception-caught
            logger.warning("Failed to fetch JWKS from %s: %s", settings.JWKS_URL, exc)
            # Return stale cache if fetch fails


def get_jwks_cache() -> JWKSCache:
    """FastAPI dependency — returns the per-app JWKS cache instance."""
    return JWKSCache()


def _get_auth_settings() -> AuthSettings:
    """FastAPI dependency — returns AuthSettings from environment.

    Can be overridden in tests via ``app.dependency_overrides[_get_auth_settings]``.
    """
    return AuthSettings()


def _decode_token(token: str, settings: AuthSettings, jwks: dict[str, Any]) -> dict[str, Any]:
    """Decode and validate a JWT.

    Args:
        token: The JWT token string.
        settings: Auth settings (JWKS URL, algorithm, etc.).
        jwks: Cached JWKS keyset.

    Returns:
        The decoded JWT payload.

    Raises:
        APIError: If token is invalid, expired, or signature verification fails.
    """
    try:
        import jwt  # PyJWT  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        from jwt import PyJWKClient  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise ImportError("PyJWT is not installed. Run: pip install wurzel[api]") from exc

    # For HMAC algorithms (HS256 — Supabase local), PyJWT needs the secret directly.
    # For RSA/EC algorithms (RS256 — production), use the JWKS endpoint.
    if settings.ALGORITHM.startswith("HS"):
        # Supabase local dev: extract symmetric key from JWKS (exposed as 'k')
        keys = jwks.get("keys", [])
        if keys:
            import base64  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

            secret = base64.urlsafe_b64decode(keys[0].get("k", "") + "==")
        else:
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
            # Fallback: some Supabase local setups omit 'aud' claim
            return jwt.decode(
                token,
                secret,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": True, "verify_aud": False},
            )

    # Asymmetric (RS256, etc.): use PyJWKClient against JWKS endpoint
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
        # Force refresh and retry once on unknown kid
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
    jwks_cache: JWKSCache = Depends(get_jwks_cache),
) -> UserClaims:
    """FastAPI dependency — validates ``Authorization: Bearer <token>``.

    Args:
        credentials: The Authorization header (if present).
        settings: Auth configuration from environment.
        jwks_cache: Cached JWKS keyset.

    Returns:
        The authenticated user's claims.

    Raises:
        APIError: If auth is disabled, token is missing, or token is invalid.
    """
    if not settings.ENABLED:
        # Dev shortcut: return synthetic user when auth is disabled
        return UserClaims(sub="dev-user", email="dev@local")

    if credentials is None:
        raise ErrorCode.INVALID_TOKEN.error(detail="Authorization: Bearer <token> header is required.")

    try:
        jwks = await jwks_cache.get_keys(settings)
        payload = _decode_token(credentials.credentials, settings, jwks)
    except Exception as exc:
        logger.debug("JWT validation failed: %s", exc)
        raise ErrorCode.TOKEN_VERIFICATION_FAILED.error(detail="JWT token is invalid or expired.") from exc

    sub = payload.get("sub")
    email = payload.get("email", "")
    if not sub:
        raise ErrorCode.INVALID_TOKEN.error(detail="JWT token is missing 'sub' claim.")

    return UserClaims(sub=sub, email=email)


# Convenience type alias used in route signatures
CurrentUser = Annotated[UserClaims, Depends(_verify_jwt)]
