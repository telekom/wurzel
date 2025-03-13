# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest
from pydantic import ValidationError

from wurzel import (
    BaseStepExecutor,
    PrometheusStepExecutor,
    PydanticModel,
    Settings,
    TypedStep,
)
from wurzel.exceptions import EnvSettingsError
from wurzel.step_executor.base_executor import step_env_encapsulation


class MySettings(Settings):
    key: str


class MyStep(TypedStep[MySettings, PydanticModel, PydanticModel]):
    def run(self, inpt: PydanticModel) -> PydanticModel:
        return PydanticModel()


class MyWithoutSettingsStep(TypedStep[None, PydanticModel, PydanticModel]):
    def run(self, inpt: PydanticModel) -> PydanticModel:
        return PydanticModel()


def test_missing():
    with pytest.raises(ValidationError):
        MyStep()


def test_missing_in_env():
    with pytest.raises(EnvSettingsError):
        with step_env_encapsulation(MyStep):
            MyStep()


def test_no_settings():
    with step_env_encapsulation(MyWithoutSettingsStep):
        MyWithoutSettingsStep()


@pytest.mark.parametrize(
    "env_set", [("MYSTEP__key", "value"), ("MYSTEP", '{"key": "value"}')]
)
def test_env_set(env, env_set):
    env.set(*env_set)
    with pytest.raises(ValidationError):
        MyStep()
    with step_env_encapsulation(MyStep):
        MyStep()


@pytest.mark.parametrize("executor", [PrometheusStepExecutor, BaseStepExecutor])
@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({}, id="{}"),
        pytest.param({"dont_encapsulate": True}, id="True"),
        pytest.param({"dont_encapsulate": False}, id="False"),
    ],
)
def test_constructor(executor, kwargs):
    with executor(**kwargs) as ex:
        assert ex
