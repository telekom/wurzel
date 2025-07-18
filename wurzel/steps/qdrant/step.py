# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""containing the DVCStep sending embedding data into Qdrant."""

# pylint: disable=duplicate-code
import itertools
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from logging import getLogger
from typing import Optional

import requests
from dateutil.parser import isoparse
from pandera.typing import DataFrame
from qdrant_client import QdrantClient, models
from qdrant_client.http.models.models import CollectionTelemetry, InlineResponse2002

from wurzel.exceptions import CustomQdrantException, StepFailed
from wurzel.step import TypedStep, step_history
from wurzel.steps.embedding.data import EmbeddingResult
from wurzel.utils import HAS_TLSH

from .data import QdrantResult
from .settings import QdrantSettings

log = getLogger(__name__)


def _batch(iterable, size):
    it = iter(iterable)
    while item := list(itertools.islice(it, size)):
        yield item


class QdrantConnectorStep(TypedStep[QdrantSettings, DataFrame[EmbeddingResult], DataFrame[QdrantResult]]):
    """Qdrant connector step. It consumes embedding csv files, creates a new schema and inserts the embeddings."""

    _timeout: int = 20
    s: QdrantSettings
    client: QdrantClient
    collection_name: str
    result_class = QdrantResult
    vector_key = "vector"

    def __init__(self) -> None:
        super().__init__()
        # Qdrant stuff passed as environment
        # because we need to enject them into the DVC step during runtime,
        # not during DVC pipeline definition time
        # uri = ":memory:"
        log.info(f"connecting to {self.settings.URI}")
        if not self.settings.APIKEY:
            log.warning("QDRANT__APIKEY for Qdrant not provided. Thus running in non-credential Mode")
        self.client = QdrantClient(
            location=self.settings.URI,
            api_key=self.settings.APIKEY,
            timeout=self._timeout,
        )
        self.collection_name = self.__construct_next_collection_name()
        self.id_iter = self.__id_gen()

    def __del__(self):
        if getattr(self, "client", None):
            self.client.close()

    def finalize(self) -> None:
        self._create_indices()
        self._update_alias()
        self._retire_collections()
        return super().finalize()

    def __id_gen(self):
        i = 0
        while True:
            i += 1
            yield i

    def _get_telemetry(self, details_level: int) -> InlineResponse2002:
        """Get Qdrant Collection Telemetry."""
        url = f"{self.settings.URI}/telemetry?details_level={details_level}"
        headers = {"api-key": self.settings.APIKEY}
        try:
            response = requests.get(url, headers=headers, timeout=self.settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            data = InlineResponse2002(**response.json())
            return data
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch telemetry from Qdrant: {e}") from e

    def run(self, inpt: DataFrame[EmbeddingResult]) -> DataFrame[QdrantResult]:
        if not self.client.collection_exists(self.collection_name):
            self._create_collection(len(inpt["vector"].loc[0]))
        df_result = self._insert_embeddings(inpt)
        return df_result

    def _create_collection(self, size: int):
        log.debug(f"Creating Qdrant collection {self.collection_name}")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(size=size, distance=self.settings.DISTANCE),
            replication_factor=self.settings.REPLICATION_FACTOR,
        )

    def _get_entry_payload(self, row: dict[str, object]) -> dict[str, object]:
        """Create the payload for the entry."""
        payload = {
            "url": row["url"],
            "text": row["text"],
            **self.get_available_hashes(row["text"]),
            "keywords": row["keywords"],
            "history": str(step_history.get()),
        }
        return payload

    def _create_point(self, row: dict) -> models.PointStruct:
        """Creates a Qdrant PointStruct object from a given row dictionary.

        Args:
            row (dict): A dictionary representing a data entry, expected to contain at least the vector data under `self.vector_key`.

        Returns:
            models.PointStruct: An instance of PointStruct with a unique id, vector, and payload extracted from the row.

        Raises:
            KeyError: If the required vector key is not present in the row.

        """
        payload = self._get_entry_payload(row)

        return models.PointStruct(
            id=next(self.id_iter),  # type: ignore[arg-type]
            vector=row[self.vector_key],
            payload=payload,
        )

    def _upsert_points(self, points: list[models.PointStruct]):
        """Inserts a list of points into the Qdrant collection in batches.

        Args:
            points (list[models.PointStruct]): The list of point structures to upsert into the collection.

        Raises:
            StepFailed: If any batch fails to be inserted into the collection.

        Logs:
            Logs a message for each successfully inserted batch, including the collection name and number of points.

        """
        for point_chunk in _batch(points, self.settings.BATCH_SIZE):
            operation_info = self.client.upsert(
                collection_name=self.collection_name,
                wait=True,
                points=point_chunk,
            )
            if operation_info.status != "completed":
                raise StepFailed(f"Failed to insert df chunk into collection '{self.collection_name}' {operation_info}")
            log.info(
                "Successfully inserted vector_chunk",
                extra={"collection": self.collection_name, "count": len(point_chunk)},
            )

    def _build_result_dataframe(self, points: list[models.PointStruct]):
        """Constructs a DataFrame from a list of PointStruct objects.

        Each PointStruct's payload is unpacked into the resulting dictionary, along with its vector, collection name, and ID.
        The resulting list of dictionaries is used to create a DataFrame of the specified result_class.

        Args:
            points (list[models.PointStruct]): A list of PointStruct objects containing payload, vector, and id information.

        """
        result_data = [
            {
                **entry.payload,
                self.vector_key: entry.vector,
                "collection": self.collection_name,
                "id": entry.id,
            }
            for entry in points
        ]
        return DataFrame[self.result_class](result_data)

    def _insert_embeddings(self, data: DataFrame[EmbeddingResult]):
        log.info("Inserting embeddings", extra={"count": len(data), "collection": self.collection_name})

        points = [self._create_point(row) for _, row in data.iterrows()]

        self._upsert_points(points)

        return self._build_result_dataframe(points)

    def _create_indices(self):
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="keywords",
            field_schema=models.TextIndexParams(
                type=models.TextIndexType.TEXT,
                tokenizer=models.TokenizerType.WHITESPACE,
            ),
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="url",
            field_schema=models.TextIndexParams(
                type=models.TextIndexType.TEXT,
                tokenizer=models.TokenizerType.PREFIX,
                min_token_len=3,
            ),
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="text",
            field_schema=models.TextIndexParams(
                type=models.TextIndexType.TEXT,
                tokenizer=models.TokenizerType.MULTILINGUAL,
            ),
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="history",
            field_schema=models.TextIndexParams(type=models.TextIndexType.TEXT, tokenizer=models.TokenizerType.WORD),
        )

    def _retire_collections(self) -> None:
        """Retire (delete) historical Qdrant collections that.
        * Are older than the configured history length, AND
        * Are not currently targeted by an alias, AND
        * Have not been recently used (per telemetry).
        """
        collections_versioned: dict[int, str] = self._get_collection_versions()
        if not collections_versioned:
            return

        latest_version = max(collections_versioned)
        retirement_threshold = latest_version - self.settings.COLLECTION_HISTORY_LEN

        alias_pointed = {alias.collection_name for alias in self.client.get_aliases().aliases}
        telemetry_collections = (
            self._get_telemetry(details_level=self.settings.TELEMETRY_DETAILS_LEVEL).result.collections.collections  # pylint: disable=no-member
        )

        for version, collection_name in collections_versioned.items():
            if version > retirement_threshold:
                continue

            if self._should_skip_collection(collection_name, alias_pointed, telemetry_collections):
                continue

            log.info("Deleting retired collection", extra={"collection": collection_name})
            self.client.delete_collection(collection_name)

    def _should_skip_collection(self, name: str, alias_pointed: set[str], telemetry_collections: list) -> bool:
        """Check if a collection should not be deleted."""
        if name in alias_pointed:
            log.warning("Skipping deletion: still aliased", extra={"collection": name})
            return True

        usage_info = next((col for col in telemetry_collections if col.id == name), None)
        if usage_info and self._was_recently_used_via_shards(usage_info):
            log.warning("Skipping deletion: recently accessed", extra={"collection": name})
            return True

        return False

    def _was_recently_used_via_shards(self, collection_info: CollectionTelemetry) -> bool:
        threshold = datetime.now(timezone.utc) - timedelta(days=self.settings.COLLECTION_USAGE_RETENTION_DAYS)
        latest_usage = self._get_latest_usage_timestamp(collection_info)
        return latest_usage is not None and latest_usage > threshold

    def _get_latest_usage_timestamp(self, collection_info: CollectionTelemetry) -> Optional[datetime]:
        timestamps = []

        for shard in collection_info.shards:
            timestamps.append(self._parse_local_timestamp(shard))
            timestamps.extend(self._parse_remote_timestamps(shard))

        return max(filter(None, timestamps), default=None)

    def _parse_local_timestamp(self, shard) -> Optional[datetime]:
        try:
            ts = shard.local.optimizations.optimizations.last_responded
            return self._safe_parse_iso(ts)
        except AttributeError:
            return None

    def _parse_remote_timestamps(self, shard) -> list[datetime]:
        return [
            self._safe_parse_iso(remote.searches.last_responded)
            for remote in (shard.remote or [])
            if self._safe_parse_iso(remote.searches.last_responded) is not None
        ]

    def _safe_parse_iso(self, timestamp: Optional[str]) -> Optional[datetime]:
        try:
            return isoparse(timestamp) if timestamp else None
        except (ValueError, TypeError):
            return None

    def _update_alias(self):
        success = self.client.update_collection_aliases(
            change_aliases_operations=[
                models.CreateAliasOperation(
                    create_alias=models.CreateAlias(
                        collection_name=self.collection_name,
                        alias_name=self.settings.COLLECTION,
                    )
                )
            ]
        )
        if not success:
            raise CustomQdrantException("Alias Update failed")

    def __construct_next_collection_name(self) -> str:
        previous_collections = self._get_collection_versions()
        if not previous_collections:
            return f"{self.settings.COLLECTION}_v1"
        previous_version = max(previous_collections.keys())
        log.info(f"Found version v{previous_version}")
        return f"{self.settings.COLLECTION}_v{previous_version + 1}"

    def _get_collection_versions(self) -> dict[int, str]:
        previous_collections = self.client.get_collections().collections
        versioned_collections = {
            int(previous.name.split("_v")[-1]): previous.name
            for previous in previous_collections
            if f"{self.settings.COLLECTION}_v" in previous.name
        }
        return dict(sorted(versioned_collections.items()))

    @staticmethod
    def get_available_hashes(text: str, encoding: str = "utf-8") -> dict:
        """Compute `n` hashes for a given input text based.
        The number `n` depends on the optionally installed python libs.
        For now only TLSH (Trend Micro Locality Sensitive Hash) is supported
        ## TLSH
        Given a byte stream with a minimum length of 50 bytes TLSH generates a hash value which can be used for similarity comparisons.

        Args:
            text (str): Input text
            encoding (str, optional): Input text will encoded to bytes using this encoding. Defaults to "utf-8".

        Returns:
            dict[str, str]: keys: `text_<algo>_hash` hash as string ! Dict might be empty!

        """
        hashes = {}
        encoded_text = text.encode(encoding)
        if HAS_TLSH:
            # pylint: disable=no-name-in-module, import-outside-toplevel
            from tlsh import hash as tlsh_hash

            hashes["text_tlsh_hash"] = tlsh_hash(encoded_text)
        hashes["text_sha256_hash"] = sha256(encoded_text).hexdigest()
        return hashes
