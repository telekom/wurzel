# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import dataclasses
from typing import Iterable

import pytest

from wurzel.utils.logging import _make_dict_serializable


@dataclasses.dataclass
class SomeDataClass:
    A: str = "Data Object"


class SomeClass:
    a = "an instance"


class AnException(Exception):
    pass


@pytest.mark.parametrize(
    "in_data,expected",
    [
        pytest.param(*i, id=type(i[0]).__name__)
        for i in [
            ("a_string", "a_string"),
            (["a", "list"], ["a", "list"]),
            ({"a": "dict"}, {"a": "dict"}),
            ({"a", "set"}, ["a", "set"]),
            (1, 1),
            (SomeClass(), None),
            (SomeClass, None),
            (AnException("Instance"), "AnException('Instance')"),
            # (SomeDataClass(),  {'A': 'Data Object'}), Todo: fix
            # (MilvusSettings(PASSWORD="123", USER="AA"), {"VECTOR_STORE_TYPE": "milvus", "HOST": "localhost", "PORT": 19530, "COLLECTION": "", "SEARCH_PARAMS": {"metric_type": "IP", "params": {"a": "b"}}, "INDEX_PARAMS": {"index_type": "FLAT", "metric_type": "IP", "params": {}}, "USER": "AA", "PASSWORD": "****", "SECURED": False})
        ]
    ],
)
def test_make_dict_serializable(in_data, expected):
    res = _make_dict_serializable(in_data)
    if expected is not None:
        if isinstance(in_data, Iterable):
            return all(d in res for d in expected)
        assert expected == res
