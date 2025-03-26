# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""containing the DVCStep sending embedding data into Qdrant"""

# pylint: disable=duplicate-code
import itertools
from logging import getLogger

from pandera.typing import DataFrame
from qdrant_client import QdrantClient, models

from wurzel.exceptions import CustomQdrantException, StepFailed
from wurzel.step import TypedStep, step_history
from wurzel.steps.embedding.data import EmbeddingResult

from .data import QdrantResult
from .settings import QdrantSettings

log = getLogger(__name__)


def _batch(iterable, size):
    it = iter(iterable)
    while item := list(itertools.islice(it, size)):
        yield item


class QdrantConnectorStep(
    TypedStep[QdrantSettings, DataFrame[EmbeddingResult], DataFrame[QdrantResult]]
):
    """
    Qdrant connector step. It consumes embedding csv files, creates a new schema and inserts the embeddings
    """

    _timeout: int = 20
    s: QdrantSettings
    client: QdrantClient
    collection_name: str

    def __init__(self) -> None:
        super().__init__()
        # Qdrant stuff passed as environment
        # because we need to enject them into the DVC step during runtime,
        # not during DVC pipeline definition time
        # uri = ":memory:"
        log.info(f"connecting to {self.settings.URI}")
        if not self.settings.APIKEY:
            log.warning(
                "QDRANT__APIKEY for Qdrant not provided."
                " Thus running in non-credential Mode"
            )
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

    def run(self, inpt: DataFrame[EmbeddingResult]) -> DataFrame[QdrantResult]:
        if not self.client.collection_exists(self.collection_name):
            self._create_collection(len(inpt["vector"].loc[0]))
        df_result = self._insert_embeddings(inpt)
        return df_result

    def _create_collection(self, size: int):
        log.debug(f"Creating Qdrant collection {self.collection_name}")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=size, distance=self.settings.DISTANCE
            ),
            replication_factor=self.settings.REPLICATION_FACTOR,
        )

    def _insert_embeddings(self, data: DataFrame[EmbeddingResult]):
        log.info(
            "Inserting embeddings",
            extra={"count": len(data), "collection": self.collection_name},
        )
        points = [
            models.PointStruct(
                id=next(self.id_iter),  # type: ignore[arg-type] # No MultiIndex, so always int.
                vector=row["vector"],
                payload={
                    "url": row["url"],
                    "text": row["text"],
                    "keywords": row["keywords"],
                    "history": str(step_history.get()),
                },
            )
            for _, row in data.iterrows()
        ]
        for point_chunk in _batch(points, self.settings.BATCH_SIZE):
            operation_info = self.client.upsert(
                collection_name=self.collection_name, wait=True, points=point_chunk
            )
            if operation_info.status != "completed":
                raise StepFailed(
                    f"Failed to insert df chunk into collection '{self.collection_name}' {operation_info}"
                )
            log.info(
                "Successfully inserted vector_chunk",
                extra={"collection": self.collection_name, "count": len(point_chunk)},
            )
        data = [
            {
                "text": entry.payload["text"],
                "url": entry.payload["url"],
                "vector": entry.vector,
                "history": entry.payload["history"],
                "keywords": entry.payload["keywords"],
                "collection": self.collection_name,
                "id": entry.id,
            }
            for entry in points
        ]
        result = DataFrame[QdrantResult](data)
        return result

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
            field_schema=models.TextIndexParams(
                type=models.TextIndexType.TEXT, tokenizer=models.TokenizerType.WORD
            ),
        )

    def _retire_collections(self):
        collections_versioned: dict[int, str] = self._get_collection_versions()
        to_delete = list(collections_versioned.keys())[
            : -self.settings.COLLECTION_HISTORY_LEN
        ]
        if not to_delete:
            return

        for col_v in to_delete:
            col = collections_versioned[col_v]
            log.info(f"deleting {col} collection caused by retirement")
            self.client.delete_collection(col)

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
