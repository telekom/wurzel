# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from typing import Optional

import json

from pydantic import Field, validator
from qdrant_client.models import Distance
from wurzel.step.settings import StepSettings


# pylint: disable=duplicate-code
class QdrantSettings(StepSettings):
    """All Settings related to Qdrant DB"""

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
        """validation for json"""
        if isinstance(v, str):
            return json.loads(v)
        return v
