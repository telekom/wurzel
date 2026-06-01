# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for the Wonderful RAG connector step."""

from pydantic import Field, SecretStr, model_validator

from wurzel.step.settings import Settings


class WonderfulRAGSettings(Settings):
    """Configuration for the Wonderful RAG connector.

    Set ``WONDERFULRAGSTEP__SKIP=true`` to make the step a no-op (passthrough
    only, no API calls, no credentials required). Used to avoid concurrency
    in lower DT environments where dev and staging share a cron schedule
    (both run at 6:30 CET on Mondays and Wednesdays) and would otherwise hit
    Wonderful staging twice in the same minute.

    Environment Variables (with WONDERFULRAGSTEP prefix):
        WONDERFULRAGSTEP__SKIP:             When true, skip processing (default: false)
        WONDERFULRAGSTEP__BASE_URL:         Wonderful API base URL (required when not SKIP)
        WONDERFULRAGSTEP__API_KEY:          API key for authentication (required when not SKIP)
        WONDERFULRAGSTEP__KNOWLEDGEBASE_ID: Knowledge base ID (required when not SKIP)
        WONDERFULRAGSTEP__TIMEOUT:          Request timeout in seconds
        WONDERFULRAGSTEP__MAX_WORKERS:      Concurrent upload workers
    """

    SKIP: bool = Field(
        default=False,
        description="When true, the step skips all API calls and passes input through unchanged.",
    )
    BASE_URL: str = Field(
        default="",
        description="Wonderful API base URL (required when SKIP=false)",
    )
    API_KEY: SecretStr = Field(
        default=SecretStr(""),
        description="API key for authentication with Wonderful (required when SKIP=false)",
    )
    KNOWLEDGEBASE_ID: str = Field(
        default="",
        description="Knowledge base ID to push documents to (required when SKIP=false)",
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
    MAX_RETRIES: int = Field(
        default=3,
        gt=0,
        description="Max attempts per HTTP call before giving up",
    )
    RETRY_BACKOFF: float = Field(
        default=0.5,
        ge=0,
        description="Base delay in seconds for exponential back-off between retries (0 disables sleep): 0.5s, 1s, 2s, ...",
    )

    @model_validator(mode="after")
    def _require_credentials_unless_skipped(self) -> "WonderfulRAGSettings":
        if self.SKIP:
            return self
        missing = [
            name
            for name, value in (
                ("BASE_URL", self.BASE_URL),
                ("API_KEY", self.API_KEY.get_secret_value()),  # pylint: disable=no-member
                ("KNOWLEDGEBASE_ID", self.KNOWLEDGEBASE_ID),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "WonderfulRAGStep is active (SKIP=false) but missing required settings: "
                + ", ".join(f"WONDERFULRAGSTEP__{name}" for name in missing)
            )
        return self
