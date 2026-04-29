# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Pydantic models for file upload routes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    """Information about an uploaded file."""

    file_id: str = Field(description="Unique identifier for the file")
    filename: str = Field(description="Original filename")
    file_size: int = Field(description="File size in bytes")
    uploaded_at: datetime = Field(description="Timestamp of upload")
    mime_type: str | None = Field(None, description="MIME type of the file")


class FileValidationError(BaseModel):
    """Error details for a file that failed validation or upload."""

    filename: str = Field(description="Filename that failed")
    reason: str = Field(description="Reason for the failure")


class FileUploadResponse(BaseModel):
    """Response from file upload endpoint."""

    files: list[FileInfo] = Field(default_factory=list, description="Successfully uploaded files")
    errors: list[FileValidationError] = Field(
        default_factory=list, description="Files that failed validation or upload"
    )


class DeleteFileResponse(BaseModel):
    """Response from file delete endpoint."""

    deleted: bool = Field(description="True if the file was deleted, False if it did not exist")
    file_id: str = Field(description="File identifier that was targeted")
