# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


import json

from wurzel.step_executor import BaseStepExecutor
from wurzel.steps import ManualMarkdownStep


def test_step(tmp_path, env):
    inpt = tmp_path / "inpt"
    inpt.mkdir()
    (inpt / "file_a.md").write_text("#My file\nThis is text")
    (inpt / "file_b.md").write_text("#My file\nThis is text")
    outp = tmp_path / "out"
    env.set("FOLDER_PATH", str(tmp_path.absolute()))
    BaseStepExecutor(dont_encapsulate=True)(ManualMarkdownStep, set(), outp)
    # Generator steps accumulate items and flush to numbered batch files.
    batch_files = sorted(outp.glob("*_batch*.json"))
    assert len(batch_files) == 1, "Expected exactly 1 batch file for 2 items"
    data = json.loads(batch_files[0].read_text())
    assert len(data) == 2
