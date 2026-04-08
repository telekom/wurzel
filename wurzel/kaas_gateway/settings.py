# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Gateway configuration (env / .env)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    SUPABASE_URL: str = Field(description="Supabase API URL, e.g. http://127.0.0.1:54321")
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str

    TEMPORAL_ADDRESS: str = "127.0.0.1:7233"
    TEMPORAL_NAMESPACE: str = "default"
    WURZEL_TEMPORAL_TASK_QUEUE: str = "wurzel-kaas"

    KAAS_GATEWAY_HOST: str = "127.0.0.1"
    KAAS_GATEWAY_PORT: int = 8010
    KAAS_GATEWAY_CORS_ORIGINS: str = "*"

    SWAGGER_ENABLED: bool = True
    KAAS_GATEWAY_INTERNAL_SECRET: str | None = None

    @field_validator("SUPABASE_URL")
    @classmethod
    def strip_slash_url(cls, v: str) -> str:
        return v.rstrip("/")

    def cors_origin_list(self) -> list[str]:
        raw = self.KAAS_GATEWAY_CORS_ORIGINS.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
