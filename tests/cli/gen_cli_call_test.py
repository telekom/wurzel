# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel import PrometheusStepExecutor
import pytest
from wurzel import BaseStepExecutor
from wurzel.cli import generate_cli_call
from wurzel.steps.manual_markdown import ManualMarkdownStep

@pytest.mark.parametrize("executor", [BaseStepExecutor, PrometheusStepExecutor])
def test_good_cli_call(executor, tmp_path):
    out_path = tmp_path / "out"
    res = generate_cli_call(
        ManualMarkdownStep,
        [],
        out_path,
        executor=executor
    )
    assert res == f"python3 -m wurzel run wurzel.steps.manual_markdown:ManualMarkdownStep -o {out_path.as_posix()} -e {executor.__qualname__}  --encapsulate-env"

def test_good_cli_call_with_input(tmp_path):
    out_path = tmp_path / "out"
    res = generate_cli_call(
        ManualMarkdownStep,
        [tmp_path],
        out_path,
        executor=BaseStepExecutor,
    )
    assert res == f"python3 -m wurzel run wurzel.steps.manual_markdown:ManualMarkdownStep -o {out_path.as_posix()} -e BaseStepExecutor -i {tmp_path.as_posix()} --encapsulate-env"
def test_good_cli_call_with_inputs(tmp_path):
    out_path = tmp_path / "out"
    res = generate_cli_call(
        ManualMarkdownStep,
        [tmp_path, tmp_path],
        out_path,
        executor=BaseStepExecutor
    )
    assert res == f"python3 -m wurzel run wurzel.steps.manual_markdown:ManualMarkdownStep -o {out_path.as_posix()} -e BaseStepExecutor -i {tmp_path.as_posix()} -i {tmp_path.as_posix()} --encapsulate-env"
