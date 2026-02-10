# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from typing import Callable

import pytest

from wurzel.core.settings import Settings
from wurzel.core.typed_step import TypedStep
from wurzel.datacontract.datacontract import PydanticModel
from wurzel.executors import BaseStepExecutor
from wurzel.utils.meta_settings import WZ, create_model


class MySettingsA(Settings):
    KEY: str


class MySettingsB(Settings):
    LST: list[str]


class MySettingsC(Settings):
    DCT: dict[str, list[str]]


class StepA(TypedStep[MySettingsA, PydanticModel, PydanticModel]):
    def run(self, inpt: PydanticModel) -> PydanticModel:
        return PydanticModel()


class StepB(TypedStep[MySettingsB, PydanticModel, PydanticModel]):
    def run(self, inpt: PydanticModel) -> PydanticModel:
        return PydanticModel()


class StepC(TypedStep[MySettingsC, PydanticModel, PydanticModel]):
    def run(self, inpt: PydanticModel) -> PydanticModel:
        return PydanticModel()


@pytest.fixture()
def dummy_with_env_prep(env) -> tuple[Callable[[], TypedStep], list[TypedStep]]:
    env.set("STEPA__KEY", "value")
    env.set("STEPB__LST", '["value"]')
    env.set("STEPC", '{"DCT": {"key": ["value"]}}')
    a = WZ(StepA)
    b = WZ(StepB)
    c = WZ(StepC)

    def pipeline_tst_func():
        a >> b >> c
        return c

    return pipeline_tst_func, [a, b, c]


def test_dummy_with_env__expand_pipeline_to_steps(dummy_with_env_prep):
    pipeline_tst_func, used_steps = dummy_with_env_prep
    steps = pipeline_tst_func().traverse()
    assert len(steps) == len(used_steps)
    assert all(step in steps for step in used_steps)


def test_dummy_with_env__validate_settings(dummy_with_env_prep):
    _, steps = dummy_with_env_prep
    mdl = create_model(steps)()
    assert mdl.STEPA.KEY == "value"
    assert mdl.STEPB.LST == ["value"]
    assert mdl.STEPC.DCT == {"key": ["value"]}


def test_dummy_with_env_execute(dummy_with_env_prep, tmp_path):
    pipeline_tst_func, used_steps = dummy_with_env_prep
    dummy_file = tmp_path / "dummy.json"
    dummy_file_out = tmp_path / "dummy_out.json"
    dummy_file.write_bytes(b"{}")
    with BaseStepExecutor() as exc:
        for step in used_steps:
            exc(step.__class__, {dummy_file}, dummy_file_out)
