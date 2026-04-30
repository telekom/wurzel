# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Base abstraction for file storage backends."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO


@dataclass
class FileMetadata:
    """Metadata for a stored file."""

    file_id: str
    filename: str
    file_size: int
    uploaded_at: datetime
    mime_type: str | None = None


class FileStorageService(abc.ABC):
    """Abstract base class for file storage backends.

    Implements an abstraction over file storage operations, supporting both
    local filesystem and cloud storage (e.g., S3).

    All file IDs are generated and returned by the service. Files are scoped
    to a project and step (path structure varies by implementation).
    """

    @abc.abstractmethod
    def upload(
        self,
        project_id: str,
        step_id: str,
        file_data: BinaryIO | bytes,
        filename: str,
        *,
        mime_type: str | None = None,
    ) -> FileMetadata:
        """Upload a file to storage.

        Args:
            project_id: Project identifier for scoping.
            step_id: Step identifier for scoping.
            file_data: File content as binary stream or bytes.
            filename: Original filename (used for retrieval).
            mime_type: MIME type of the file (optional).

        Returns:
            FileMetadata with the generated file_id.

        Raises:
            IOError: If upload fails.
        """

    @abc.abstractmethod
    def get_file_metadata(self, project_id: str, step_id: str, file_id: str) -> FileMetadata:
        """Retrieve metadata for a stored file.

        Args:
            project_id: Project identifier.
            step_id: Step identifier.
            file_id: File identifier returned by upload().

        Returns:
            FileMetadata for the file.

        Raises:
            FileNotFoundError: If file does not exist.
        """

    @abc.abstractmethod
    def delete(self, project_id: str, step_id: str, file_id: str) -> bool:
        """Delete a stored file.

        Args:
            project_id: Project identifier.
            step_id: Step identifier.
            file_id: File identifier.

        Returns:
            True if file was deleted, False if it did not exist.

        Raises:
            IOError: If deletion fails.
        """

    @abc.abstractmethod
    def list_files(self, project_id: str, step_id: str) -> list[FileMetadata]:
        """List all files for a project/step combination.

        Args:
            project_id: Project identifier.
            step_id: Step identifier.

        Returns:
            List of FileMetadata for all uploaded files.

        Raises:
            IOError: If listing fails.
        """

    @abc.abstractmethod
    def read_file(self, project_id: str, step_id: str, file_id: str) -> bytes:
        """Read the full contents of a stored file.

        Args:
            project_id: Project identifier.
            step_id: Step identifier.
            file_id: File identifier.

        Returns:
            File contents as bytes.

        Raises:
            FileNotFoundError: If file does not exist.
            IOError: If read fails.
        """
