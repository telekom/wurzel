# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest
from pydantic import Field
from pydantic_core import Url

from wurzel.step.settings import SettingsBase, SettingsLeaf


class _InnerLeaf(SettingsLeaf):
    VALUE: str = "default"
    SECONDARY: int = 0


class _NestedBaseLeaf(SettingsBase):
    PREFIX: _InnerLeaf = _InnerLeaf()


class _NNestedBaseBaseLeaf(SettingsBase):
    NEST: _NestedBaseLeaf = _NestedBaseLeaf()


@pytest.mark.parametrize(
    "env_dict,validate",
    [
        pytest.param(
            {"NEST__PREFIX__VALUE": "magic00", "NEST__PREFIX__SECONDARY": "200"},
            lambda: _NNestedBaseBaseLeaf().NEST.PREFIX.model_dump()
            == {"VALUE": "magic00", "SECONDARY": 200},
            id="Nested^2",
        ),
        pytest.param(
            {"PREFIX__VALUE": "magic01", "PREFIX__SECONDARY": "201"},
            lambda: _NestedBaseLeaf().PREFIX.model_dump()
            == {"VALUE": "magic01", "SECONDARY": 201},
            id="Nested",
        ),
        pytest.param(
            {"VALUE": "magic10", "SECONDARY": "210"},
            lambda: _InnerLeaf().model_dump() == {"VALUE": "magic10", "SECONDARY": 210},
            id="Root",
        ),
        pytest.param(
            {"NEST__PREFIX": '{"VALUE":"magic02","SECONDARY": "202"}'},
            lambda: _NNestedBaseBaseLeaf().NEST.PREFIX.model_dump()
            == {"VALUE": "magic02", "SECONDARY": 202},
            id="Nested^2-json1",
        ),
        pytest.param(
            {
                "NEST__PREFIX": '{"VALUE":"magic02","SECONDARY": "202"}',
                "NEST__PREFIX__VALUE": "magic72",
            },
            lambda: _NNestedBaseBaseLeaf().NEST.PREFIX.model_dump()
            == {"VALUE": "magic72", "SECONDARY": 202},
            id="Nested^2-json1_and_override",
        ),
        pytest.param(
            {"NEST": '{"PREFIX":{"VALUE":"magic03","SECONDARY": "203"}}'},
            lambda: _NNestedBaseBaseLeaf().NEST.PREFIX.model_dump()
            == {"VALUE": "magic03", "SECONDARY": 203},
            id="Nested^2-json2",
        ),
        pytest.param(
            {
                "NEST": '{"PREFIX":{"VALUE":"magic03","SECONDARY": "203"}}',
                "NEST__PREFIX__VALUE": "magic73",
            },
            lambda: _NNestedBaseBaseLeaf().NEST.PREFIX.model_dump()
            == {"VALUE": "magic73", "SECONDARY": 203},
            id="Nested^2-json2_and_override",
        ),
        pytest.param(
            {"PREFIX": '{"VALUE":"magic09","SECONDARY": "209"}'},
            lambda: _NestedBaseLeaf().PREFIX.model_dump()
            == {"VALUE": "magic09", "SECONDARY": 209},
            id="Nested-json",
        ),
        pytest.param(
            {
                "PREFIX": '{"VALUE":"magic09","SECONDARY": "209"}',
                "PREFIX__VALUE": "magic79",
            },
            lambda: _NestedBaseLeaf().PREFIX.model_dump()
            == {"VALUE": "magic79", "SECONDARY": 209},
            id="Nested-json_and_override",
        ),
        pytest.param(
            {"NEST__PREFIX": '{"VALUE":"magic04"}', "NEST__PREFIX__SECONDARY": "204"},
            lambda: _NNestedBaseBaseLeaf().NEST.PREFIX.model_dump()
            == {"VALUE": "magic04", "SECONDARY": 204},
            id="Nested^2-json1-correction",
        ),
        pytest.param(
            {
                "NEST": '{"PREFIX":{"VALUE":"magic05"}}',
                "NEST__PREFIX__SECONDARY": "205",
            },
            lambda: _NNestedBaseBaseLeaf().NEST.PREFIX.model_dump()
            == {"VALUE": "magic05", "SECONDARY": 205},
            id="Nested^2-json2-correction",
        ),
        pytest.param(
            {"PREFIX": '{"VALUE":"magic06"}', "PREFIX__SECONDARY": "206"},
            lambda: _NestedBaseLeaf().PREFIX.model_dump()
            == {"VALUE": "magic06", "SECONDARY": 206},
            id="Nested^2-json-correction",
        ),
    ],
)
def test_nested_ok_B_B_L(env, env_dict, validate):
    _NestedBaseLeaf()
    _InnerLeaf()
    _NNestedBaseBaseLeaf()
    env.update(env_dict)
    assert validate()


@pytest.mark.parametrize(
    "env_dict",
    [
        pytest.param({"VALUE": "__"}, id="VALUE"),
    ],
)
def test_nested_at_root(env, env_dict):
    env.update(env_dict)
    assert _NestedBaseLeaf().PREFIX.VALUE == "default"


class _EmbeddingSettings(SettingsLeaf):
    """Anything Embedding-related"""

    API: Url = Url("https://ex/embed")
    NORMALIZE: bool = Field(False)


class _Nested(SettingsBase):
    PREFIX: _EmbeddingSettings = _EmbeddingSettings()


@pytest.mark.mytest
@pytest.mark.parametrize(
    "env_dict,get_embedding_settings",
    [
        pytest.param(
            {"PREFIX__API": "https://de.my.example.com"},
            lambda: _Nested().PREFIX,
            id="Nested",
        ),
        pytest.param(
            {"API": "https://de.my.example.com"},
            lambda: _EmbeddingSettings(),
            id="Root",
        ),
    ],
)
def test_url_valid(env, env_dict, get_embedding_settings):
    env.update(env_dict)
    a = get_embedding_settings()
    assert str(a.API) == "https://de.my.example.com/"
