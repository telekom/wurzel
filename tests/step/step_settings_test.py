# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest
from pydantic import ValidationError
from wurzel import NoSettings, TypedStep, PydanticModel, Settings
from wurzel.exceptions import StaticTypeError
from types import NoneType
# used in pipel


class MyModel(PydanticModel):
    pass


class MySettings(Settings):
    IMPORTANT: str


@pytest.mark.parametrize("SettingsT", [NoSettings, MySettings])
def test_class_definition(SettingsT):
    class MyClass(TypedStep[SettingsT, PydanticModel, PydanticModel]):
        def run(self, inpt: PydanticModel) -> PydanticModel:
            return PydanticModel()

    used_in_pipeline = TypedStep.__new__(MyClass)
    assert used_in_pipeline.settings_class == SettingsT or NoneType
    assert used_in_pipeline.input_model_class == PydanticModel
    assert used_in_pipeline.output_model_class == PydanticModel


def test_settings_no_env():
    class MyClass(TypedStep[MySettings, PydanticModel, PydanticModel]):
        def run(self, inpt: PydanticModel) -> PydanticModel:
            return PydanticModel()

    with pytest.raises(ValidationError):
        MyClass()


def test_settings_env(env):
    env.set("IMPORTANT", "VALUE")

    class MyClass(TypedStep[MySettings, PydanticModel, PydanticModel]):
        def run(self, inpt: PydanticModel) -> PydanticModel:
            return PydanticModel()

    ins = MyClass()
    assert ins.settings.IMPORTANT == "VALUE"


def test_invalid_setting():
    class MyStep(TypedStep[PydanticModel, PydanticModel, PydanticModel]):
        def run(self, inpt: PydanticModel) -> PydanticModel:
            return PydanticModel()

    with pytest.raises(StaticTypeError):
        MyStep()
