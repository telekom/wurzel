# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
import shutil
from pathlib import Path

import pytest

from wurzel.utils import HAS_SPACY, HAS_TIKTOKEN

if not HAS_SPACY or not HAS_TIKTOKEN:
    pytest.skip("Simple splitter dependencies (spacy, tiktoken) are not available", allow_module_level=True)

from wurzel.step_executor import BaseStepExecutor
from wurzel.steps.splitter import SimpleSplitterStep


@pytest.fixture
def default_markdown_data(tmp_path):
    mock_file = Path("tests/data/markdown.json")
    input_folder = tmp_path / "input"
    input_folder.mkdir()
    shutil.copy(mock_file, input_folder)
    output_folder = tmp_path / "out"
    return (input_folder, output_folder)


def test_simple_splitter_step(default_markdown_data, env):
    """Tests the execution of the `SimpleSplitterStep` with a mock input file."""
    env.set("SIMPLESPLITTERSTEP__TOKEN_COUNT_MIN", "64")
    env.set("SIMPLESPLITTERSTEP__TOKEN_COUNT_MAX", "256")
    env.set("SIMPLESPLITTERSTEP__TOKEN_COUNT_BUFFER", "32")

    input_folder, output_folder = default_markdown_data
    step_res = BaseStepExecutor(dont_encapsulate=False).execute_step(SimpleSplitterStep, [input_folder], output_folder)
    assert output_folder.is_dir()
    assert len(list(output_folder.glob("*"))) > 0

    step_output, step_report = step_res[0]

    assert len(step_output) == 11, "Step outputs have wrong count."
    assert step_report.results == 11, "Step report has wrong count of outputs."
