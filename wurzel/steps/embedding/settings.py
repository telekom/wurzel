# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import re
from pathlib import Path
from typing import Annotated

from pydantic import Field, WrapValidator
from pydantic_core import Url

from wurzel.steps.splitter import SplitterSettings


class EmbeddingSettings(SplitterSettings):
    """EmbeddingSettings is a configuration class for embedding-related settings.

    Attributes:
        API (Url): The API endpoint for embedding operations.
        NORMALIZE (bool): A flag indicating whether to normalize embeddings. Defaults to False.
        BATCH_SIZE (int): The batch size for processing embeddings. Must be greater than 0. Defaults to 100.
        TOKEN_COUNT_MIN (int): The minimum token count for processing. Must be greater than 0. Defaults to 64.
        TOKEN_COUNT_MAX (int): The maximum token count for processing. Must be greater than 1. Defaults to 256.
        TOKEN_COUNT_BUFFER (int): The buffer size for token count. Must be greater than 0. Defaults to 32.
        STEPWORDS_PATH (Path): The file path to the stopwords file. Defaults to "data/german_stopwords_full.txt".
        N_JOBS (int): The number of parallel jobs to use. Must be greater than 0. Defaults to 1.
        PREFIX_MAP (dict[re.Pattern, str]): A mapping of regex patterns to string prefixes.
            This is validated and transformed using the `_wrap_validator_model_mapping` method.

    Methods:
        _wrap_validator_model_mapping(input_dict: dict[str, str], handler):
            A static method to wrap and validate the model mapping. It converts string regex keys
            in the input dictionary to compiled regex patterns and applies a handler function to the result.

    """

    @staticmethod
    def _wrap_validator_model_mapping(input_dict: dict[str, str], handler):
        new_dict = {}
        for regex, prefix in input_dict.items():
            if isinstance(regex, str):
                new_dict[re.compile(regex)] = prefix
            else:
                new_dict.update({regex: prefix})
        return handler(new_dict)

    API: Url
    NORMALIZE: bool = False
    BATCH_SIZE: int = Field(100, gt=0)
    TOKEN_COUNT_MIN: int = Field(64, gt=0)
    TOKEN_COUNT_MAX: int = Field(256, gt=1)
    TOKEN_COUNT_BUFFER: int = Field(32, gt=0)
    STEPWORDS_PATH: Path = Path("data/german_stopwords_full.txt")
    N_JOBS: int = Field(1, gt=0)
    PREFIX_MAP: Annotated[dict[re.Pattern, str], WrapValidator(_wrap_validator_model_mapping)] = Field(
        default={"e5-": "query: ", "DPR|dpr": ""}
    )
    CLEAN_MD_BEFORE_EMBEDDING: bool = True
