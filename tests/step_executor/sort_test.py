# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
import pandas
import pytest
from pandera.typing import DataFrame

from wurzel.datacontract.common import MarkdownDataContract
from wurzel.step_executor.base_executor import _try_sort
from wurzel.steps.embedding.data import EmbeddingResult


@pytest.mark.parametrize(
    "inpt",
    [
        pytest.param(
            MarkdownDataContract(md="md", keywords="kw", url="ur"), id="Single Pyd Obj"
        ),
        pytest.param(
            [
                MarkdownDataContract(md="md", keywords="kw", url="ur"),
                MarkdownDataContract(md="md", keywords="kw", url="ur"),
            ],
            id="Multiple Pyd Obj",
        ),
        pytest.param(
            DataFrame[EmbeddingResult](
                [
                    {"text": "a", "url": "url", "vector": [0.1], "keywords": "kw"},
                    {"text": "b", "url": "url", "vector": [0.1], "keywords": "kw"},
                ]
            ),
            id="DataFrame",
        ),
    ],
)
def test_sorted(inpt):
    sorted = _try_sort(inpt)
    if isinstance(inpt, pandas.DataFrame):
        assert sorted.equals(inpt)
    else:
        assert sorted == inpt
