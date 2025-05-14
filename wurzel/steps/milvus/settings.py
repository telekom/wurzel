# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json

from pydantic import Field, validator

from wurzel.step.settings import Settings


# pylint: disable=duplicate-code
class MilvusSettings(Settings):
    """MilvusSettings is a configuration class for managing settings related to MilvusDB.

    Attributes:
        HOST (str): The hostname or IP address of the Milvus server. Defaults to "localhost".
        PORT (int): The port number for the Milvus server. Must be between 1 and 65535. Defaults to 19530.
        COLLECTION (str): The name of the collection in MilvusDB.
        COLLECTION_HISTORY_LEN (int): The length of the collection history. Defaults to 10.
        SEARCH_PARAMS (dict): Parameters for search operations in MilvusDB. Defaults to {"metric_type": "IP", "params": {}}.
        INDEX_PARAMS (dict): Parameters for indexing operations in MilvusDB. Defaults to {"index_type": "FLAT",
                                "field_name": "vector", "metric_type": "IP", "params": {}}.
        USER (str): The username for authentication with MilvusDB.
        PASSWORD (str): The password for authentication with MilvusDB.
        SECURED (bool): Indicates whether the connection to MilvusDB is secured. Defaults to False.

    Methods:
        parse_json(cls, v): Validates and parses JSON strings into Python objects for SEARCH_PARAMS and INDEX_PARAMS.

    Args:
                v (str or dict): The value to validate and parse.

    Returns:
                dict: The parsed dictionary if the input is a JSON string, or the original value if it is already a dictionary.

    """

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
        """Validation for json."""
        if isinstance(v, str):
            return json.loads(v)
        return v
