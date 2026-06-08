# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for S3MarkdownStep — the dumb S3 sink that dumps the doc list as one JSON array."""

import json

import boto3
import pytest
from moto import mock_aws

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed
from wurzel.steps.s3 import S3MarkdownStep

BUCKET = "test-kb-bucket"
REGION = "eu-central-1"


def _docs() -> list[MarkdownDataContract]:
    return [
        MarkdownDataContract(md="# A\ntext a", keywords="k1,k2", url="https://x/a", metadata={"char_len": 6}),
        MarkdownDataContract(md="# B\ntext b", keywords="", url="https://x/b", metadata=None),
    ]


@pytest.fixture
def aws_creds(env):
    """Fake creds so boto3/moto are happy; bare settings env for direct construction."""
    env.update(
        {
            "AWS_ACCESS_KEY_ID": "testing",  # pragma: allowlist secret
            "AWS_SECRET_ACCESS_KEY": "testing",  # pragma: allowlist secret
            "AWS_DEFAULT_REGION": REGION,
        }
    )


@pytest.fixture
def s3_bucket(aws_creds):
    with mock_aws():
        client = boto3.client("s3", region_name=REGION)
        client.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION})
        yield client


def _list_keys(client) -> list[str]:
    resp = client.list_objects_v2(Bucket=BUCKET, Prefix="kb/")
    return sorted(o["Key"] for o in resp.get("Contents", []))


def test_writes_latest_and_timestamped_snapshot(s3_bucket, env):
    env.update({"BUCKET": BUCKET, "PREFIX": "kb", "REGION": REGION})
    docs = _docs()

    out = S3MarkdownStep().run(docs)

    keys = _list_keys(s3_bucket)
    assert "kb/latest.json" in keys
    ts_keys = [k for k in keys if k != "kb/latest.json"]
    assert len(ts_keys) == 1, f"expected one timestamped snapshot, got {ts_keys}"

    expected = [d.model_dump() for d in docs]
    latest_body = json.loads(s3_bucket.get_object(Bucket=BUCKET, Key="kb/latest.json")["Body"].read())
    snap_body = json.loads(s3_bucket.get_object(Bucket=BUCKET, Key=ts_keys[0])["Body"].read())
    assert latest_body == expected
    assert snap_body == expected  # snapshot and latest are byte-identical
    assert out == docs  # passthrough


def test_metadata_field_preserved(s3_bucket, env):
    env.update({"BUCKET": BUCKET, "PREFIX": "kb", "REGION": REGION})
    S3MarkdownStep().run(_docs())
    body = json.loads(s3_bucket.get_object(Bucket=BUCKET, Key="kb/latest.json")["Body"].read())
    assert body[0]["metadata"] == {"char_len": 6}
    assert body[1]["metadata"] is None


def test_provenance_object_metadata(s3_bucket, env):
    env.update({"BUCKET": BUCKET, "PREFIX": "kb", "REGION": REGION, "TENANT": "cz"})
    S3MarkdownStep().run(_docs())
    head = s3_bucket.head_object(Bucket=BUCKET, Key="kb/latest.json")
    meta = head["Metadata"]  # boto3 strips the x-amz-meta- prefix and lowercases keys
    assert meta["record-count"] == "2"
    assert meta["tenant"] == "cz"
    assert meta["run-ts"]  # present


def test_empty_prefix_writes_to_bucket_root(s3_bucket, env):
    # PREFIX="" (default) → keys at the bucket root, no leading slash.
    env.update({"BUCKET": BUCKET, "PREFIX": "", "REGION": REGION})
    S3MarkdownStep().run(_docs())
    keys = sorted(o["Key"] for o in s3_bucket.list_objects_v2(Bucket=BUCKET).get("Contents", []))
    assert "latest.json" in keys
    assert not any(k.startswith("/") for k in keys)  # no leading-slash keys
    ts_keys = [k for k in keys if k != "latest.json"]
    assert len(ts_keys) == 1 and ts_keys[0].endswith(".json")


def test_skip_is_noop_passthrough(env):
    env.set("SKIP", "true")  # no bucket / creds required
    docs = _docs()
    out = S3MarkdownStep().run(docs)
    assert out == docs


def test_empty_input_does_not_write(s3_bucket, env):
    # Never clobber latest.json with an empty array when the upstream yields nothing.
    env.update({"BUCKET": BUCKET, "PREFIX": "kb", "REGION": REGION})
    out = S3MarkdownStep().run([])
    assert out == []
    assert _list_keys(s3_bucket) == []  # nothing written


def test_put_error_raises_stepfailed(aws_creds, env):
    # Bucket does not exist under moto → PutObject fails → StepFailed.
    with mock_aws():
        env.update({"BUCKET": "does-not-exist", "PREFIX": "kb", "REGION": REGION})
        with pytest.raises(StepFailed):
            S3MarkdownStep().run(_docs())


def test_step_scoped_credentials_passed_to_client(env, mocker):
    # When the step's own AWS_* settings are set, they are passed explicitly to the client
    # (so the pod's ambient AWS identity is never used/overridden).
    env.update(
        {
            "BUCKET": BUCKET,
            "REGION": REGION,
            "AWS_ACCESS_KEY_ID": "AKIASTEPSCOPED",  # pragma: allowlist secret
            "AWS_SECRET_ACCESS_KEY": "stepscopedsecret",  # pragma: allowlist secret
        }
    )
    fake = mocker.patch("wurzel.steps.s3.step.boto3.client")
    S3MarkdownStep()._build_client()
    _, kwargs = fake.call_args
    assert kwargs["aws_access_key_id"] == "AKIASTEPSCOPED"  # pragma: allowlist secret
    assert kwargs["aws_secret_access_key"] == "stepscopedsecret"  # pragma: allowlist secret


def test_credentials_fall_back_to_chain_when_unset(env, monkeypatch, mocker):
    # No step-scoped creds → don't pass any, let boto3's provider chain (env/IRSA) decide.
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    env.update({"BUCKET": BUCKET, "REGION": REGION})
    fake = mocker.patch("wurzel.steps.s3.step.boto3.client")
    S3MarkdownStep()._build_client()
    _, kwargs = fake.call_args
    assert "aws_access_key_id" not in kwargs
    assert "aws_secret_access_key" not in kwargs
