# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Minimal Pydantic models for the Qdrant /telemetry API response.

Only the fields relevant to the collection retirement logic are modelled.
All other fields in the actual response are silently ignored via extra="ignore".

Relevant path:
  result.collections.collections[]
    .id                                              -- collection name
    .shards[].local.optimizations.optimizations.last_responded
    .shards[].remote[].searches.last_responded
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class _IgnoreExtra(BaseModel):
    """Base model that silently discards any extra fields from the API response."""

    model_config = ConfigDict(extra="ignore")


class OperationStats(_IgnoreExtra):
    """Timing statistics for a single Qdrant operation type."""

    last_responded: Optional[datetime] = None


class OptimizerTelemetry(_IgnoreExtra):
    """Telemetry for the optimizer process running on a local shard."""

    optimizations: Optional[OperationStats] = None


class LocalShardTelemetry(_IgnoreExtra):
    """Telemetry data for a locally held shard replica."""

    optimizations: Optional[OptimizerTelemetry] = None


class RemoteShardTelemetry(_IgnoreExtra):
    """Telemetry data for a remotely held shard replica."""

    searches: Optional[OperationStats] = None


class ReplicaSetTelemetry(_IgnoreExtra):
    """Telemetry for one shard's full replica set (local + remote peers)."""

    local: Optional[LocalShardTelemetry] = None
    remote: list[RemoteShardTelemetry] = []


class CollectionTelemetry(_IgnoreExtra):
    """Telemetry entry for a single Qdrant collection."""

    id: str
    shards: Optional[list[ReplicaSetTelemetry]] = None


class CollectionsTelemetry(_IgnoreExtra):
    """Container for the list of per-collection telemetry entries."""

    collections: Optional[list[CollectionTelemetry]] = None


class TelemetryResult(_IgnoreExtra):
    """The ``result`` object returned by the Qdrant ``/telemetry`` endpoint."""

    collections: CollectionsTelemetry


class TelemetryResponse(_IgnoreExtra):
    """Top-level wrapper for the Qdrant ``/telemetry`` JSON response."""

    result: TelemetryResult
