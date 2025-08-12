# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.step import NoSettings, PydanticModel, TypedStep
from wurzel.utils import WZ


class StepA(TypedStep[NoSettings, PydanticModel, PydanticModel]):
    def run(self, inpt: PydanticModel) -> PydanticModel:
        return PydanticModel()


class StepB(TypedStep[NoSettings, PydanticModel, PydanticModel]):
    def run(self, inpt: PydanticModel) -> PydanticModel:
        return PydanticModel()


class StepC(TypedStep[NoSettings, PydanticModel, PydanticModel]):
    def run(self, inpt: PydanticModel) -> PydanticModel:
        return PydanticModel()


@pytest.fixture(autouse=True)
def reset_class_dependencies():
    """Reset class-level dependencies before each test."""
    for step_class in [StepA, StepB, StepC]:
        step_class.clear_class_dependencies()
    yield
    # Clean up after test too
    for step_class in [StepA, StepB, StepC]:
        step_class.clear_class_dependencies()


def test_single():
    a = StepA
    assert a.traverse() == {a}


def test_easy():
    a = StepA
    b = StepB
    b >> a
    assert a.traverse() == {a, b}


def test_2_1():
    a = StepA
    b = StepB
    c = StepC
    b >> a
    c >> a
    assert a.traverse() == {a, b, c}


def test_class_composition():
    # Test class-level composition
    result = StepB >> StepA
    assert len(result.traverse()) == 2


def test_class_chain():
    # Test chaining classes
    result = StepC >> StepB >> StepA
    assert len(result.traverse()) == 3


def test_single_wrapper():
    a = WZ(StepA)
    assert a.traverse() == {a}


def test_easy_wrapper():
    a = WZ(StepA)
    b = WZ(StepB)
    b >> a
    assert a.traverse() == {a, b}


def test_2_1_wrapper():
    a = WZ(StepA)
    b = WZ(StepB)
    c = WZ(StepC)
    b >> a
    c >> a
    assert a.traverse() == {a, b, c}
