# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import io
import uuid
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.supabase_e2e

_STEP_PATH = "wurzel.steps.manual_markdown.ManualMarkdownStep"


def test_s3_upload_list_read_delete_roundtrip(
    s3_client,
    s3_file_service,
    project_context,
    step_info_factory,
):
    project_id = project_context["project_id"]
    step_id = f"s3-step-{uuid.uuid4().hex[:6]}"
    endpoint = f"/v1/projects/{project_id}/steps/{step_id}/files"

    with patch(
        "wurzel.api.services.file_service.fetch_step_info",
        return_value=step_info_factory(extensions=[".md"], mime_types=["text/markdown"]),
    ):
        upload = s3_client.post(
            endpoint,
            params={"step_path": _STEP_PATH},
            files=[
                ("files", ("doc1.md", io.BytesIO(b"# one"), "text/markdown")),
                ("files", ("doc2.md", io.BytesIO(b"# two"), "text/markdown")),
                ("files", ("empty.md", io.BytesIO(b""), "text/markdown")),
            ],
        )
    assert upload.status_code == 200
    payload = upload.json()
    assert len(payload["files"]) == 3
    assert payload["errors"] == []
    assert any(item["file_size"] == 0 for item in payload["files"])

    listed = s3_client.get(endpoint)
    assert listed.status_code == 200
    assert {item["filename"] for item in listed.json()} == {"doc1.md", "doc2.md", "empty.md"}

    first = payload["files"][0]
    content = s3_file_service.read_file(project_id=project_id, step_id=step_id, file_id=first["file_id"])
    assert content in (b"# one", b"# two", b"")

    deleted = s3_client.delete(f"{endpoint}/{first['file_id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    deleted_again = s3_client.delete(f"{endpoint}/{first['file_id']}")
    assert deleted_again.status_code == 200
    assert deleted_again.json()["deleted"] is False


def test_s3_upload_validation_and_partial_success(
    s3_client,
    project_context,
    step_info_factory,
):
    project_id = project_context["project_id"]
    step_id = f"s3-step-{uuid.uuid4().hex[:6]}"
    endpoint = f"/v1/projects/{project_id}/steps/{step_id}/files"

    with patch(
        "wurzel.api.services.file_service.fetch_step_info",
        return_value=step_info_factory(extensions=[".md"], mime_types=["text/markdown"]),
    ):
        upload = s3_client.post(
            endpoint,
            params={"step_path": _STEP_PATH},
            files=[
                ("files", ("ok.md", io.BytesIO(b"# ok"), "text/markdown")),
                ("files", ("bad.txt", io.BytesIO(b"bad"), "text/plain")),
            ],
        )

    assert upload.status_code == 200
    body = upload.json()
    assert len(body["files"]) == 1
    assert body["files"][0]["filename"] == "ok.md"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["filename"] == "bad.txt"
    assert "not accepted" in body["errors"][0]["reason"]
