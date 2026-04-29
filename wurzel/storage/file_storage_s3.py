# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""S3-based file storage backend for wurzel."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import BinaryIO

from wurzel.storage.file_storage import FileMetadata, FileStorageService


class S3FileStorageService(FileStorageService):
    """S3-based file storage service using boto3.

    Files are stored in a bucket with the path structure:
    ``{bucket_prefix}/projects/{project_id}/steps/{step_id}/files/{file_id}/{filename}``

    Requires boto3 to be installed and AWS credentials configured.
    """

    def __init__(self, bucket_name: str, bucket_prefix: str = "wurzel", region_name: str | None = None):
        """Initialize S3 file storage.

        Args:
            bucket_name: S3 bucket name.
            bucket_prefix: Prefix for all files in the bucket (default: "wurzel").
            region_name: AWS region (uses boto3 default if None).

        Raises:
            ImportError: If boto3 is not installed.
        """
        try:
            import boto3  # pylint: disable=import-outside-toplevel
        except ImportError as exc:
            raise ImportError("boto3 is required for S3FileStorageService. Install with: pip install boto3") from exc

        self.bucket_name = bucket_name
        self.bucket_prefix = bucket_prefix
        self._s3_client = boto3.client("s3", region_name=region_name)

    def _storage_key(self, project_id: str, step_id: str, file_id: str, filename: str) -> str:
        """Generate the S3 storage key for a file."""
        return f"{self.bucket_prefix}/projects/{project_id}/steps/{step_id}/files/{file_id}/{filename}"

    def upload(
        self,
        project_id: str,
        step_id: str,
        file_data: BinaryIO | bytes,
        filename: str,
        mime_type: str | None = None,
    ) -> FileMetadata:
        """Upload a file to S3.

        Args:
            project_id: Project identifier.
            step_id: Step identifier.
            file_data: File content as binary stream or bytes.
            filename: Original filename.
            mime_type: MIME type of the file (optional).

        Returns:
            FileMetadata with the generated file_id.

        Raises:
            IOError: If upload fails.
        """
        file_id = str(uuid.uuid4())
        key = self._storage_key(project_id, step_id, file_id, filename)

        try:
            # Convert BinaryIO to bytes if needed
            if isinstance(file_data, bytes):
                body = file_data
            else:
                body = file_data.read()

            # Calculate file size
            file_size = len(body)

            # Upload to S3
            extra_args = {}
            if mime_type:
                extra_args["ContentType"] = mime_type

            self._s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=body,
                **extra_args,
            )

            return FileMetadata(
                file_id=file_id,
                filename=filename,
                file_size=file_size,
                uploaded_at=datetime.now(timezone.utc),
                mime_type=mime_type,
            )
        except Exception as exc:
            raise IOError(f"Failed to upload file '{filename}' to S3: {exc}") from exc

    def get_file_metadata(self, project_id: str, step_id: str, file_id: str) -> FileMetadata:
        """Retrieve metadata for a stored file from S3.

        Note: This method requires listing files to find the filename.
        For efficiency, consider caching metadata client-side.

        Args:
            project_id: Project identifier.
            step_id: Step identifier.
            file_id: File identifier.

        Returns:
            FileMetadata for the file.

        Raises:
            FileNotFoundError: If file does not exist.
            IOError: If metadata retrieval fails.
        """
        try:
            # List objects to find the file with this ID
            prefix = f"{self.bucket_prefix}/projects/{project_id}/steps/{step_id}/files/{file_id}/"
            response = self._s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=1,
            )

            if "Contents" not in response or len(response["Contents"]) == 0:
                raise FileNotFoundError(
                    f"File '{file_id}' not found in S3 for project '{project_id}', step '{step_id}'"
                )

            # Get the first (and should be only) object
            obj = response["Contents"][0]
            filename = obj["Key"].rsplit("/", 1)[-1]

            return FileMetadata(
                file_id=file_id,
                filename=filename,
                file_size=obj["Size"],
                uploaded_at=obj["LastModified"],
                mime_type=None,  # S3 metadata doesn't always preserve MIME type
            )
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise IOError(f"Failed to retrieve metadata for file '{file_id}': {exc}") from exc

    def delete(self, project_id: str, step_id: str, file_id: str) -> bool:
        """Delete a stored file from S3.

        Args:
            project_id: Project identifier.
            step_id: Step identifier.
            file_id: File identifier.

        Returns:
            True if file was deleted, False if it did not exist.

        Raises:
            IOError: If deletion fails.
        """
        try:
            # List objects with this file_id to find the exact key
            prefix = f"{self.bucket_prefix}/projects/{project_id}/steps/{step_id}/files/{file_id}/"
            response = self._s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=1,
            )

            if "Contents" not in response or len(response["Contents"]) == 0:
                return False

            # Delete the object
            key = response["Contents"][0]["Key"]
            self._s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception as exc:
            raise IOError(f"Failed to delete file '{file_id}': {exc}") from exc

    def list_files(self, project_id: str, step_id: str) -> list[FileMetadata]:
        """List all files for a project/step combination in S3.

        Args:
            project_id: Project identifier.
            step_id: Step identifier.

        Returns:
            List of FileMetadata for all uploaded files.

        Raises:
            IOError: If listing fails.
        """
        try:
            prefix = f"{self.bucket_prefix}/projects/{project_id}/steps/{step_id}/files/"
            files = []
            paginator = self._s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            for page in pages:
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    # Extract file_id and filename from key
                    # Key format: prefix/projects/{id}/steps/{id}/files/{file_id}/{filename}
                    parts = obj["Key"].split("/")
                    if len(parts) >= 2:
                        filename = parts[-1]
                        file_id = parts[-2]

                        files.append(
                            FileMetadata(
                                file_id=file_id,
                                filename=filename,
                                file_size=obj["Size"],
                                uploaded_at=obj["LastModified"],
                                mime_type=None,
                            )
                        )

            return files
        except Exception as exc:
            raise IOError(f"Failed to list files for project '{project_id}', step '{step_id}': {exc}") from exc

    def read_file(self, project_id: str, step_id: str, file_id: str) -> bytes:
        """Read the full contents of a stored file from S3.

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
        try:
            # List objects to find the file
            prefix = f"{self.bucket_prefix}/projects/{project_id}/steps/{step_id}/files/{file_id}/"
            response = self._s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=1,
            )

            if "Contents" not in response or len(response["Contents"]) == 0:
                raise FileNotFoundError(
                    f"File '{file_id}' not found in S3 for project '{project_id}', step '{step_id}'"
                )

            key = response["Contents"][0]["Key"]
            response = self._s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise IOError(f"Failed to read file '{file_id}': {exc}") from exc
