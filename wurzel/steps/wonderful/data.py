# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Data contracts for the Wonderful RAG connector step."""

from dataclasses import dataclass

import pandera as pa
from pandera.typing import Series

from wurzel.datacontract import PanderaDataFrameModel


@dataclass
class FileUploadInfo:
    """Information about an uploaded file result."""

    file_id: str | None
    status: str
    error: str | None


class WonderfulRAGResult(PanderaDataFrameModel):
    """Result schema for documents pushed to the Wonderful RAG knowledge base.

    Attributes:
        file_id: The file ID assigned by Wonderful (None if upload failed).
        url: The original URL/identifier of the document.
        filename: The filename used when uploading to the knowledge base.
        content: The content that was pushed (truncated for display).
        status: Status of the upload operation ("success" or "failed").
        error: Error message if the upload failed, None otherwise.
    """

    file_id: Series[str] = pa.Field(nullable=True)
    url: Series[str] = pa.Field()
    filename: Series[str] = pa.Field()
    content: Series[str] = pa.Field()
    status: Series[str] = pa.Field(isin=["success", "failed"])
    error: Series[str] = pa.Field(nullable=True)
