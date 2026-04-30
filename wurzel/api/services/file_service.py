# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""File upload service with validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wurzel.api.routes.steps.service import fetch_step_info
from wurzel.storage.file_storage import FileMetadata, FileStorageService


@dataclass
class FileUploadError:
    """Error details for a failed file upload."""

    filename: str
    reason: str


class FileUploadService:
    """Service for handling file uploads with validation.

    Validates uploaded files against a step's accepted file extensions and MIME types,
    then stores them using the configured FileStorageService.
    """

    def __init__(self, storage_service: FileStorageService):
        """Initialize the file upload service.

        Args:
            storage_service: Backend storage service (e.g., S3FileStorageService).
        """
        self.storage = storage_service

    def validate_and_upload(
        self,
        project_id: str,
        step_id: str,
        step_path: str,
        files: list[tuple[str, bytes, str | None]],
    ) -> tuple[list[FileMetadata], list[FileUploadError]]:
        """Validate and upload files for a specific step.

        Args:
            project_id: Project identifier.
            step_id: Step identifier.
            step_path: Fully-qualified step class path (e.g., 'wurzel.steps.MyStep').
            files: List of tuples (filename, file_data, mime_type).

        Returns:
            Tuple of (uploaded_files, errors) where:
            - uploaded_files: FileMetadata for each successfully stored file
            - errors: List of FileUploadError for failed validations/uploads

        Raises:
            APIError: 404 if step not found.
        """
        # Fetch step info to get file acceptance criteria
        step_info = fetch_step_info(step_path)

        accepted_extensions: list[str] = step_info.accepted_file_extensions
        accepted_mime_types: list[str] = step_info.accepted_mime_types

        successful_uploads: list[FileMetadata] = []
        errors: list[FileUploadError] = []

        for filename, file_data, mime_type in files:
            # Validate file extension
            if accepted_extensions:
                file_ext = Path(filename).suffix.lower()
                if file_ext not in [ext.lower() for ext in list(accepted_extensions)]:
                    errors.append(
                        FileUploadError(
                            filename=filename,
                            reason=f"File extension '{file_ext}' not accepted. Accepted: {', '.join(list(accepted_extensions))}",
                        )
                    )
                    continue

            # Validate MIME type
            if accepted_mime_types and mime_type:
                if mime_type not in accepted_mime_types:
                    errors.append(
                        FileUploadError(
                            filename=filename,
                            reason=f"MIME type '{mime_type}' not accepted. Accepted: {', '.join(list(accepted_mime_types))}",
                        )
                    )
                    continue

            # Upload the file
            try:
                metadata = self.storage.upload(
                    project_id=project_id,
                    step_id=step_id,
                    file_data=file_data,
                    filename=filename,
                    mime_type=mime_type,
                )
                successful_uploads.append(metadata)
            except OSError as exc:
                errors.append(
                    FileUploadError(
                        filename=filename,
                        reason=f"Upload failed: {str(exc)}",
                    )
                )

        return successful_uploads, errors

    def list_files(self, project_id: str, step_id: str) -> list[FileMetadata]:
        """List all uploaded files for a project/step."""
        return self.storage.list_files(project_id, step_id)

    def delete_file(self, project_id: str, step_id: str, file_id: str) -> bool:
        """Delete a stored file. Returns True if deleted, False if not found."""
        return self.storage.delete(project_id, step_id, file_id)
