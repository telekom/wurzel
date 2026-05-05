# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for the Wonderful RAG connector step."""

from pydantic import Field, SecretStr, model_validator

from wurzel.step.settings import Settings


class WonderfulRAGSettings(Settings):
    """Configuration for the Wonderful RAG connector.

    Set ``WONDERFULRAGSTEP__ENABLED=false`` to make the step a no-op
    (passthrough only, no API calls, no credentials required). Useful for
    pipeline environments where the Wonderful sink is intentionally disabled
    (e.g. DT's dev environment).

    Environment Variables (with WONDERFULRAGSTEP prefix):
        WONDERFULRAGSTEP__ENABLED:          Whether the step performs uploads (default: true)
        WONDERFULRAGSTEP__BASE_URL:         Wonderful API base URL (required when ENABLED)
        WONDERFULRAGSTEP__API_KEY:          API key for authentication (required when ENABLED)
        WONDERFULRAGSTEP__KNOWLEDGEBASE_ID: Knowledge base ID (required when ENABLED)
        WONDERFULRAGSTEP__TIMEOUT:          Request timeout in seconds
        WONDERFULRAGSTEP__MAX_WORKERS:      Concurrent upload workers
    """

    ENABLED: bool = Field(
        default=True,
        description="When false, the step skips all API calls and passes input through unchanged.",
    )
    BASE_URL: str = Field(
        default="",
        description="Wonderful API base URL (required when ENABLED)",
    )
    API_KEY: SecretStr = Field(
        default=SecretStr(""),
        description="API key for authentication with Wonderful (required when ENABLED)",
    )
    KNOWLEDGEBASE_ID: str = Field(
        default="",
        description="Knowledge base ID to push documents to (required when ENABLED)",
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

    @model_validator(mode="after")
    def _require_credentials_when_enabled(self) -> "WonderfulRAGSettings":
        if not self.ENABLED:
            return self
        missing = [
            name
            for name, value in (
                ("BASE_URL", self.BASE_URL),
                ("API_KEY", self.API_KEY.get_secret_value()),
                ("KNOWLEDGEBASE_ID", self.KNOWLEDGEBASE_ID),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "WonderfulRAGStep is enabled but missing required settings: "
                + ", ".join(f"WONDERFULRAGSTEP__{name}" for name in missing)
            )
        return self
