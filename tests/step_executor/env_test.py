# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json
from typing import Optional

import pytest

from wurzel.datacontract import PydanticModel
from wurzel.step.settings import Settings
from wurzel.step.typed_step import TypedStep
from wurzel.step_executor import BaseStepExecutor


class MySettings(Settings):
    A: int
    B: str
    C: list[int]
    D: Optional[int] = None


class MyResult(PydanticModel):
    data: dict


class MyStep(TypedStep[MySettings, None, MyResult]):
    def run(self, inpt: None) -> MyResult:
        return MyResult(data=self.settings.model_dump())


@pytest.mark.parametrize(
    "base_env",
    [
        MySettings(A=1, B="b", C=[1, 2], D=None),
        MySettings(A=1, B="b", C=[], D=None),
        MySettings(A=1, B="b", C=[1, 2], D=2),
    ],
)
@pytest.mark.parametrize(
    "base_env_gen",
    [
        pytest.param(lambda cls, x: {cls.__name__.upper(): x.model_dump_json()}, id="json"),
        pytest.param(
            lambda cls, x: {f"{cls.__name__.upper()}__{k}": json.dumps(v) for k, v in x.model_dump(mode="json").items() if v is not None},
            id="keys",
        ),
    ],
)
def test_set_env(tmp_path, env, base_env, base_env_gen):
    out = tmp_path / "out.json"
    base_env = base_env_gen(MyStep, base_env)
    env.update(base_env)
    with BaseStepExecutor() as exc:
        exc(MyStep, set(), out)


def test_set_env_no(tmp_path):
    out = tmp_path / "out.json"

    class MyOtherStep(TypedStep[None, None, MyResult]):
        def run(self, inpt: None) -> MyResult:
            return MyResult(data={"da": "ta"})

    with BaseStepExecutor() as exc:
        exc(MyOtherStep, set(), out)
