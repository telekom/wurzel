# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Top-level settings for the Wurzel API."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from wurzel.core.settings import Settings


class APISettings(Settings):
    """Runtime configuration for the Wurzel API server.

    All fields are read from environment variables with the prefix ``API__``.

    Example::

        API__PORT=9000 API__DEBUG=true uvicorn wurzel.api.app:create_app --factory
    """

    model_config = SettingsConfigDict(
        env_prefix="API__",
        extra="ignore",
        case_sensitive=True,
    )

    HOST: str = Field("0.0.0.0", description="Bind address for uvicorn")  # noqa: S104
    PORT: int = Field(8000, gt=0, lt=65536, description="Bind port")
    WORKERS: int = Field(1, gt=0, description="Number of uvicorn worker processes")
    DEBUG: bool = Field(False, description="Enable debug / reload mode")

    API_KEY: SecretStr = Field(..., description="Bearer API key — set via API__API_KEY env var")
    CORS_ORIGINS: list[str] = Field(["*"], description="Allowed CORS origins")

    API_TITLE: str = Field("Wurzel — Knowledge as a Service", description="OpenAPI title")
    API_VERSION: str = Field("v1", description="API version prefix, e.g. 'v1'")
