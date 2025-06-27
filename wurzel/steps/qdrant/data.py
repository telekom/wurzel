# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from typing import Optional

from pandera.typing import Series

from wurzel.datacontract.datacontract import PydanticModel
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


# ----------------------------
# Telemetry Models
# ----------------------------


class OptimizationData(PydanticModel):
    """Data Contract Telemetry."""

    last_responded: Optional[str]


class LocalOptimizations(PydanticModel):
    """Data Contract Telemetry."""

    optimizations: Optional[OptimizationData]


class LocalShard(PydanticModel):
    """Data Contract Telemetry."""

    optimizations: Optional[LocalOptimizations]


class RemoteUsage(PydanticModel):
    """Data Contract Telemetry."""

    searches: Optional[OptimizationData]
    updates: Optional[OptimizationData]


class ShardInfo(PydanticModel):
    """Data Contract Telemetry."""

    local: Optional[LocalShard]
    remote: Optional[list[RemoteUsage]]


class CollectionInfo(PydanticModel):
    """Data Contract Telemetry."""

    id: str
    shards: list[ShardInfo]


class TelemetryCollections(PydanticModel):
    """Data Contract Telemetry."""

    collections: list[CollectionInfo]


class TelemetryResult(PydanticModel):
    """Data Contract Telemetry."""

    collections: TelemetryCollections


class TelemetryResponse(PydanticModel):
    """Data Contract Telemetry."""

    result: TelemetryResult
