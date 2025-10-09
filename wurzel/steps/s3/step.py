# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""S3 markdown sink — dumps the whole document list to S3 as one JSON array."""

import json
from datetime import datetime, timezone
from logging import getLogger

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed
from wurzel.core import TypedStep

from .settings import S3MarkdownStepSettings

log = getLogger(__name__)


class S3MarkdownStep(TypedStep[S3MarkdownStepSettings, list[MarkdownDataContract], list[MarkdownDataContract]]):
    """Write the input documents to S3 as a single JSON array, then pass them through.

    The whole ``list[MarkdownDataContract]`` is serialized to ONE JSON array
    (``[{md, keywords, url, metadata}, ...]`` — *not* per-record ``.md`` files) and PUT to:

      * ``s3://<BUCKET>/<PREFIX>/<UTC-timestamp>.json`` — immutable per-run history snapshot
      * ``s3://<BUCKET>/<PREFIX>/latest.json``          — stable pointer to the newest snapshot

    Both objects carry the same body and ``x-amz-meta-*`` provenance (record-count, run-ts,
    tenant). The step returns its input unchanged (passthrough sink) so it can chain.

    When ``S3MARKDOWNSTEP__SKIP=true`` the step is a no-op: no S3 call, no credentials required.
    Empty input is a no-op write (it never clobbers ``latest.json`` with an empty array).

    Environment Variables:
        S3MARKDOWNSTEP__SKIP:         When true, skip processing (default: false)
        S3MARKDOWNSTEP__BUCKET:       Target S3 bucket (required when not SKIP)
        S3MARKDOWNSTEP__PREFIX:       Optional key prefix (default: "" — bucket root)
        S3MARKDOWNSTEP__TENANT:       Provenance tenant tag (default: = PREFIX)
        S3MARKDOWNSTEP__REGION:                AWS region (default: "eu-central-1")
        S3MARKDOWNSTEP__ENDPOINT_URL:          Override endpoint (MinIO/localstack tests only)
        S3MARKDOWNSTEP__AWS_ACCESS_KEY_ID:     Step-scoped AWS access key id (optional)
        S3MARKDOWNSTEP__AWS_SECRET_ACCESS_KEY: Step-scoped AWS secret access key (optional)
    """

    def __init__(self) -> None:
        super().__init__()
        if self.settings.SKIP:
            log.info("S3MarkdownStep skipped — running in no-op (passthrough) mode")

    def _build_client(self):
        boto3_client_parameters = {"region_name": self.settings.REGION}
        if self.settings.ENDPOINT_URL:
            boto3_client_parameters["endpoint_url"] = self.settings.ENDPOINT_URL
        # Step-scoped credentials take precedence; when unset, boto3 falls back to its
        # default provider chain (ambient env, instance/IRSA role).
        secret = self.settings.AWS_SECRET_ACCESS_KEY.get_secret_value()
        if self.settings.AWS_ACCESS_KEY_ID and secret:
            boto3_client_parameters["aws_access_key_id"] = self.settings.AWS_ACCESS_KEY_ID
            boto3_client_parameters["aws_secret_access_key"] = secret
        return boto3.client("s3", **boto3_client_parameters)

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Dump the document list to S3 (snapshot + latest pointer) and pass it through."""
        if self.settings.SKIP:
            log.info(f"S3MarkdownStep skipped — passing through {len(inpt)} documents unchanged")
            return inpt
        if not inpt:
            # Never overwrite latest.json with an empty array when the upstream yields nothing.
            log.warning("No documents to write — skipping S3 upload (latest.json left intact)")
            return inpt

        body = json.dumps([doc.model_dump() for doc in inpt], ensure_ascii=False).encode("utf-8")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
        snapshot_key = f"{self.settings.key_prefix}{ts}.json"
        latest_key = f"{self.settings.key_prefix}latest.json"
        metadata = {
            "record-count": str(len(inpt)),
            "run-ts": ts,
            "tenant": self.settings.resolved_tenant,
        }

        client = self._build_client()
        log.info(f"Uploading {len(inpt)} documents to s3://{self.settings.BUCKET}/{snapshot_key} (+ latest.json)")
        try:
            for key in (snapshot_key, latest_key):
                client.put_object(
                    Bucket=self.settings.BUCKET,
                    Key=key,
                    Body=body,
                    ContentType="application/json",
                    Metadata=metadata,
                )
        except (BotoCoreError, ClientError) as e:
            raise StepFailed(f"S3 upload to bucket '{self.settings.BUCKET}' failed: {e}") from e

        # Passthrough preserves the original input length and order.
        return inpt
