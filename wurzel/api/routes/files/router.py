# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""File upload routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status

from wurzel.api.routes.files.data import DeleteFileResponse, FileInfo, FileUploadResponse, FileValidationError
from wurzel.api.services.file_service import FileUploadService
from wurzel.storage.file_storage import FileMetadata


router = APIRouter(tags=["files"])


def _to_file_info(metadata: FileMetadata) -> FileInfo:
    """Convert storage FileMetadata to API FileInfo."""
    return FileInfo(
        file_id=metadata.file_id,
        filename=metadata.filename,
        file_size=metadata.file_size,
        uploaded_at=metadata.uploaded_at,
        mime_type=metadata.mime_type,
    )


def get_file_upload_service() -> FileUploadService:
    """Dependency injection for FileUploadService.

    In a real application, this would be configured with the appropriate
    FileStorageService backend (e.g., S3FileStorageService).

    For now, this is a placeholder that will be configured by the main app.
    """
    # This will be injected by the main application
    raise NotImplementedError("FileUploadService must be configured in the main app")


@router.post(
    "",
    response_model=FileUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload files for a step",
    description="Upload one or more files to be used as input for a specific step. "
    "Files are validated against the step's accepted file types.",
)
async def upload_files(
    project_id: str,
    step_id: str,
    step_path: str,
    files: list[UploadFile] = File(...),
    file_service: FileUploadService = Depends(get_file_upload_service),
) -> FileUploadResponse:
    """Upload files for a step.

    Args:
        project_id: Project identifier.
        step_id: Step identifier (unique within project).
        step_path: Fully-qualified step class path (e.g., 'wurzel.steps.ingest.MyCSVIngestStep').
        files: List of files to upload.
        file_service: File upload service (injected).

    Returns:
        FileUploadResponse with successfully uploaded files and any errors.

    Raises:
        404: If step_path does not correspond to a valid TypedStep.
        422: If request is malformed (e.g., missing parameters).
    """
    # Read file contents
    file_tuples = []
    for file in files:
        content = await file.read()
        mime_type = file.content_type
        file_tuples.append((file.filename or "unknown", content, mime_type))

    # Validate and upload
    uploaded_files, errors = file_service.validate_and_upload(
        project_id=project_id,
        step_id=step_id,
        step_path=step_path,
        files=file_tuples,
    )

    return FileUploadResponse(
        files=[_to_file_info(m) for m in uploaded_files],
        errors=[FileValidationError(filename=e.filename, reason=e.reason) for e in errors],
    )


@router.get(
    "",
    response_model=list[FileInfo],
    status_code=status.HTTP_200_OK,
    summary="List uploaded files for a step",
    description="List all files that have been uploaded for a specific step.",
)
async def list_files(
    project_id: str,
    step_id: str,
    file_service: FileUploadService = Depends(get_file_upload_service),
) -> list[FileInfo]:
    """List all uploaded files for a step."""
    return [_to_file_info(m) for m in file_service.list_files(project_id, step_id)]


@router.delete(
    "/{file_id}",
    response_model=DeleteFileResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete an uploaded file",
    description="Delete a file that was previously uploaded for a step.",
)
async def delete_file(
    project_id: str,
    step_id: str,
    file_id: str,
    file_service: FileUploadService = Depends(get_file_upload_service),
) -> DeleteFileResponse:
    """Delete an uploaded file."""
    deleted = file_service.delete_file(project_id, step_id, file_id)
    return DeleteFileResponse(deleted=deleted, file_id=file_id)
