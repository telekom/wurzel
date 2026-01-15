# SPDX-FileCopyrightText: 2025
#
# SPDX-License-Identifier: Apache-2.0

"""Data contracts for the Decagon Knowledge Base connector step."""

from dataclasses import dataclass

import pandera as pa
from pandera.typing import Series


@dataclass
class ChunkResultInfo:
    """Information about a processed chunk result."""

    chunk_idx: int
    total: int
    article_id: int | None
    status: str
    error: str | None


class DecagonArticleResult(pa.DataFrameModel):
    """Result schema for articles pushed to Decagon Knowledge Base.

    This data contract represents the output of the DecagonKnowledgeBaseStep,
    containing information about each article that was processed.

    Attributes:
        article_id: The ID assigned by Decagon (None for bulk sync).
        url: The original URL/identifier of the document.
        content: The content that was pushed (truncated for display).
        source: The source label applied to the article.
        tags: Keywords/tags associated with the article.
        status: Status of the push operation ("success" or "failed").
        error: Error message if the push failed, None otherwise.
        metadata: Additional metadata from the source document.
    """

    article_id: Series[int] = pa.Field(nullable=True)
    url: Series[str] = pa.Field()
    content: Series[str] = pa.Field()
    source: Series[str] = pa.Field()
    tags: Series[object] = pa.Field()  # List[str]
    status: Series[str] = pa.Field(isin=["success", "failed"])
    error: Series[str] = pa.Field(nullable=True)
    metadata: Series[object] = pa.Field(nullable=True)  # Optional dict
