# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pandera.typing import Series
from wurzel.steps.embedding.data import EmbeddingResult, EmbeddingMultiVectorResult


class QdrantResult(EmbeddingResult):
    """Data Contract Proxy adding collection name to the PanderaDataframe"""

    collection: Series[str]
    id: Series[int]


class QdranttMultiVectorResult(EmbeddingMultiVectorResult):
    """Data Contract Proxy adding collection name to the PanderaDataframe"""

    collection: Series[str]
    id: Series[int]
