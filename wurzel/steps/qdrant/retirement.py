# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Handles retirement (deletion) of old versioned Qdrant collections."""

from logging import getLogger

from qdrant_client import QdrantClient

from .settings import QdrantSettings

log = getLogger(__name__)


class CollectionRetirer:
    """Retires (deletes) old versioned Qdrant collections that are no longer needed.

    A collection is retired when it:
    - Is not among the N most recent versions (configurable via COLLECTION_HISTORY_LEN), and
    - Is not currently targeted by any alias.
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

        for version, collection_name in collections_versioned.items():
            if version in versions_to_keep:
                continue
            if collection_name in alias_pointed:
                log.info("Skipping deletion: still aliased", extra={"collection": collection_name})
                continue
            self._retire_or_log(collection_name)

    def _retire_or_log(self, collection_name: str) -> None:
        """Delete the collection unless DRY_RUN is enabled, in which case log the action."""
        if self._settings.COLLECTION_RETIRE_DRY_RUN:
            log.info("[DRY RUN] Would retire collection", extra={"collection": collection_name})
        else:
            log.info("Deleting retired collection", extra={"collection": collection_name})
            self._client.delete_collection(collection_name)
