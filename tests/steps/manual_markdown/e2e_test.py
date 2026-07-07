# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


import json

from wurzel.executors import BaseStepExecutor
from wurzel.steps import ManualMarkdownStep


def test_step(tmp_path, env):
    inpt = tmp_path / "inpt"
    inpt.mkdir()
    (inpt / "file_a.md").write_text("#My file\nThis is text")
    (inpt / "file_b.md").write_text("#My file\nThis is text")
    outp = tmp_path / "out"
    env.set("FOLDER_PATH", str(tmp_path.absolute()))
    BaseStepExecutor(dont_encapsulate=True)(ManualMarkdownStep, set(), outp)
    out = outp / "ManualMarkdown.json"
    assert out.exists() and out.is_file()
    data = json.loads(out.read_text())
    assert data
    assert len(data) == 2
