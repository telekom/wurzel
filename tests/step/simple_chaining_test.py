# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Set
from wurzel.step import Step
from wurzel.adapters import DvcAdapter
import pytest

class A(Step):
    def execute(self, inputs: Set[Path], output: Path):
        pass
class B(Step):
    def execute(self, inputs: Set[Path], output: Path):
        pass

def test_asd():
    a = A()
    b = B()
    a >> b
    dic =  DvcAdapter.generate_dict(b,".")
    assert dic
