# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json
from typing import Dict, List, Literal, Tuple, Type, Union

import pytest
from pydantic import Field
from pydantic_core import Url as pyd_c_Url

from wurzel.step.settings import SettingsBase, SettingsLeaf


def test_prefix():
    class A(SettingsLeaf):
        pass

    assert A.with_prefix("pp").model_config["env_prefix"] == "pp"
    assert A.model_config["env_prefix"] != "pp"


@pytest.mark.parametrize("init_method", ["constructor", "environment"])
def test_nest_0(init_method, env):
    class A(SettingsBase):
        ARG: str

    if init_method == "constructor":
        a = A(ARG="A")
        assert a.ARG == "A"
        return
    env.set("ARG", "B")
    assert A().ARG == "B"


@pytest.mark.parametrize("init_method", ["constructor", "environment"])
def test_nest_1(init_method, env):
    class A(SettingsBase):
        ARG: str

    class Parent(SettingsBase):
        ARG: A

    if init_method == "constructor":
        a = Parent(ARG=A(ARG="A"))
        assert a.ARG.ARG == "A"
        a = Parent(ARG={"ARG": "A"})
        assert a.ARG.ARG == "A"
        return
    env.set("ARG__ARG", "B")
    assert Parent().ARG.ARG == "B"


@pytest.mark.parametrize("init_method", ["constructor", "environment"])
@pytest.mark.parametrize("init_dict", [{"1": "Eins"}, {1: "Eins"}])
def test_complex_nest_0(init_method, init_dict, env):
    class A(SettingsBase):
        ARG: Dict[int, str]

    if init_method == "constructor":
        a = A(ARG=init_dict)
    else:
        env.set("ARG", json.dumps(init_dict))
        a = A()
    assert a.ARG[1] == "Eins"


class leaf_field_default(SettingsLeaf):
    A: str = Field("a")


class leaf_field_defaultfactory(SettingsLeaf):
    A: str = Field(default_factory=lambda: "a")


class leaf_cls(SettingsLeaf):
    A: str = "a"


@pytest.mark.parametrize(
    "cls", [leaf_cls, leaf_field_default, leaf_field_defaultfactory]
)
def test_leaf_defaults(cls):
    a = cls()
    assert a.A == "a"


@pytest.mark.parametrize("init_method", ["defaults", "environment"])
@pytest.mark.parametrize(
    "mapping_default",
    [
        pytest.param(Field, id="Field_default"),
        pytest.param(
            lambda x: Field(default_factory=lambda: x), id="Field_defaultfactory"
        ),
        pytest.param(lambda x: x, id="Class"),
    ],
)
def test_nested_mapping(init_method, mapping_default, env):
    EXPECTED_HAIR = "some"

    class Child(SettingsLeaf):
        HAIR: str = EXPECTED_HAIR

    EXPECTED_CHILDREN = {"Thomas": Child({"HAIR": "yes"})}

    class Parent(Child, SettingsBase):
        CHILDREN: Dict[str, Child] = mapping_default(EXPECTED_CHILDREN)

    if init_method == "defaults":
        pass
    elif init_method == "environment":
        env.update({"HAIR": "any"})
        EXPECTED_HAIR = "any"
    p = Parent()
    assert p.HAIR == EXPECTED_HAIR
    assert p.CHILDREN == EXPECTED_CHILDREN


@pytest.mark.parametrize("init_method", ["defaults", "environment"])
@pytest.mark.parametrize(
    "mapping_default",
    [
        pytest.param(Field, id="Field_default"),
        pytest.param(
            lambda x: Field(default_factory=lambda: x), id="Field_defaultfactory"
        ),
        pytest.param(lambda x: x, id="Class"),
    ],
)
def test_nested_mapping_no_defaults(init_method, mapping_default, env):
    EXPECTED_HAIR = "any"

    class Child(SettingsLeaf):
        HAIR: str = EXPECTED_HAIR
        EYES: Dict[str, bool] = mapping_default({"left": True, "right": True})

    EXPECTED_CHILDREN = {"Thomas": Child()}

    class Parent(Child, SettingsBase):
        CHILDREN: Dict[str, Child] = Field(
            default_factory=lambda: {n: Child() for n in ["Thomas"]}
        )

    # pytest.fail(mapping_default)
    if init_method == "defaults":
        pass
    elif init_method == "environment":
        env.update({"HAIR": "any"})
        EXPECTED_HAIR = "any"
    p = Parent()
    assert p.HAIR == EXPECTED_HAIR
    assert p.CHILDREN == EXPECTED_CHILDREN


@pytest.mark.parametrize(
    "env_values,validator",
    [
        pytest.param(None, lambda _: True, id="from_constructor"),
        (
            [("CHILDREN", {"Thomas": {"HAIR": "yea"}})],
            lambda p: p.__dict__["CHILDREN"]["Thomas"].HAIR == "yea",
        ),
        (
            [("CHILDREN", {"Thomas": {"EYES": {"center": {"HAS": False}}}})],
            lambda p: p.__dict__["CHILDREN"]["Thomas"].EYES["center"].HAS is False,
        ),
    ],
)
@pytest.mark.parametrize(
    "mapping_default",
    [
        pytest.param(Field, id="Field_default"),
        pytest.param(
            lambda x: Field(default_factory=lambda: x), id="Field_defaultfactory"
        ),
        pytest.param(lambda x: x, id="Class"),
    ],
)
def test_nested_twice_mapping_no_defaults(env_values, validator, mapping_default, env):
    EXPECTED_HAIR = "any"

    class Eye(SettingsLeaf):
        HAS: bool = mapping_default(True)

    class Child(SettingsLeaf):
        HAIR: str = EXPECTED_HAIR
        EYES: Dict[str, Eye] = mapping_default({"left": Eye(), "right": Eye()})

    class Parent(Child, SettingsBase):
        CHILDREN: Dict[str, Child] = Field(
            default_factory=lambda: {n: Child() for n in ["Thomas", "Tom"]}
        )

    # pytest.fail(mapping_default)
    if env_values is not None:
        env_values: List[Tuple[str, dict]]
        for tup in env_values:
            key, val = tup
            env.set(key, json.dumps(val))
        EXPECTED_HAIR = "any"
    p = Parent()
    assert p.HAIR == EXPECTED_HAIR
    if env_values is None:
        assert p.CHILDREN["Thomas"] == Child()
    assert validator(p)


def url_param(
    scheme: Union[Literal["http"], Literal["https"]], host: str, port: int, path: str
) -> pytest.param:
    tpl = (scheme, host, port, path)
    return pytest.param(*tpl, id=f"{scheme}://{host}:{port}/{path}")


@pytest.mark.parametrize("url_class", [pyd_c_Url, str])
@pytest.mark.parametrize(
    "scheme,host,port,path",
    [
        url_param(status_code, "my-url.example.local", 8080, path)
        for status_code in ["http", "https"]
        for path in ["", "my-long/path/"]
    ],
)
def test_url_parsing(
    env,
    url_class: Type[Union[pyd_c_Url, str]],
    scheme: Union[Literal["http"], Literal["https"]],
    host: str,
    port: int,
    path: str,
):
    url = pyd_c_Url.build(scheme=scheme, host=host, port=port, path=path)
    url_s = str(url)

    class MySetting(SettingsBase):
        MY_URL: url_class

    env.set("MY_URL", url_s)
    assert str(MySetting().MY_URL) == url_s
