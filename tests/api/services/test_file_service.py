# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from tests.storage.test_file_storage import MockFileStorageService
from wurzel.api.services.file_service import FileUploadService


class TestFileUploadService:
    @pytest.fixture
    def storage(self):
        return MockFileStorageService()

    @pytest.fixture
    def service(self, storage):
        return FileUploadService(storage)

    @patch("wurzel.api.services.file_service.fetch_step_info")
    def test_upload_valid_files(self, mock_fetch, service):
        mock_fetch.return_value.accepted_file_extensions = [".csv", ".tsv"]
        mock_fetch.return_value.accepted_mime_types = ["text/csv"]

        files = [
            ("data.csv", b"col1,col2\n1,2", "text/csv"),
            ("data.tsv", b"col1\tcol2\n1\t2", "text/csv"),
        ]

        successful, errors = service.validate_and_upload("proj1", "step1", "my.StepClass", files)

        assert len(successful) == 2
        assert len(errors) == 0
        assert successful[0].filename == "data.csv"
        assert successful[1].filename == "data.tsv"

    @patch("wurzel.api.services.file_service.fetch_step_info")
    def test_upload_invalid_extension(self, mock_fetch, service):
        mock_fetch.return_value.accepted_file_extensions = [".csv"]
        mock_fetch.return_value.accepted_mime_types = []

        files = [
            ("data.csv", b"valid", "text/csv"),
            ("data.txt", b"invalid", "text/plain"),
        ]

        successful, errors = service.validate_and_upload("proj1", "step1", "my.StepClass", files)

        assert len(successful) == 1
        assert len(errors) == 1
        assert errors[0].filename == "data.txt"
        assert "not accepted" in errors[0].reason

    @patch("wurzel.api.services.file_service.fetch_step_info")
    def test_upload_invalid_mime_type(self, mock_fetch, service):
        mock_fetch.return_value.accepted_file_extensions = []
        mock_fetch.return_value.accepted_mime_types = ["text/csv"]

        files = [
            ("data.csv", b"valid", "text/csv"),
            ("data.json", b"invalid", "application/json"),
        ]

        successful, errors = service.validate_and_upload("proj1", "step1", "my.StepClass", files)

        assert len(successful) == 1
        assert len(errors) == 1
        assert errors[0].filename == "data.json"

    @patch("wurzel.api.services.file_service.fetch_step_info")
    def test_upload_no_restrictions(self, mock_fetch, service):
        mock_fetch.return_value.accepted_file_extensions = []
        mock_fetch.return_value.accepted_mime_types = []

        files = [
            ("file1.txt", b"content1", "text/plain"),
            ("file2.csv", b"content2", "text/csv"),
        ]

        successful, errors = service.validate_and_upload("proj1", "step1", "my.StepClass", files)

        assert len(successful) == 2
        assert len(errors) == 0

    @patch("wurzel.api.services.file_service.fetch_step_info")
    def test_extension_case_insensitive(self, mock_fetch, service):
        mock_fetch.return_value.accepted_file_extensions = [".CSV"]
        mock_fetch.return_value.accepted_mime_types = []

        files = [("data.csv", b"content", None)]

        successful, errors = service.validate_and_upload("proj1", "step1", "my.StepClass", files)

        assert len(successful) == 1
        assert len(errors) == 0

    @patch("wurzel.api.services.file_service.fetch_step_info")
    def test_upload_with_storage_error(self, mock_fetch, service):
        mock_fetch.return_value.accepted_file_extensions = [".csv"]
        mock_fetch.return_value.accepted_mime_types = []

        service.storage.upload = Mock(side_effect=OSError("Storage unavailable"))

        files = [("data.csv", b"content", "text/csv")]

        successful, errors = service.validate_and_upload("proj1", "step1", "my.StepClass", files)

        assert len(successful) == 0
        assert len(errors) == 1
        assert "Upload failed" in errors[0].reason
