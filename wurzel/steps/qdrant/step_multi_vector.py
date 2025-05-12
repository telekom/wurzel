# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""containing the DVCStep sending embedding data into Qdrant."""

# pylint: disable=duplicate-code
import itertools
from logging import getLogger

from pandera.typing import DataFrame
from qdrant_client import models

from wurzel.exceptions import StepFailed
from wurzel.step import TypedStep
from wurzel.steps.embedding.data import EmbeddingMultiVectorResult
from wurzel.steps.qdrant.step import QdrantConnectorStep

from .data import QdranttMultiVectorResult
from .settings import QdrantSettings

log = getLogger(__name__)


def _batch(iterable, size):
    it = iter(iterable)
    while item := list(itertools.islice(it, size)):
        yield item


class QdrantConnectorMultiVectorStep(
    QdrantConnectorStep,
    TypedStep[
        QdrantSettings,
        DataFrame[EmbeddingMultiVectorResult],
        DataFrame[QdranttMultiVectorResult],
    ],
):
    """Qdrant connector step. It consumes embedding csv files, creates a new schema and inserts the embeddings."""

    def _create_collection(self, size: int):
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=size,
                distance=self.settings.DISTANCE,
                multivector_config=models.MultiVectorConfig(comparator=models.MultiVectorComparator.MAX_SIM),
            ),
            replication_factor=self.settings.REPLICATION_FACTOR,
        )

    def run(self, inpt: DataFrame[EmbeddingMultiVectorResult]) -> DataFrame[QdranttMultiVectorResult]:
        if not self.client.collection_exists(self.collection_name):
            self._create_collection(len(inpt["vectors"].loc[0][0]))
        df_result = self._insert_embeddings(inpt)
        return df_result

    def _insert_embeddings(self, data: DataFrame[EmbeddingMultiVectorResult]) -> DataFrame[QdranttMultiVectorResult]:
        log.debug(f"Creating Qdrant collection {self.collection_name}")

        log.info(
            "Inserting embeddings",
            extra={"count": len(data), "collection": self.collection_name},
        )
        points = [
            models.PointStruct(
                id=next(self.id_iter),  # type: ignore[arg-type] # No MultiIndex, so always int.
                vector=row["vectors"],
                payload={
                    "url": row["url"],
                    "text": row["text"],
                    **self.get_available_hashes(row["text"]),
                    "splits": row["splits"],
                    "keywords": row["keywords"],
                },
            )
            for i, row in data.iterrows()
        ]
        for point_chunk in _batch(points, self.settings.BATCH_SIZE):
            operation_info = self.client.upsert(collection_name=self.collection_name, wait=True, points=point_chunk)
            if operation_info.status != "completed":
                raise StepFailed(f"Failed to insert df chunk into collection '{self.collection_name}' {operation_info}")
            log.info(
                "Successfully inserted vector_chunk",
                extra={"collection": self.collection_name, "count": len(point_chunk)},
            )
        self._create_indices()
        self._update_alias()
        data = [
            {
                **entry.payload,
                "vectors": entry.vector,
                "collection": self.collection_name,
                "id": entry.id,
            }
            for entry in points
        ]
        result = DataFrame[QdranttMultiVectorResult](data)
        return result
