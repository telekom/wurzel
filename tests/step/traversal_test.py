# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel import TypedStep, PydanticModel
from wurzel.utils import WZ


class StepA(TypedStep[None, PydanticModel, PydanticModel]):
    def run(self, inpt: PydanticModel) -> PydanticModel:
        return PydanticModel()


class StepB(TypedStep[None, PydanticModel, PydanticModel]):
    def run(self, inpt: PydanticModel) -> PydanticModel:
        return PydanticModel()


class StepC(TypedStep[None, PydanticModel, PydanticModel]):
    def run(self, inpt: PydanticModel) -> PydanticModel:
        return PydanticModel()


def test_single():
    a = WZ(StepA)
    assert a.traverse() == {a}


def test_easy():
    a = WZ(StepA)
    b = WZ(StepB)
    b >> a
    assert a.traverse() == {a, b}


def test_2_1():
    a = WZ(StepA)
    b = WZ(StepB)
    c = WZ(StepC)
    b >> a
    c >> a
    assert a.traverse() == {a, b, c}
