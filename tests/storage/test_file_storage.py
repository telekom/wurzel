# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for file storage services."""

import pytest
from datetime import datetime, timezone
from io import BytesIO

from wurzel.storage.file_storage import FileMetadata, FileStorageService


class MockFileStorageService(FileStorageService):
    """Mock file storage for testing."""

    def __init__(self):
        self.files = {}  # {(project_id, step_id, file_id): (metadata, content)}

    def upload(self, project_id: str, step_id: str, file_data, filename: str, mime_type=None):
        import uuid
        file_id = str(uuid.uuid4())

        if isinstance(file_data, bytes):
            content = file_data
        else:
            content = file_data.read()

        metadata = FileMetadata(
            file_id=file_id,
            filename=filename,
            file_size=len(content),
            uploaded_at=datetime.now(timezone.utc),
            mime_type=mime_type,
        )

        self.files[(project_id, step_id, file_id)] = (metadata, content)
        return metadata

    def get_file_metadata(self, project_id: str, step_id: str, file_id: str):
        if (project_id, step_id, file_id) not in self.files:
            raise FileNotFoundError(f"File {file_id} not found")
        metadata, _ = self.files[(project_id, step_id, file_id)]
        return metadata

    def delete(self, project_id: str, step_id: str, file_id: str):
        if (project_id, step_id, file_id) in self.files:
            del self.files[(project_id, step_id, file_id)]
            return True
        return False

    def list_files(self, project_id: str, step_id: str):
        return [
            metadata
            for (p, s, _), (metadata, _) in self.files.items()
            if p == project_id and s == step_id
        ]

    def read_file(self, project_id: str, step_id: str, file_id: str):
        if (project_id, step_id, file_id) not in self.files:
            raise FileNotFoundError(f"File {file_id} not found")
        _, content = self.files[(project_id, step_id, file_id)]
        return content


class TestMockFileStorageService:
    """Test the mock storage service."""

    def test_upload_with_bytes(self):
        storage = MockFileStorageService()
        content = b"test content"
        metadata = storage.upload("proj1", "step1", content, "test.txt", "text/plain")

        assert metadata.filename == "test.txt"
        assert metadata.file_size == len(content)
        assert metadata.mime_type == "text/plain"
        assert metadata.file_id is not None

    def test_upload_with_stream(self):
        storage = MockFileStorageService()
        content = b"test content"
        stream = BytesIO(content)
        metadata = storage.upload("proj1", "step1", stream, "test.txt", "text/plain")

        assert metadata.file_size == len(content)

    def test_get_file_metadata(self):
        storage = MockFileStorageService()
        metadata = storage.upload("proj1", "step1", b"content", "test.txt")
        retrieved = storage.get_file_metadata("proj1", "step1", metadata.file_id)

        assert retrieved.filename == "test.txt"
        assert retrieved.file_size == 7

    def test_get_file_metadata_not_found(self):
        storage = MockFileStorageService()
        with pytest.raises(FileNotFoundError):
            storage.get_file_metadata("proj1", "step1", "nonexistent")

    def test_delete_existing_file(self):
        storage = MockFileStorageService()
        metadata = storage.upload("proj1", "step1", b"content", "test.txt")
        deleted = storage.delete("proj1", "step1", metadata.file_id)

        assert deleted is True
        with pytest.raises(FileNotFoundError):
            storage.get_file_metadata("proj1", "step1", metadata.file_id)

    def test_delete_nonexistent_file(self):
        storage = MockFileStorageService()
        deleted = storage.delete("proj1", "step1", "nonexistent")
        assert deleted is False

    def test_list_files(self):
        storage = MockFileStorageService()
        storage.upload("proj1", "step1", b"file1", "test1.txt")
        storage.upload("proj1", "step1", b"file2", "test2.txt")
        storage.upload("proj1", "step2", b"file3", "test3.txt")

        files = storage.list_files("proj1", "step1")
        assert len(files) == 2

        files = storage.list_files("proj1", "step2")
        assert len(files) == 1

    def test_read_file(self):
        storage = MockFileStorageService()
        original_content = b"test content"
        metadata = storage.upload("proj1", "step1", original_content, "test.txt")
        content = storage.read_file("proj1", "step1", metadata.file_id)

        assert content == original_content

    def test_read_file_not_found(self):
        storage = MockFileStorageService()
        with pytest.raises(FileNotFoundError):
            storage.read_file("proj1", "step1", "nonexistent")
