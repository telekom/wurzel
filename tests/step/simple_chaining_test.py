# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from wurzel.adapters import DvcBackend
from wurzel.step import Step


class A(Step):
    def execute(self, inputs: set[Path], output: Path):
        pass


class B(Step):
    def execute(self, inputs: set[Path], output: Path):
        pass


def test_asd():
    a = A()
    b = B()
    a >> b
    dic = DvcBackend().generate_dict(b)
    assert dic
