# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest

from wurzel import (
    BaseStepExecutor,
    MarkdownDataContract,
    Settings,
    TypedStep,
)
from wurzel.exceptions import StepFailed


class MySettings(Settings):
    FIELD: int


class TestableStep(TypedStep[MySettings, None, list[MarkdownDataContract]]):
    def run(self, inpt: None) -> list[MarkdownDataContract]:
        assert self.settings.FIELD == 12
        return []


def test_no_env(tmp_path: Path):
    with BaseStepExecutor() as ex:
        with pytest.raises(StepFailed) as err:
            ex(TestableStep, set(), tmp_path / "Hey")
        assert err


def test_with_env(env, tmp_path: Path):
    env.set("TESTABLESTEP__FIELD", "12")
    with BaseStepExecutor() as ex:
        ex(TestableStep, set(), tmp_path / "Hey")


def test_with_extra_env_bad(env):
    env.set("TESTABLESTEP__FIELD", "12")
    env.set("TESTABLESTEP__extra", "12")
    with pytest.raises(StepFailed):
        with BaseStepExecutor() as ex:
            ex(TestableStep, set(), Path("Hey"))


def test_with_extra_env_good(env, tmp_path: Path):
    env.set("ALLOW_EXTRA_SETTINGS", "true")
    env.set("TESTABLESTEP__FIELD", "12")
    env.set("TESTABLESTEP__extra", "12")
    with BaseStepExecutor() as ex:
        ex(TestableStep, set(), tmp_path / "Hey")
