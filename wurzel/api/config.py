# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Unified configuration for the Wurzel API.

Consolidates APISettings, AuthSettings, and SupabaseSettings into a single
configuration object that is instantiated once and injected via FastAPI DI.

Environment variables are organized by service prefix:
- API__*      → API server (port, workers, etc.)
- AUTH__*     → JWT/OIDC configuration
- SUPABASE__* → Supabase backend configuration
"""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from wurzel.core.settings import Settings


class WurzelConfig(Settings):
    r"""Complete configuration for the Wurzel API.

    All fields are read from environment variables with prefixes ``API__``,
    ``AUTH__``, and ``SUPABASE__``.

    Example::

        API__PORT=9000 \
        AUTH__JWKS_URL=http://127.0.0.1:54321/auth/v1/.well-known/jwks.json \
        SUPABASE__URL=http://localhost:54321 \
        SUPABASE__SERVICE_KEY=... \
        uvicorn wurzel.api.app:create_app --factory

    Raises:
        ValueError: If required fields (API_KEY, AUTH__JWKS_URL, SUPABASE__*) are missing.
    """

    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=True,
    )

    # ──────────────────────────────────────────────────────────────────
    # API Server Configuration (API__ prefix)
    # ──────────────────────────────────────────────────────────────────

    API_HOST: str = Field("0.0.0.0", description="Bind address for uvicorn")  # noqa: S104
    API_PORT: int = Field(8000, gt=0, lt=65536, description="Bind port")
    API_WORKERS: int = Field(1, gt=0, description="Number of uvicorn worker processes")
    API_DEBUG: bool = Field(False, description="Enable debug / reload mode")
    API_KEY: SecretStr = Field(..., description="Bearer API key for X-API-Key authentication")
    API_CORS_ORIGINS: list[str] = Field(["*"], description="Allowed CORS origins")
    API_TITLE: str = Field("Wurzel — Knowledge as a Service", description="OpenAPI title")
    API_VERSION: str = Field("v1", description="API version prefix, e.g. 'v1'")

    # ──────────────────────────────────────────────────────────────────
    # JWT/OIDC Authentication (AUTH__ prefix)
    # ──────────────────────────────────────────────────────────────────

    AUTH_JWKS_URL: str = Field(
        ...,
        description="JWKS endpoint for the JWT issuer, e.g. {SUPABASE_URL}/auth/v1/.well-known/jwks.json",
    )
    AUTH_JWT_AUDIENCE: str = Field(
        "authenticated",
        description="Expected 'aud' claim in JWT tokens (Supabase default: 'authenticated')",
    )
    AUTH_ALGORITHM: str = Field(
        "HS256",
        description="JWT signing algorithm. Supabase local uses HS256; production typically RS256.",
    )
    AUTH_ENABLED: bool = Field(
        True,
        description="Set to false to disable JWT auth (development only — always enable in production)",
    )

    # ──────────────────────────────────────────────────────────────────
    # Supabase Storage Backend (SUPABASE__ prefix)
    # ──────────────────────────────────────────────────────────────────

    SUPABASE_URL: str = Field(..., description="Supabase project URL, e.g. https://<project>.supabase.co")
    SUPABASE_SERVICE_KEY: SecretStr = Field(..., description="Supabase service-role key (never expose to clients)")
    SUPABASE_KNOWLEDGE_TABLE: str = Field("knowledge", description="Table name for knowledge items")
    SUPABASE_INGEST_JOBS_TABLE: str = Field("ingest_jobs", description="Table name for ingest job records")
    SUPABASE_MANIFESTS_TABLE: str = Field("manifests", description="Table name for pipeline manifest records")

    def get_api_settings(self) -> APISettings:
        """Extract API-specific settings as a SettingsConfigDict-compatible object."""
        return APISettings(
            host=self.API_HOST,
            port=self.API_PORT,
            workers=self.API_WORKERS,
            debug=self.API_DEBUG,
            api_key=self.API_KEY,
            cors_origins=self.API_CORS_ORIGINS,
            title=self.API_TITLE,
            version=self.API_VERSION,
        )

    def get_auth_settings(self) -> AuthSettings:
        """Extract auth-specific settings as a SettingsConfigDict-compatible object."""
        return AuthSettings(
            jwks_url=self.AUTH_JWKS_URL,
            jwt_audience=self.AUTH_JWT_AUDIENCE,
            algorithm=self.AUTH_ALGORITHM,
            enabled=self.AUTH_ENABLED,
        )

    def get_supabase_settings(self) -> SupabaseSettings:
        """Extract Supabase-specific settings as a SettingsConfigDict-compatible object."""
        return SupabaseSettings(
            url=self.SUPABASE_URL,
            service_key=self.SUPABASE_SERVICE_KEY,
            knowledge_table=self.SUPABASE_KNOWLEDGE_TABLE,
            ingest_jobs_table=self.SUPABASE_INGEST_JOBS_TABLE,
            manifests_table=self.SUPABASE_MANIFESTS_TABLE,
        )


# ─────────────────────────────────────────────────────────────────────────
# Legacy Settings Classes (for backward compatibility with existing code)
# These are now derived from WurzelConfig.
# ─────────────────────────────────────────────────────────────────────────


class APISettings(Settings):
    """API server configuration (subset of WurzelConfig).

    Kept for backward compatibility. New code should use WurzelConfig directly.
    """

    model_config = SettingsConfigDict(
        env_prefix="API__",
        extra="ignore",
        case_sensitive=True,
    )

    host: str = Field("0.0.0.0", description="Bind address for uvicorn")  # noqa: S104
    port: int = Field(8000, gt=0, lt=65536, description="Bind port")
    workers: int = Field(1, gt=0, description="Number of uvicorn worker processes")
    debug: bool = Field(False, description="Enable debug / reload mode")
    api_key: SecretStr = Field(..., description="Bearer API key")
    cors_origins: list[str] = Field(["*"], description="Allowed CORS origins")
    title: str = Field("Wurzel — Knowledge as a Service", description="OpenAPI title")
    version: str = Field("v1", description="API version prefix")


class AuthSettings(Settings):
    """JWT authentication configuration (subset of WurzelConfig).

    Kept for backward compatibility. New code should use WurzelConfig directly.
    """

    model_config = SettingsConfigDict(
        env_prefix="AUTH__",
        extra="ignore",
        case_sensitive=True,
    )

    jwks_url: str = Field(..., description="JWKS endpoint for the JWT issuer")
    jwt_audience: str = Field("authenticated", description="Expected 'aud' claim in JWT tokens")
    algorithm: str = Field("HS256", description="JWT signing algorithm")
    enabled: bool = Field(True, description="Enable JWT auth")


class SupabaseSettings(Settings):
    """Supabase backend configuration (subset of WurzelConfig).

    Kept for backward compatibility. New code should use WurzelConfig directly.
    """

    model_config = SettingsConfigDict(
        env_prefix="SUPABASE__",
        extra="ignore",
        case_sensitive=True,
    )

    url: str = Field(..., description="Supabase project URL")
    service_key: SecretStr = Field(..., description="Supabase service-role key")
    knowledge_table: str = Field("knowledge", description="Table name for knowledge items")
    ingest_jobs_table: str = Field("ingest_jobs", description="Table name for ingest job records")
    manifests_table: str = Field("manifests", description="Table name for pipeline manifest records")
