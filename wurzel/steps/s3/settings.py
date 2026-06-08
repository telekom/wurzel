# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for the S3 markdown sink step."""

from pydantic import Field, SecretStr, computed_field, model_validator

from wurzel.step.settings import Settings


class S3MarkdownStepSettings(Settings):
    """Configuration for ``S3MarkdownStep``.

    Set ``S3MARKDOWNSTEP__SKIP=true`` to make the step a no-op (passthrough only, no S3
    calls, no credentials required) — useful in lower environments that should not write.

    AWS credentials: set ``S3MARKDOWNSTEP__AWS_ACCESS_KEY_ID`` /
    ``S3MARKDOWNSTEP__AWS_SECRET_ACCESS_KEY`` to use a credential scoped to this step
    (so it never collides with the pod's ambient ``AWS_*`` identity). When left empty the
    step falls back to the standard boto3 provider chain (ambient env, instance/IRSA role).

    Environment Variables (with S3MARKDOWNSTEP prefix):
        S3MARKDOWNSTEP__SKIP:                  When true, skip processing (default: false)
        S3MARKDOWNSTEP__BUCKET:                Target S3 bucket (required when not SKIP)
        S3MARKDOWNSTEP__PREFIX:                Optional key prefix (default: "" — bucket root)
        S3MARKDOWNSTEP__TENANT:                Provenance tenant tag (default: = PREFIX)
        S3MARKDOWNSTEP__REGION:                AWS region (default: "eu-central-1")
        S3MARKDOWNSTEP__ENDPOINT_URL:          Override endpoint (MinIO/localstack tests only)
        S3MARKDOWNSTEP__AWS_ACCESS_KEY_ID:     Step-scoped AWS access key id (optional)
        S3MARKDOWNSTEP__AWS_SECRET_ACCESS_KEY: Step-scoped AWS secret access key (optional)
    """

    SKIP: bool = Field(
        default=False,
        description="When true, the step skips the S3 write and passes input through unchanged.",
    )
    BUCKET: str = Field(
        default="",
        description="Target S3 bucket (required when SKIP=false)",
    )
    PREFIX: str = Field(
        default="",
        description="Optional key prefix; objects land at <PREFIX>/<ts>.json and <PREFIX>/latest.json (root when empty)",
    )
    TENANT: str = Field(
        default="",
        description="Provenance tenant tag written as x-amz-meta-tenant (defaults to PREFIX, then 'default')",
    )
    REGION: str = Field(
        default="eu-central-1",
        description="AWS region for the S3 client",
    )
    ENDPOINT_URL: str = Field(
        default="",
        description="Custom S3 endpoint URL — set only for MinIO / localstack tests",
    )
    AWS_ACCESS_KEY_ID: str = Field(
        default="",
        description="Step-scoped AWS access key id. Empty → fall back to the boto3 provider chain.",
    )
    AWS_SECRET_ACCESS_KEY: SecretStr = Field(
        default=SecretStr(""),
        description="Step-scoped AWS secret access key (paired with AWS_ACCESS_KEY_ID).",
    )

    @model_validator(mode="after")
    def _require_bucket_unless_skipped(self) -> "S3MarkdownStepSettings":
        if not self.SKIP and not self.BUCKET:
            raise ValueError("S3MarkdownStep is active (SKIP=false) but S3MARKDOWNSTEP__BUCKET is not set")
        return self

    @computed_field
    @property
    def key_prefix(self) -> str:
        """Normalized object-key prefix — ``"<PREFIX>/"`` (trailing slash) or ``""`` for bucket root."""
        prefix = self.PREFIX.strip("/")  # pylint: disable=no-member
        return f"{prefix}/" if prefix else ""

    @computed_field
    @property
    def resolved_tenant(self) -> str:
        """Provenance tenant tag written to ``x-amz-meta-tenant``: TENANT, else PREFIX, else 'default'."""
        return self.TENANT or self.PREFIX.strip("/") or "default"  # pylint: disable=no-member
