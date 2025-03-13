# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest
from wurzel.step import TypedStep
from wurzel.datacontract import PydanticModel


class DataType(PydanticModel):
    value: str = "V"


class OtherDataType(PydanticModel):
    value: str = "V"
    key: str = "K"


class FirstStep(TypedStep[None, None, DataType]):
    def run(self, inpt: None) -> DataType:
        return DataType()


class SecondStep(TypedStep[None, DataType, OtherDataType]):
    def run(self, inpt: DataType) -> OtherDataType:
        return OtherDataType()


class FirstListStep(TypedStep[None, None, list[DataType]]):
    def run(self, inpt: None) -> list[DataType]:
        return [DataType()]


class SecondListStep(TypedStep[None, list[OtherDataType], OtherDataType]):
    def run(self, inpt: list[OtherDataType]) -> OtherDataType:
        return OtherDataType()


@pytest.mark.parametrize(
    "chain",
    [
        pytest.param(lambda: FirstStep() >> FirstStep(), id="None got input"),
        pytest.param(lambda: SecondStep() >> FirstStep(), id="got wrong"),
        pytest.param(
            lambda: FirstListStep() >> SecondListStep(), id="got wrong in list"
        ),
    ],
)
def test_invalid_chain(chain):
    try:
        chain()
    except TypeError as err:
        assert "Cannot chain" in str(err)
        return
    pytest.fail("chaining did not result in TypeError")
