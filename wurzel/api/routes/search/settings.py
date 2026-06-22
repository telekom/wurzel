# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for the search route."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from wurzel.core.settings import Settings


class SearchSettings(Settings):
    """Configuration for the search route.

    Reads from environment variables with the prefix ``SEARCH__``.
    """

    model_config = SettingsConfigDict(
        env_prefix="SEARCH__",
        extra="ignore",
        case_sensitive=True,
    )

    DEFAULT_LIMIT: int = Field(10, gt=0, le=100, description="Default number of results")
    SCORE_THRESHOLD: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score; results below are filtered out",
    )
