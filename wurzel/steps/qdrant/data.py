# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from typing import Optional

from pandera.typing import Series

from wurzel.steps.embedding.data import EmbeddingMultiVectorResult, EmbeddingResult


class QdrantResult(EmbeddingResult):
    """Data Contract Proxy adding collection name to the PanderaDataframe."""

    text_tlsh_hash: Optional[Series[str]]
    collection: Series[str]
    id: Series[int]


class QdrantMultiVectorResult(EmbeddingMultiVectorResult):
    """Data Contract Proxy adding collection name to the PanderaDataframe."""

    text_tlsh_hash: Optional[Series[str]]
    collection: Series[str]
    id: Series[int]
