# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for the ingest route."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from wurzel.core.settings import Settings


class IngestSettings(Settings):
    """Configuration for the ingest route.

    Reads from environment variables with the prefix ``INGEST__``.
    """

    model_config = SettingsConfigDict(
        env_prefix="INGEST__",
        extra="ignore",
        case_sensitive=True,
    )

    MAX_BATCH_SIZE: int = Field(
        1000,
        gt=0,
        description="Maximum number of items per ingest request",
    )
    CONCURRENCY: int = Field(
        4,
        gt=0,
        description="Number of concurrent ingest workers per job",
    )
