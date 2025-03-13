# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json
from pydantic import Field, validator
from wurzel.step.settings import StepSettings


# pylint: disable=duplicate-code
class MilvusSettings(StepSettings):
    """All Settings related to MivusDB"""

    HOST: str = "localhost"
    PORT: int = Field(19530, gt=0, le=65535)
    COLLECTION: str
    COLLECTION_HISTORY_LEN: int = 10
    SEARCH_PARAMS: dict = {"metric_type": "IP", "params": {}}
    INDEX_PARAMS: dict = {
        "index_type": "FLAT",
        "field_name": "vector",
        "metric_type": "IP",
        "params": {},
    }
    USER: str
    PASSWORD: str
    SECURED: bool = False

    @validator("SEARCH_PARAMS", "INDEX_PARAMS", pre=True)
    @classmethod
    # pylint: disable-next=R0801
    def parse_json(cls, v):
        """validation for json"""
        if isinstance(v, str):
            return json.loads(v)
        return v
