# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.datacontract import PydanticModel
from wurzel import TypedStep, NoSettings
from wurzel.step_executor import BaseStepExecutor
from wurzel.exceptions import ContractFailedException
class A(PydanticModel):
    i: int
class B(PydanticModel):
    b: int
def test_run_ok(tmp_path):
    class MyStep(TypedStep[NoSettings, A, A]):
        def run(self, inpt: A) -> A:
            return A(i=-1)
    BaseStepExecutor().execute_step(MyStep, (A(i=9),) , tmp_path /"out.json")

@pytest.mark.parametrize("return_value", [
    pytest.param(([A(i=-1)]),id="ListOfCorrect"),
    pytest.param([A],id="ListOfClass"),
    pytest.param(A,id="Class"),
    pytest.param([],id="EmptyList"),
    pytest.param(None,id="None"),
    pytest.param(B(b=-1),id="WrongType"),
    
])
def test_run_wrong_return(tmp_path, return_value):
    class MyStep(TypedStep[NoSettings, A, A]):
        def run(self,  inpt: A) -> A:
            return return_value
    with pytest.raises(ContractFailedException):
        BaseStepExecutor().execute_step(MyStep, set(), tmp_path /"out.json")
