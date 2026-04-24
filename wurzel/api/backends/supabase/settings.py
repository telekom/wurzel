# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for the Supabase storage backend."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from wurzel.core.settings import Settings


class SupabaseSettings(Settings):
    """Configuration for the Supabase backend.

    Reads from environment variables with the prefix ``SUPABASE__``.

    Example::

        SUPABASE__URL=https://xxx.supabase.co
        SUPABASE__SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    """

    model_config = SettingsConfigDict(
        env_prefix="SUPABASE__",
        extra="ignore",
        case_sensitive=True,
    )

    URL: str = Field(..., description="Supabase project URL, e.g. https://<project>.supabase.co")
    SERVICE_KEY: SecretStr = Field(..., description="Supabase service-role key (never expose to clients)")

    KNOWLEDGE_TABLE: str = Field("knowledge", description="Table name for knowledge items")
    INGEST_JOBS_TABLE: str = Field("ingest_jobs", description="Table name for ingest job records")
    MANIFESTS_TABLE: str = Field("manifests", description="Table name for pipeline manifest records")
