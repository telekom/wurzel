# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for S3-based file storage service."""

import sys
from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_boto3():
    """Inject a mock boto3 into sys.modules so the lazy import inside __init__ works."""
    mock_boto3_module = MagicMock()
    mock_client = MagicMock()
    mock_boto3_module.client.return_value = mock_client
    with patch.dict(sys.modules, {"boto3": mock_boto3_module}):
        yield mock_boto3_module, mock_client


@pytest.fixture
def s3_service(mock_boto3):
    from wurzel.storage.file_storage_s3 import S3FileStorageService

    return S3FileStorageService(bucket_name="test-bucket")


@pytest.fixture
def s3_service_with_prefix(mock_boto3):
    from wurzel.storage.file_storage_s3 import S3FileStorageService

    return S3FileStorageService(bucket_name="test-bucket", bucket_prefix="myprefix", region_name="us-east-1")


class TestS3FileStorageServiceInit:
    def test_init_creates_s3_client(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        mock, mock_client = mock_boto3
        svc = S3FileStorageService(bucket_name="my-bucket")
        assert svc.bucket_name == "my-bucket"
        assert svc.bucket_prefix == "wurzel"
        mock.client.assert_called_once_with("s3", region_name=None)

    def test_init_with_custom_prefix_and_region(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        mock, _ = mock_boto3
        svc = S3FileStorageService(bucket_name="b", bucket_prefix="pfx", region_name="eu-west-1")
        assert svc.bucket_prefix == "pfx"
        mock.client.assert_called_once_with("s3", region_name="eu-west-1")

    def test_init_raises_when_boto3_missing(self):
        import sys

        # boto3 is not installed; remove any cached mock so import fails naturally
        saved = sys.modules.pop("boto3", None)
        try:
            from wurzel.storage.file_storage_s3 import S3FileStorageService

            with pytest.raises(ImportError, match="boto3"):
                S3FileStorageService(bucket_name="x")
        finally:
            if saved is not None:
                sys.modules["boto3"] = saved

    def test_storage_key_format(self, s3_service):
        key = s3_service._storage_key("proj1", "step1", "file123", "foo.txt")
        assert key == "wurzel/projects/proj1/steps/step1/files/file123/foo.txt"


class TestS3Upload:
    def test_upload_bytes(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        svc = S3FileStorageService(bucket_name="test-bucket")
        metadata = svc.upload("proj", "step", b"hello", "test.txt")

        assert metadata.filename == "test.txt"
        assert metadata.file_size == 5
        assert metadata.mime_type is None
        assert metadata.file_id is not None
        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Body"] == b"hello"

    def test_upload_bytes_with_mime_type(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        svc = S3FileStorageService(bucket_name="test-bucket")
        metadata = svc.upload("proj", "step", b"data", "file.pdf", mime_type="application/pdf")

        assert metadata.mime_type == "application/pdf"
        call_kwargs = mock_client.put_object.call_args[1]
        assert call_kwargs["ContentType"] == "application/pdf"

    def test_upload_binary_stream(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        svc = S3FileStorageService(bucket_name="test-bucket")
        stream = BytesIO(b"stream data")
        metadata = svc.upload("proj", "step", stream, "file.bin")

        assert metadata.file_size == 11
        mock_client.put_object.assert_called_once()

    def test_upload_raises_on_s3_error(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_client.put_object.side_effect = Exception("S3 error")
        svc = S3FileStorageService(bucket_name="test-bucket")

        with pytest.raises(OSError, match="Failed to upload"):
            svc.upload("proj", "step", b"data", "file.txt")


class TestS3GetFileMetadata:
    def test_get_metadata_success(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_client.list_objects_v2.return_value = {
            "Contents": [
                {
                    "Key": "wurzel/projects/proj/steps/step/files/abc123/myfile.txt",
                    "Size": 42,
                    "LastModified": datetime(2024, 1, 1, tzinfo=UTC),
                }
            ]
        }
        svc = S3FileStorageService(bucket_name="test-bucket")
        metadata = svc.get_file_metadata("proj", "step", "abc123")

        assert metadata.filename == "myfile.txt"
        assert metadata.file_size == 42
        assert metadata.file_id == "abc123"

    def test_get_metadata_not_found(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_client.list_objects_v2.return_value = {}
        svc = S3FileStorageService(bucket_name="test-bucket")

        with pytest.raises(FileNotFoundError):
            svc.get_file_metadata("proj", "step", "missing")

    def test_get_metadata_empty_contents(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_client.list_objects_v2.return_value = {"Contents": []}
        svc = S3FileStorageService(bucket_name="test-bucket")

        with pytest.raises(FileNotFoundError):
            svc.get_file_metadata("proj", "step", "missing")

    def test_get_metadata_raises_on_s3_error(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_client.list_objects_v2.side_effect = Exception("network error")
        svc = S3FileStorageService(bucket_name="test-bucket")

        with pytest.raises(OSError, match="Failed to retrieve metadata"):
            svc.get_file_metadata("proj", "step", "abc")


class TestS3Delete:
    def test_delete_existing_file(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_client.list_objects_v2.return_value = {"Contents": [{"Key": "wurzel/projects/proj/steps/step/files/abc/file.txt"}]}
        svc = S3FileStorageService(bucket_name="test-bucket")
        result = svc.delete("proj", "step", "abc")

        assert result is True
        mock_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="wurzel/projects/proj/steps/step/files/abc/file.txt")

    def test_delete_nonexistent_file(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_client.list_objects_v2.return_value = {}
        svc = S3FileStorageService(bucket_name="test-bucket")
        result = svc.delete("proj", "step", "missing")

        assert result is False
        mock_client.delete_object.assert_not_called()

    def test_delete_empty_contents(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_client.list_objects_v2.return_value = {"Contents": []}
        svc = S3FileStorageService(bucket_name="test-bucket")
        result = svc.delete("proj", "step", "missing")

        assert result is False

    def test_delete_raises_on_s3_error(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_client.list_objects_v2.side_effect = Exception("error")
        svc = S3FileStorageService(bucket_name="test-bucket")

        with pytest.raises(OSError, match="Failed to delete"):
            svc.delete("proj", "step", "abc")


class TestS3ListFiles:
    def test_list_files_returns_metadata(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "wurzel/projects/proj/steps/step/files/id1/file1.txt",
                        "Size": 10,
                        "LastModified": datetime(2024, 1, 1, tzinfo=UTC),
                    },
                    {
                        "Key": "wurzel/projects/proj/steps/step/files/id2/file2.txt",
                        "Size": 20,
                        "LastModified": datetime(2024, 1, 2, tzinfo=UTC),
                    },
                ]
            }
        ]
        svc = S3FileStorageService(bucket_name="test-bucket")
        files = svc.list_files("proj", "step")

        assert len(files) == 2
        assert files[0].filename == "file1.txt"
        assert files[0].file_id == "id1"
        assert files[1].filename == "file2.txt"

    def test_list_files_empty(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{}]
        svc = S3FileStorageService(bucket_name="test-bucket")
        files = svc.list_files("proj", "step")

        assert files == []

    def test_list_files_multiple_pages(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "wurzel/projects/p/steps/s/files/id1/a.txt",
                        "Size": 5,
                        "LastModified": datetime(2024, 1, 1, tzinfo=UTC),
                    }
                ]
            },
            {
                "Contents": [
                    {
                        "Key": "wurzel/projects/p/steps/s/files/id2/b.txt",
                        "Size": 8,
                        "LastModified": datetime(2024, 1, 2, tzinfo=UTC),
                    }
                ]
            },
        ]
        svc = S3FileStorageService(bucket_name="test-bucket")
        files = svc.list_files("p", "s")
        assert len(files) == 2

    def test_list_files_raises_on_s3_error(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_client.get_paginator.side_effect = Exception("paginator error")
        svc = S3FileStorageService(bucket_name="test-bucket")

        with pytest.raises(OSError, match="Failed to list files"):
            svc.list_files("proj", "step")


class TestS3ReadFile:
    def test_read_file_success(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_body = MagicMock()
        mock_body.read.return_value = b"file content"
        mock_client.list_objects_v2.return_value = {"Contents": [{"Key": "wurzel/projects/p/steps/s/files/fid/file.txt"}]}
        mock_client.get_object.return_value = {"Body": mock_body}
        svc = S3FileStorageService(bucket_name="test-bucket")
        content = svc.read_file("p", "s", "fid")

        assert content == b"file content"

    def test_read_file_not_found(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_client.list_objects_v2.return_value = {}
        svc = S3FileStorageService(bucket_name="test-bucket")

        with pytest.raises(FileNotFoundError):
            svc.read_file("p", "s", "missing")

    def test_read_file_empty_contents(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_client.list_objects_v2.return_value = {"Contents": []}
        svc = S3FileStorageService(bucket_name="test-bucket")

        with pytest.raises(FileNotFoundError):
            svc.read_file("p", "s", "missing")

    def test_read_file_raises_on_s3_error(self, mock_boto3):
        from wurzel.storage.file_storage_s3 import S3FileStorageService

        _, mock_client = mock_boto3
        mock_client.list_objects_v2.side_effect = Exception("read error")
        svc = S3FileStorageService(bucket_name="test-bucket")

        with pytest.raises(OSError, match="Failed to read file"):
            svc.read_file("p", "s", "abc")
