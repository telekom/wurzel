# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.executors import BaseStepExecutor
from wurzel.step import NoSettings, PydanticModel, TypedStep


class NiecheException(Exception):
    def __str__(self) -> str:
        return "NiecheException"


class MyModel(PydanticModel):
    i: int = 1


class MyToBeTestedStep(TypedStep[NoSettings, None, MyModel]):
    def run(self, inpt: None) -> MyModel:
        return MyModel()

    def finalize(self) -> None:
        raise NiecheException()


def test_finalize_called(tmp_path):
    with BaseStepExecutor() as ex:
        with pytest.raises(Exception) as e:
            _ = ex(MyToBeTestedStep, None, tmp_path)
        assert "NiecheException" in str(e.value.message)
