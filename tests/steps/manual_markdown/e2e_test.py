# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

import json

from wurzel.steps import ManualMarkdownStep
from wurzel.step_executor import BaseStepExecutor


def test_step(tmp_path, env):
    inpt = tmp_path / "inpt"
    inpt.mkdir()
    file_a = (inpt / "file_a.md").write_text("#My file\nThis is text")
    file_b = (inpt / "file_b.md").write_text("#My file\nThis is text")
    outp = tmp_path / "out"
    env.set("FOLDER_PATH", tmp_path.as_posix())
    BaseStepExecutor(dont_encapsulate=True)(ManualMarkdownStep, set(), outp)
    out = outp / "ManualMarkdown.json"
    assert out.exists() and out.is_file()
    data = json.loads(out.read_text())
    assert data
    assert len(data) == 2
