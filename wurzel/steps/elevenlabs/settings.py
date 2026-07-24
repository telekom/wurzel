# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for the ElevenLabs Knowledge Base connector step."""

# pylint: disable=duplicate-code
# Each connector step in wurzel/steps/ is an intentionally independent module
# rather than sharing a base class, so the common TIMEOUT/PUSH_ENABLED field +
# validator pattern is duplicated by design.

from typing import Self

from pydantic import Field, SecretStr, model_validator

from wurzel.core.settings import Settings


class ElevenLabsKnowledgeBaseSettings(Settings):
    """Configuration for the ElevenLabs Agents Knowledge Base connector.

    Attributes:
        API_KEY: API key for authentication (required when PUSH_ENABLED is True).
        BASE_URL: Base URL for the ElevenLabs API.
        NAME_PREFIX: Prefix applied to generated document names. Used both to
            namespace documents created by this pipeline and to scope the
            list/prune query so unrelated documents in the same workspace are
            never touched.
        PARENT_FOLDER_ID: Optional knowledge base folder to file new documents under.
        FOLDER_PER_SOURCE: When True, file documents into a subfolder named after the
            originating source step (the first step in this invocation's step_history
            lineage - see ElevenLabsKnowledgeBaseStep._source_category), created under
            PARENT_FOLDER_ID if it doesn't already exist. Requires PARENT_FOLDER_ID: the
            knowledge base root is a single flat namespace shared by every integration in
            the workspace, and the API enforces no uniqueness on folder names, so an
            unprefixed category folder created there could collide with an unrelated
            folder created by something else entirely.
        TIMEOUT: Request timeout in seconds.
        PUSH_ENABLED: When False, skip pushing to ElevenLabs and return the input data unchanged.
        PRUNE_STALE: When True, delete documents present in the knowledge base but
            absent from the input (so the knowledge base mirrors the input). Requires
            NAME_PREFIX to be set: the knowledge base is a single flat namespace shared
            by every integration in the workspace, so without a prefix "absent from the
            input" would match every other text document in the workspace too.
        PRUNE_FORCE: When True, prune deletions also remove the document from any
            agent it is attached to. When False (default) pruning a document still
            attached to an agent fails and is logged instead of raised.
        PAGE_SIZE: Number of documents fetched per page when listing existing documents.
        MAX_RETRIES: Max attempts per HTTP call before giving up.
        RETRY_BACKOFF: Base delay in seconds for exponential back-off between retries
            (0 disables sleep): 0.5s, 1s, 2s, ...

    Environment Variables (with ELEVENLABSKNOWLEDGEBASESTEP prefix):
        ELEVENLABSKNOWLEDGEBASESTEP__API_KEY:          API key for authentication
        ELEVENLABSKNOWLEDGEBASESTEP__BASE_URL:         ElevenLabs API base URL
        ELEVENLABSKNOWLEDGEBASESTEP__NAME_PREFIX:      Prefix for generated document names
        ELEVENLABSKNOWLEDGEBASESTEP__PARENT_FOLDER_ID: Knowledge base folder id for new documents
        ELEVENLABSKNOWLEDGEBASESTEP__FOLDER_PER_SOURCE: File documents into a per-source-step subfolder (default: False)
        ELEVENLABSKNOWLEDGEBASESTEP__TIMEOUT:          Request timeout in seconds
        ELEVENLABSKNOWLEDGEBASESTEP__PUSH_ENABLED:     Whether to push documents (default: True)
        ELEVENLABSKNOWLEDGEBASESTEP__PRUNE_STALE:      Delete documents absent from input (default: False)
        ELEVENLABSKNOWLEDGEBASESTEP__PRUNE_FORCE:      Force-delete documents attached to agents (default: False)
        ELEVENLABSKNOWLEDGEBASESTEP__PAGE_SIZE:        Page size when listing existing documents
        ELEVENLABSKNOWLEDGEBASESTEP__MAX_RETRIES:      Max attempts per HTTP call (default: 3)
        ELEVENLABSKNOWLEDGEBASESTEP__RETRY_BACKOFF:    Base back-off seconds - 0.5s, 1s, 2s, ... (default: 0.5)
    """

    API_KEY: SecretStr | None = Field(
        default=None,
        description="API key for authentication with ElevenLabs (required when PUSH_ENABLED is True)",
    )
    BASE_URL: str = Field(
        default="https://api.elevenlabs.io",
        description="Base URL for the ElevenLabs API",
    )
    NAME_PREFIX: str = Field(
        default="",
        description="Prefix applied to generated document names",
    )
    PARENT_FOLDER_ID: str | None = Field(
        default=None,
        description="Knowledge base folder id to file new documents under",
    )
    FOLDER_PER_SOURCE: bool = Field(
        default=False,
        description="When True, file documents into a subfolder named after the originating source step",
    )
    TIMEOUT: int = Field(
        default=120,
        gt=0,
        description="Request timeout in seconds",
    )
    PUSH_ENABLED: bool = Field(
        default=True,
        description="When False, skip pushing to ElevenLabs and return the input data unchanged",
    )
    PRUNE_STALE: bool = Field(
        default=False,
        description="When True, delete documents in the knowledge base absent from the input",
    )
    PRUNE_FORCE: bool = Field(
        default=False,
        description="When True, prune deletions also detach the document from any agent using it",
    )
    PAGE_SIZE: int = Field(
        default=100,
        gt=0,
        le=100,
        description="Number of documents fetched per page when listing existing documents",
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
    def validate_api_key_when_push_enabled(self) -> Self:
        """Ensure API_KEY is provided when PUSH_ENABLED is True."""
        if self.PUSH_ENABLED and self.API_KEY is None:
            raise ValueError("API_KEY is required when PUSH_ENABLED is True")
        return self

    @model_validator(mode="after")
    def validate_name_prefix_when_pruning(self) -> Self:
        """Require a non-empty NAME_PREFIX whenever PRUNE_STALE is enabled.

        The knowledge base is a single flat namespace shared by every integration
        in the workspace. Without a prefix, "documents absent from the input" means
        every other text document in the workspace - PRUNE_STALE would delete
        content this pipeline never created.
        """
        if self.PRUNE_STALE and not self.NAME_PREFIX:
            raise ValueError("NAME_PREFIX is required when PRUNE_STALE is True")
        return self

    @model_validator(mode="after")
    def validate_parent_folder_id_when_categorizing(self) -> Self:
        """Require PARENT_FOLDER_ID whenever FOLDER_PER_SOURCE is enabled.

        Without it, category folders would be created at the knowledge base root - the same
        flat namespace shared by every integration in the workspace - where an unprefixed,
        server-side-undeduplicated folder name could collide with an unrelated folder created
        by something else entirely.
        """
        if self.FOLDER_PER_SOURCE and not self.PARENT_FOLDER_ID:
            raise ValueError("PARENT_FOLDER_ID is required when FOLDER_PER_SOURCE is True")
        return self
