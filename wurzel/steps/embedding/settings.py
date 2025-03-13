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
    """Anything Embedding-related"""

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
    PREFIX_MAP: Annotated[
        dict[re.Pattern, str], WrapValidator(_wrap_validator_model_mapping)
    ] = Field(default={"e5-": "query : ", "DPR|dpr": ""})
