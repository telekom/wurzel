# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json
from typing import Optional

from pydantic import Field, validator
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
        APIKEY (Optional[str]): The API key for authentication, default is an empty string.
        REPLICATION_FACTOR (int): The replication factor for the database, default is 3, must be greater than 0.
        BATCH_SIZE (int): The batch size for operations, default is 1024, must be greater than 0.

    Methods:
        parse_json(v):
            Validates and parses JSON strings into Python objects for SEARCH_PARAMS and INDEX_PARAMS.

    Args:
                v (Union[str, dict]): The input value, either a JSON string or a dictionary.

    Returns:
                dict: The parsed dictionary if the input is a JSON string, otherwise the input value.

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
    APIKEY: Optional[str] = ""
    REPLICATION_FACTOR: int = Field(default=3, gt=0)
    BATCH_SIZE: int = Field(default=1024, gt=0)

    @validator("SEARCH_PARAMS", "INDEX_PARAMS", pre=True)
    @classmethod
    def parse_json(cls, v):
        """Validation for json."""
        if isinstance(v, str):
            return json.loads(v)
        return v
