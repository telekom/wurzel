# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""containing the DVCStep sending embedding data into milvus."""

from logging import getLogger

import pandas as pd
from pandera.typing import DataFrame
from pymilvus import CollectionSchema, DataType, FieldSchema
from pymilvus.exceptions import MilvusException
from pymilvus.milvus_client import MilvusClient
from pymilvus.milvus_client.index import IndexParams

from wurzel.exceptions import NoPreviousCollection, StepFailed
from wurzel.step import TypedStep
from wurzel.steps.embedding.data import EmbeddingResult

from .data import Result as MilvusResult
from .settings import MilvusSettings

log = getLogger(__name__)


class MilvusConnectorStep(TypedStep[MilvusSettings, DataFrame[EmbeddingResult], MilvusResult]):  # pragma: no cover
    """Milvus connector step. It consumes embedding csv files, creates a new schema and inserts the embeddings."""

    milvus_timeout: float = 20.0

    def __init__(self) -> None:
        super().__init__()
        # milvus stuff passed as environment
        # because we need to enject them into the DVC step during runtime,
        # not during DVC pipeline definition time
        uri = f"http://{self.settings.HOST}:{self.settings.PORT}"
        if not self.settings.PASSWORD or not self.settings.USER:
            log.warning("MILVUS_HOST, MILVUS_USER or MILVUS_PASSWORD for Milvus not provided. Thus running in non-credential Mode")
        self.client: MilvusClient = MilvusClient(
            uri=uri,
            user=self.settings.USER,
            password=self.settings.PASSWORD,
            timeout=self.milvus_timeout,
        )
        self.collection_index: IndexParams = IndexParams(**self.settings.INDEX_PARAMS)
        self.collection_history_len = self.settings.COLLECTION_HISTORY_LEN

        self.collection_prefix = self.settings.COLLECTION

    def __del__(self):
        if getattr(self, "client", None):
            self.client.close()

    def run(self, inpt: DataFrame[EmbeddingResult]) -> MilvusResult:
        self._insert_embeddings(inpt)
        try:
            old = self.__construct_last_collection_name()
        except NoPreviousCollection:
            old = ""
        self._retire_collection()
        return MilvusResult(new=self.__construct_current_collection_name(), old=old)

    def _insert_embeddings(self, data: pd.DataFrame):
        collection_name = self.__construct_next_collection_name()
        log.info(f"Creating milvus collection {collection_name}")
        collection_schema = CollectionSchema(
            fields=[
                FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=3000),
                FieldSchema(
                    name="vector",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=len(data["vector"].loc[0]),
                ),
                FieldSchema(name="url", dtype=DataType.VARCHAR, max_length=300),
            ],
            description="Collection for storing Milvus embeddings",
        )

        log.info("schema created")
        self.client.create_collection(collection_name=collection_name, schema=collection_schema)
        log.info("collection created")
        log.info(f"Inserting embedding {len(data)} into collection {collection_name}")
        result: dict = self.client.insert(collection_name=collection_name, data=data.to_dict("records"))
        if result["insert_count"] != len(data):
            raise StepFailed(
                f"Failed to insert df into collection '{collection_name}'.{result['insert_count']}/{len(data)} where successful"
            )
        log.info(f"Successfully inserted {len(data)} vectors into collection '{collection_name}'")
        self.client.create_index(collection_name=collection_name, index_params=self.collection_index)
        log.info(f"Successfully craeted index {self.collection_index} into collection '{collection_name}")
        self.client.load_collection(collection_name)
        log.info(f"Successfully loaded the collection {collection_name}' into collection '{collection_name}'")
        try:
            self.client.release_collection(self.__construct_last_collection_name())
        except NoPreviousCollection:
            pass
        self._update_alias(collection_name)

    def _retire_collection(self):
        collections_versioned: dict[int, str] = self._get_collection_versions()
        to_delete = sorted(collections_versioned.keys())[: -self.collection_history_len]
        if not to_delete:
            return

        for col_v in to_delete:
            col = collections_versioned[col_v]
            log.info(f"deleting {col} collection caused by retirement")
            self.client.drop_collection(col, timeout=self.milvus_timeout)

    def _update_alias(self, collection_name):
        try:
            self.client.create_alias(
                collection_name=collection_name,
                alias=self.collection_prefix,
                timeout=self.milvus_timeout,
            )
        except MilvusException:
            self.client.alter_alias(
                collection_name=collection_name,
                alias=self.collection_prefix,
                timeout=self.milvus_timeout,
            )

    def __construct_next_collection_name(self) -> str:
        previous_collections = self._get_collection_versions()
        if not previous_collections:
            return f"{self.collection_prefix}_v1"
        previous_version = max(previous_collections.keys())
        log.info(f"Found version v{previous_version}")
        return f"{self.collection_prefix}_v{previous_version + 1}"

    def __construct_last_collection_name(self) -> str:
        previous_collections = self._get_collection_versions()
        if not previous_collections or len(previous_collections) <= 1:
            raise NoPreviousCollection(f"Milvus does not contain a previous collection for {self.collection_prefix}")
        previous_version = sorted(previous_collections.keys())[-2]
        log.info(f"Found previous version v{previous_version}")
        return f"{self.collection_prefix}_v{previous_version}"

    def __construct_current_collection_name(self) -> str:
        previous_collections = self._get_collection_versions()
        if not previous_collections or len(previous_collections) < 1:
            raise NoPreviousCollection(f"Milvus does not contain a previous collection for {self.collection_prefix}")
        previous_version = sorted(previous_collections.keys())[-1]
        log.info(f"Found previous version v{previous_version}")
        return f"{self.collection_prefix}_v{previous_version}"

    def _get_collection_versions(self) -> dict[int, str]:
        previous_collections = self.client.list_collections(timeout=self.milvus_timeout)
        versioned_collections = {
            int(previous.split("_v")[-1]): previous for previous in previous_collections if self.collection_prefix in previous
        }
        return versioned_collections
