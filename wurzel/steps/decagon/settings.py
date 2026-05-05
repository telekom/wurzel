# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for the Decagon Knowledge Base connector step."""

from pydantic import Field, SecretStr

from wurzel.step.settings import Settings


class DecagonSettings(Settings):
    """Configuration for the Decagon Knowledge Base connector.

    Attributes:
        API_URL: Base URL for the Decagon API.
        API_KEY: API key for authentication (required when PUSH_ENABLED is True).
        SOURCE: Source identifier for articles - all created articles will
            have this source value.
        TIMEOUT: Request timeout in seconds.
        PUSH_ENABLED: When False, skip pushing to Decagon and return the input data unchanged.

    Environment Variables (with DECAGONKBSTEP prefix):
        DECAGONKBSTEP__API_URL: Decagon API base URL
        DECAGONKBSTEP__API_KEY: API key for authentication
        DECAGONKBSTEP__SOURCE: Source identifier for articles
        DECAGONKBSTEP__TIMEOUT: Request timeout in seconds
        DECAGONKBSTEP__PUSH_ENABLED: Whether to push documents to Decagon (default: True)
    """

    API_URL: str = Field(
        default="https://eu.api.decagon.ai",
        description="Base URL for the Decagon API",
    )
    API_KEY: SecretStr | None = Field(
        default=None,
        description="API key for authentication with Decagon (required when PUSH_ENABLED is True)",
    )
    SOURCE: str = Field(
        default="Wurzel",
        description="Source identifier for articles",
    )
    TIMEOUT: int = Field(
        default=120,
        gt=0,
        description="Request timeout in seconds",
    )
    PUSH_ENABLED: bool = Field(
        default=True,
        description="When False, skip pushing to Decagon and return the input data unchanged",
    )
