# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for the knowledge route."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from wurzel.core.settings import Settings


class KnowledgeSettings(Settings):
    """Configuration for the knowledge route.

    Reads from environment variables with the prefix ``KNOWLEDGE__``.
    """

    model_config = SettingsConfigDict(
        env_prefix="KNOWLEDGE__",
        extra="ignore",
        case_sensitive=True,
    )

    MAX_CONTENT_LENGTH: int = Field(
        1_000_000,
        gt=0,
        description="Maximum allowed content length in bytes",
    )
