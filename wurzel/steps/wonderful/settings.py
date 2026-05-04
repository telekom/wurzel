# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for the Wonderful RAG connector step."""

from pydantic import Field, SecretStr

from wurzel.step.settings import Settings


class WonderfulRAGSettings(Settings):
    """Configuration for the Wonderful RAG connector.

    Environment Variables (with WONDERFULRAGSTEP prefix):
        WONDERFULRAGSTEP__BASE_URL:         Wonderful API base URL
        WONDERFULRAGSTEP__API_KEY:          API key for authentication (required)
        WONDERFULRAGSTEP__KNOWLEDGEBASE_ID: Knowledge base ID (required)
        WONDERFULRAGSTEP__TIMEOUT:          Request timeout in seconds
    """

    BASE_URL: str = Field(
        description="Wonderful API base URL",
    )
    API_KEY: SecretStr = Field(
        description="API key for authentication with Wonderful",
    )
    KNOWLEDGEBASE_ID: str = Field(
        description="Knowledge base ID to push documents to",
    )
    TIMEOUT: int = Field(
        default=120,
        gt=0,
        description="Request timeout in seconds",
    )
    MAX_WORKERS: int = Field(
        default=10,
        gt=0,
        description="Max concurrent upload workers",
    )
