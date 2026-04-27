# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for the JWT/OIDC authentication layer."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from wurzel.core.settings import Settings


class AuthSettings(Settings):
    """Configuration for JWT authentication.

    Reads from environment variables with the prefix ``AUTH__``.

    Example (Supabase local dev)::

        AUTH__JWKS_URL=http://127.0.0.1:54321/auth/v1/.well-known/jwks.json
        AUTH__JWT_AUDIENCE=authenticated
    """

    model_config = SettingsConfigDict(
        env_prefix="AUTH__",
        extra="ignore",
        case_sensitive=True,
    )

    JWKS_URL: str = Field(
        ...,
        description="JWKS endpoint for the JWT issuer, e.g. {SUPABASE_URL}/auth/v1/.well-known/jwks.json",
    )
    JWT_AUDIENCE: str = Field(
        "authenticated",
        description="Expected 'aud' claim in JWT tokens (Supabase default: 'authenticated')",
    )
    ALGORITHM: str = Field(
        "HS256",
        description="JWT signing algorithm. Supabase local uses HS256; production typically RS256.",
    )
    ENABLED: bool = Field(
        True,
        description="Set to false to disable JWT auth (development only — always enable in production)",
    )
