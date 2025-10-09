# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
from pathlib import Path

from wurzel.executors.base_executor import BaseStepExecutor
from wurzel.step import MarkdownDataContract, NoSettings
from wurzel.step.self_consuming_step import SelfConsumingLeafStep


class MySelfConsumingStep(SelfConsumingLeafStep[NoSettings, list[MarkdownDataContract]]):
    def run(self, inpt: list[MarkdownDataContract] | None) -> list[MarkdownDataContract]:
        if not inpt:
            return [MarkdownDataContract(md="abc", url="cde", keywords="")]
        else:
            return inpt + inpt


def test_self_consuming_no_input(tmp_path: Path):
    output = tmp_path / f"{MySelfConsumingStep.__name__}"
    os.mkdir(tmp_path / "input")
    shutil.copy("tests/data/markdown.json", tmp_path / "input/")
    output.mkdir(parents=True, exist_ok=True)
    with BaseStepExecutor() as ex:
        result = ex(MySelfConsumingStep, set(), output)

    assert list(output.iterdir())
    assert len(result[0][0]) == 1


def test_self_consuming_with_input(tmp_path: Path):
    output = tmp_path / f"{MySelfConsumingStep.__name__}"
    os.mkdir(tmp_path / "input")
    shutil.copy("tests/data/markdown.json", tmp_path / "input/")
    output.mkdir(parents=True, exist_ok=True)
    with BaseStepExecutor() as ex:
        ex(MySelfConsumingStep, set(), output)
        result = ex(MySelfConsumingStep, set(), output)
    assert list(output.iterdir())
    assert len(result[0][0]) == 2
