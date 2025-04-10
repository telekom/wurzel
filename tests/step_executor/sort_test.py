# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
import pandas
import pytest
from pandera.typing import DataFrame

from wurzel.datacontract.common import MarkdownDataContract
from wurzel.datacontract.datacontract import PydanticModel
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
    sorted_inpt: pandas.DataFrame | PydanticModel | list[PydanticModel] = _try_sort(inpt)
    if isinstance(inpt, pandas.DataFrame):
        assert sorted_inpt.equals(inpt)
    else:
        assert sorted_inpt == inpt


def test_unsorted_mdcs():
    expected = [
        MarkdownDataContract(md="b", keywords="kw", url="ur"),
        MarkdownDataContract(md="a", keywords="kw", url="ur"),
    ]
    inpt = reversed(expected)
    assert _try_sort(list(inpt)) == expected


def test_unsorted_df():
    unsorted = DataFrame[EmbeddingResult](
        [
            {"text": "b", "url": "url", "vector": [0.1], "keywords": "kw"},
            {"text": "a", "url": "url", "vector": [0.1], "keywords": "kw"},
        ]
    )
    sort = DataFrame[EmbeddingResult](
        [
            {"text": "a", "url": "url", "vector": [0.1], "keywords": "kw"},
            {"text": "b", "url": "url", "vector": [0.1], "keywords": "kw"},
        ]
    )
    assert not sort.equals(unsorted), "sanity check"
    assert sort.reset_index(drop=True).equals(
        _try_sort(unsorted).reset_index(drop=True)
    )
