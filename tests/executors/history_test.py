# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.core import MarkdownDataContract, NoSettings, TypedStep
from wurzel.core.history import History, step_history
from wurzel.executors import BaseStepExecutor


class OkExc(Exception):
    pass


class TestableXXStep(TypedStep[NoSettings, None, list[MarkdownDataContract]]):
    def run(self, inputs):
        assert str(step_history.get()[-1]) == "TestableXX"
        return []


def test_setting_of_history(tmp_path):
    with BaseStepExecutor() as ex:
        assert step_history.get() is None, "Before should be None"
        ex(TestableXXStep, set(), tmp_path / "Hey")
        assert step_history.get() is None, "Cleanup after"


def test_history_obj():
    h = History()
    h += "A"
    h += [TestableXXStep, TestableXXStep()]
    h += object
    h += lambda _: _
    assert h._history == ["A", "TestableXX", "TestableXX", "object", "function"]


def test_history_init():
    assert History() == History(initial=[])


def test_getitiem_bad():
    with pytest.raises(TypeError):
        h = History()
        h["Hi"]


def test_add():
    h = History()
    h = h + "A"
    h = h + [TestableXXStep, TestableXXStep()]
    h = h + object
    h = h + test_add
    h = h + h
    assert h._history == ["A", "TestableXX", "TestableXX", "object", "function"] * 2


def test_str_repr():
    h = History("A", "B")
    assert str(h) != repr(h)
    assert str(h) == "A-B"
