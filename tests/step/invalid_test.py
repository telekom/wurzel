# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


from typing import Any

import pytest

from wurzel.datacontract import PydanticModel
from wurzel.exceptions import ContractFailedException
from wurzel.step import TypedStep
from wurzel.step_executor import BaseStepExecutor


class MyModel(PydanticModel):
    i: int


@pytest.mark.parametrize(
    "result",
    [pytest.param({}, id="{}"), pytest.param({"i": "a"}, id="incorrect dtype")],
)
@pytest.mark.parametrize("base", [MyModel, list[MyModel]])
def test_pydantic_invalid_return(result, base, tmp_path):
    class Mystep(TypedStep[None, None, base]):
        def run(self, inpt: None) -> base:
            return result

    with pytest.raises(ContractFailedException):
        BaseStepExecutor().execute_step(Mystep, (), tmp_path / "res.json")


@pytest.mark.parametrize(
    "result, result_cls",
    [
        pytest.param({}, dict[Any, Any], id="{}"),
        pytest.param({"i": "a"}, dict[str, str], id="wrong_dict"),
        pytest.param(["i", "a"], list[str], id="wrong_list_types"),
        pytest.param("str", str, id="string"),
    ],
)
@pytest.mark.parametrize("base", [MyModel, list[MyModel]])
def test_invalid_return_with_wrong_typing(result, result_cls, base, tmp_path):
    class MyStep(TypedStep[None, None, list[base]]):
        def run(self, inpt: None) -> result_cls:
            return result

    with pytest.raises(ContractFailedException):
        BaseStepExecutor().execute_step(MyStep, (), tmp_path / "res.json")


# TODO: Equal Test for DVCPanderaBaseModel
