# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Handles retirement (deletion) of old versioned Qdrant collections."""

from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Optional

import requests
from qdrant_client import QdrantClient

from .settings import QdrantSettings
from .telemetry import CollectionTelemetry, TelemetryResponse

log = getLogger(__name__)


class CollectionRetirer:
    """Retires (deletes) old versioned Qdrant collections that are no longer needed.

    A collection is retired when it:
    - Is not among the N most recent versions (configurable via COLLECTION_HISTORY_LEN),
    - Is not currently targeted by any alias, and
    - Has not been recently accessed (based on telemetry, configurable via COLLECTION_USAGE_RETENTION_DAYS).
    """

    def __init__(self, client: QdrantClient, settings: QdrantSettings) -> None:
        self._client = client
        self._settings = settings

    def retire(self, collections_versioned: dict[int, str]) -> None:
        """Retire old versioned collections that are no longer needed.

        Skipped entirely if ENABLE_COLLECTION_RETIREMENT is False.
        """
        if not self._settings.ENABLE_COLLECTION_RETIREMENT:
            log.info("Skipping Qdrant collection retirement as ENABLE_COLLECTION_RETIREMENT is set.")
            return

        if not collections_versioned:
            return

        sorted_versions = sorted(collections_versioned.keys())
        versions_to_keep = set(sorted_versions[-self._settings.COLLECTION_HISTORY_LEN :])

        alias_pointed = {alias.collection_name for alias in self._client.get_aliases().aliases}
        telemetry_collections = self._get_telemetry(details_level=self._settings.TELEMETRY_DETAILS_LEVEL)

        for version, collection_name in collections_versioned.items():
            if version in versions_to_keep:
                continue
            if self._should_skip_collection(collection_name, alias_pointed, telemetry_collections):
                continue
            self._retire_or_log(collection_name)

    def _get_telemetry(self, details_level: int) -> list[CollectionTelemetry]:
        """Fetch per-collection telemetry data from Qdrant.

        Parses the `/telemetry` response into typed models, returning only the
        per-collection entries used for the collection retirement logic.

        Args:
            details_level (int): Level of detail (higher = more shard stats).

        Returns:
            list[CollectionTelemetry]: Typed collection telemetry entries.
        """
        url = f"{self._settings.URI}/telemetry?details_level={details_level}"
        headers = {"api-key": self._settings.APIKEY.get_secret_value()}
        try:
            response = requests.get(url, headers=headers, timeout=self._settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            parsed = TelemetryResponse.model_validate(response.json())
            return parsed.result.collections.collections or []
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch telemetry from Qdrant: {e}") from e

    def _retire_or_log(self, collection_name: str) -> None:
        """Delete the collection unless DRY_RUN is enabled, in which case log the action."""
        if self._settings.COLLECTION_RETIRE_DRY_RUN:
            log.info("[DRY RUN] Would retire collection", extra={"collection": collection_name})
        else:
            log.info("Deleting retired collection", extra={"collection": collection_name})
            self._client.delete_collection(collection_name)

    def _should_skip_collection(self, name: str, alias_pointed: set[str], telemetry_collections: list[CollectionTelemetry]) -> bool:
        """Return True if the collection should be kept (aliased or recently used)."""
        if name in alias_pointed:
            log.info("Skipping deletion: still aliased", extra={"collection": name})
            return True

        usage_info = next((col for col in telemetry_collections if col.id == name), None)
        if usage_info and self._was_recently_used_via_shards(usage_info):
            log.info("Skipping deletion: recently accessed", extra={"collection": name})
            return True

        return False

    def _was_recently_used_via_shards(self, collection_info: CollectionTelemetry) -> bool:
        """Return True if the collection was accessed within the retention window."""
        threshold = datetime.now(timezone.utc) - timedelta(days=self._settings.COLLECTION_USAGE_RETENTION_DAYS)
        latest_usage = self._get_latest_usage_timestamp(collection_info)
        return latest_usage is not None and latest_usage > threshold

    def _get_latest_usage_timestamp(self, collection_info: CollectionTelemetry) -> Optional[datetime]:
        """Return the most recent usage timestamp across all local and remote shards."""
        timestamps: list[Optional[datetime]] = []

        for shard in collection_info.shards or []:
            if shard.local and shard.local.optimizations and shard.local.optimizations.optimizations:
                timestamps.append(shard.local.optimizations.optimizations.last_responded)
            for remote in shard.remote:
                if remote.searches:
                    timestamps.append(remote.searches.last_responded)

        return max(filter(None, timestamps), default=None)
