# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json

from pydantic import Field, SecretStr, field_validator
from qdrant_client.models import Distance

from wurzel.step.settings import Settings


# pylint: disable=duplicate-code
class QdrantSettings(Settings):
    """QdrantSettings is a configuration class for managing settings related to the Qdrant database.

    Attributes:
        DISTANCE (Distance): The distance metric to be used, default is Distance.DOT.
        URI (str): The URI for the Qdrant database, default is "http://localhost:6333".
        COLLECTION (str): The name of the collection in the Qdrant database.
        COLLECTION_HISTORY_LEN (int): The length of the collection history, default is 10.
        SEARCH_PARAMS (dict): Parameters for search operations, default is {"metric_type": "IP", "params": {}}.
        INDEX_PARAMS (dict): Parameters for index creation, default includes "index_type", "field_name", "distance", and "params".
        APIKEY (SecretStr): The API key for authentication, default is an empty SecretStr.
        REPLICATION_FACTOR (int): The replication factor for the database, default is 3, must be greater than 0.
        BATCH_SIZE (int): The batch size for operations, default is 1024, must be greater than 0.

    Methods:
        parse_json(v):
            Validates and parses JSON strings into Python objects for SEARCH_PARAMS and INDEX_PARAMS.
    """

    DISTANCE: Distance = Distance.DOT
    URI: str = "http://localhost:6333"
    COLLECTION: str
    COLLECTION_HISTORY_LEN: int = 10
    SEARCH_PARAMS: dict = {"metric_type": "IP", "params": {}}
    INDEX_PARAMS: dict = {
        "index_type": "FLAT",
        "field_name": "vector",
        "distance": "Dot",
        "params": {},
    }
    APIKEY: SecretStr = SecretStr("")
    REPLICATION_FACTOR: int = Field(default=3, gt=0, description="Number of replicas for each Qdrant collection.")
    BATCH_SIZE: int = Field(default=1024, gt=0, description="Number of vector points to upsert into Qdrant in a single batch.")
    TELEMETRY_DETAILS_LEVEL: int = Field(
        default=3, description="Level of detail for telemetry data requested from Qdrant. Higher values may include more metrics."
    )
    COLLECTION_USAGE_RETENTION_DAYS: int = Field(default=2, description="Number of days to consider a collection as recently used.")
    REQUEST_TIMEOUT: int = Field(default=20, description="Timeout (in seconds) for requests sent to Qdrant (e.g., telemetry).")
    COLLECTION_RETIRE_DRY_RUN: bool = Field(default=False, description="If True, only log collections to be retired without deleting.")
    ENABLE_COLLECTION_RETIREMENT: bool = Field(default=False, description="Skips retirement of collections, if enable.")

    @field_validator("SEARCH_PARAMS", "INDEX_PARAMS", mode="before")
    @classmethod
    def parse_json(cls, v):
        """Validation for json."""
        if isinstance(v, str):
            return json.loads(v)
        return v
