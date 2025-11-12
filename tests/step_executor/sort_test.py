# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
import pandas
import pytest
from pandera.typing import DataFrame

from wurzel.datacontract.common import MarkdownDataContract
from wurzel.datacontract.datacontract import PydanticModel
from wurzel.step_executor.base_executor import _try_sort
from wurzel.steps.data import EmbeddingResult


@pytest.mark.parametrize(
    "inpt",
    [
        pytest.param(MarkdownDataContract(md="md", keywords="kw", url="ur"), id="Single Pyd Obj"),
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
                    {"text": "a", "url": "url", "vector": [0.1], "keywords": "kw", "embedding_input_text": "a"},
                    {"text": "b", "url": "url", "vector": [0.1], "keywords": "kw", "embedding_input_text": "b"},
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


@pytest.mark.parametrize("run_num", range(10))
@pytest.mark.parametrize(
    "expected",
    [
        pytest.param(
            [
                MarkdownDataContract(md="b", keywords="kw", url="ur"),
                MarkdownDataContract(md="a", keywords="kw", url="ur"),
            ],
            id="md-dc",
        ),
        pytest.param([1, 2, 3, 4, 5, 6, 7, 8, 9], id="ints"),
    ],
)
def test_unsorted(run_num, expected):
    inpt = reversed(expected)
    assert _try_sort(list(inpt)) == expected


def test_unsorted_df():
    unsorted = DataFrame[EmbeddingResult](
        [
            {"text": "b", "url": "url", "vector": [0.1], "keywords": "kw", "embedding_input_text": "b"},
            {"text": "a", "url": "url", "vector": [0.1], "keywords": "kw", "embedding_input_text": "a"},
        ]
    )
    sort = DataFrame[EmbeddingResult](
        [
            {"text": "a", "url": "url", "vector": [0.1], "keywords": "kw", "embedding_input_text": "a"},
            {"text": "b", "url": "url", "vector": [0.1], "keywords": "kw", "embedding_input_text": "b"},
        ]
    )
    assert not sort.equals(unsorted), "sanity check"
    assert sort.reset_index(drop=True).equals(_try_sort(unsorted).reset_index(drop=True))


def test_hashing():
    args = {"md": "md", "keywords": "kwds", "url": "urls"}
    expected = hash(MarkdownDataContract(**args))
    for i in range(100):
        assert hash(MarkdownDataContract(**args)) == expected, f"Failed in iteration {i}"
