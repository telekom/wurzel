# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Any

import pytest
from pandera.typing import Series

from wurzel.adapters import DvcBackend
from wurzel.datacontract import PanderaDataFrameModel, PydanticModel
from wurzel.step import TypedStep
from wurzel.step.settings import StepSettings


class MySettings(StepSettings):
    sett: str


class MyModel(PydanticModel):
    s: str


def test_bad_step_no_types():
    with pytest.raises(TypeError):

        class MyStep(TypedStep):
            def run(self, inpt: list) -> Any:
                pass

        MyStep()


def test_bad_step_only_settings():
    with pytest.raises(TypeError):

        class MyStep(TypedStep[MySettings]):
            def run(self, inpt: list) -> Any:
                pass


def test_bad_step_only_settings_and_input():
    with pytest.raises(TypeError):

        class MyStep(TypedStep[MySettings, MyModel]):
            def run(self, inpt: list) -> Any:
                pass


def test_step_creation_good_no_settings():
    class MyStep(TypedStep[None, list[MyModel], MyModel]):
        def run(self, inpt: list[MyModel]) -> MyModel:
            pass


def test_step_creation_good_with_settings():
    class MyStep(TypedStep[MySettings, list[MyModel], MyModel]):
        def run(self, inpt: list[MyModel]) -> MyModel:
            pass


def test_step_chain_good():
    class MyStep(TypedStep[None, MyModel, MyModel]):
        def run(self, inpt: MyModel) -> MyModel:
            pass

    s1 = MyStep()
    s2 = MyStep()
    s1 >> s2


def test_step_chain_bad_contract():
    class MyStep(TypedStep[None, MyModel, MyModel]):
        def run(self, inpt: MyModel) -> MyModel:
            pass

    class MyOtherStep(TypedStep[None, list[MyModel], MyModel]):
        def run(self, inpt: list[MyModel]) -> MyModel:
            pass

    s1 = MyStep()
    s2 = MyOtherStep()
    with pytest.raises(TypeError):
        s1 >> s2
    pass


def test_generate():
    class SuccessModel(PydanticModel):
        s: str = "Done!"

    class MyCSV(PanderaDataFrameModel):
        col0: Series[int]

    class Step0(TypedStep[None, None, MyModel]):
        def run(self, inpt: None) -> MyModel:
            return MyModel(s="s")

    class Step1(TypedStep[None, MyModel, MyCSV]):
        def run(self, inpt: MyModel) -> MyCSV:
            return None

    class Step2(TypedStep[None, MyCSV, SuccessModel]):
        def run(self, inpt: MyCSV) -> SuccessModel:
            return SuccessModel()

    a = Step0()
    b = Step1()
    c = Step2()
    a >> b >> c
    steps = [a, b, c]
    res = DvcBackend.generate_dict(c, "/")
    assert res != {}
    for step in steps:
        data: dict = res.get(step.__class__.__name__, None)
        assert data is not None
        assert data["cmd"].startswith("python3 -m wurzel run")
    assert res[a.__class__.__name__]["outs"][0] == Path("/Step0")
    assert res[a.__class__.__name__]["outs"][0] in res[b.__class__.__name__]["deps"]
    assert res[b.__class__.__name__]["outs"][0] == Path("/Step1")


def test_circular():
    class MyStep(TypedStep[None, MyModel, MyModel]):
        def run(self, inpt: MyModel) -> MyModel:
            return inpt

    a = MyStep()
    a >> a
    # TODO: Maybe this should be caught before Python.Recursion Error
    with pytest.raises(RecursionError) as err:
        DvcBackend.generate_dict(a, ".")
        assert not isinstance(err, RecursionError)
