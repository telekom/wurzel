# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for file upload API routes."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi", reason="wurzel[fastapi] not installed")

from fastapi.testclient import TestClient  # noqa: E402

from wurzel.api.routes.files.router import get_file_upload_service  # noqa: E402
from wurzel.api.services.file_service import FileUploadService  # noqa: E402
from tests.api.routes.conftest import ADMIN_USER, make_app  # noqa: E402
from tests.storage.test_file_storage import MockFileStorageService  # noqa: E402

_UPLOAD_URL = "/v1/projects/proj1/steps/step1/files"
_STEP_PATH = "wurzel.steps.MyStep"


@pytest.fixture
def file_service():
    return FileUploadService(MockFileStorageService())


@pytest.fixture
def app(file_service):
    _app = make_app(ADMIN_USER)
    _app.dependency_overrides[get_file_upload_service] = lambda: file_service
    return _app


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _step_info(extensions=None, mime_types=None):
    """Build a mock step_info with the given acceptance criteria."""
    m = type("StepInfo", (), {})()
    m.accepted_file_extensions = extensions or []
    m.accepted_mime_types = mime_types or []
    return m


class TestUploadFiles:
    @patch("wurzel.api.services.file_service.fetch_step_info")
    def test_upload_single_file(self, mock_fetch, client):
        mock_fetch.return_value = _step_info(extensions=[".csv"], mime_types=["text/csv"])

        r = client.post(
            _UPLOAD_URL,
            params={"step_path": _STEP_PATH},
            files={"files": ("data.csv", BytesIO(b"col1,col2\n1,2"), "text/csv")},
        )

        assert r.status_code == 200
        data = r.json()
        assert len(data["files"]) == 1
        assert data["files"][0]["filename"] == "data.csv"
        assert data["errors"] == []

    @patch("wurzel.api.services.file_service.fetch_step_info")
    def test_upload_multiple_files(self, mock_fetch, client):
        mock_fetch.return_value = _step_info(extensions=[".csv", ".tsv"])

        r = client.post(
            _UPLOAD_URL,
            params={"step_path": _STEP_PATH},
            files=[
                ("files", ("data1.csv", BytesIO(b"content1"), "text/csv")),
                ("files", ("data2.tsv", BytesIO(b"content2"), "text/plain")),
            ],
        )

        assert r.status_code == 200
        data = r.json()
        assert len(data["files"]) == 2
        assert data["errors"] == []

    @patch("wurzel.api.services.file_service.fetch_step_info")
    def test_invalid_extension_is_rejected(self, mock_fetch, client):
        mock_fetch.return_value = _step_info(extensions=[".csv"])

        r = client.post(
            _UPLOAD_URL,
            params={"step_path": _STEP_PATH},
            files=[
                ("files", ("valid.csv", BytesIO(b"valid"), "text/csv")),
                ("files", ("invalid.txt", BytesIO(b"invalid"), "text/plain")),
            ],
        )

        assert r.status_code == 200
        data = r.json()
        assert len(data["files"]) == 1
        assert len(data["errors"]) == 1
        assert data["errors"][0]["filename"] == "invalid.txt"
        assert "not accepted" in data["errors"][0]["reason"]

    @patch("wurzel.api.services.file_service.fetch_step_info")
    def test_response_has_file_id_and_size(self, mock_fetch, client):
        mock_fetch.return_value = _step_info()
        content = b"hello,world"

        r = client.post(
            _UPLOAD_URL,
            params={"step_path": _STEP_PATH},
            files={"files": ("test.csv", BytesIO(content), "text/csv")},
        )

        info = r.json()["files"][0]
        assert "file_id" in info
        assert info["file_size"] == len(content)
        assert "uploaded_at" in info


class TestListFiles:
    @patch("wurzel.api.services.file_service.fetch_step_info")
    def test_lists_previously_uploaded_files(self, mock_fetch, client):
        mock_fetch.return_value = _step_info()

        # Upload two files
        client.post(
            _UPLOAD_URL,
            params={"step_path": _STEP_PATH},
            files=[
                ("files", ("file1.csv", BytesIO(b"a"), "text/csv")),
                ("files", ("file2.csv", BytesIO(b"b"), "text/csv")),
            ],
        )

        r = client.get(_UPLOAD_URL)

        assert r.status_code == 200
        filenames = {f["filename"] for f in r.json()}
        assert filenames == {"file1.csv", "file2.csv"}

    def test_empty_list_when_no_files(self, client):
        r = client.get(_UPLOAD_URL)
        assert r.status_code == 200
        assert r.json() == []


class TestDeleteFile:
    @patch("wurzel.api.services.file_service.fetch_step_info")
    def test_delete_existing_file(self, mock_fetch, client):
        mock_fetch.return_value = _step_info()

        # Upload first
        r = client.post(
            _UPLOAD_URL,
            params={"step_path": _STEP_PATH},
            files={"files": ("data.csv", BytesIO(b"content"), "text/csv")},
        )
        file_id = r.json()["files"][0]["file_id"]

        r = client.delete(f"{_UPLOAD_URL}/{file_id}")

        assert r.status_code == 200
        assert r.json()["deleted"] is True
        assert r.json()["file_id"] == file_id

    @patch("wurzel.api.services.file_service.fetch_step_info")
    def test_delete_nonexistent_returns_false(self, mock_fetch, client):
        r = client.delete(f"{_UPLOAD_URL}/nonexistent-id")

        assert r.status_code == 200
        assert r.json()["deleted"] is False

