# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.cli import generate_cli_call
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor
from wurzel.steps.manual_markdown import ManualMarkdownStep


@pytest.mark.parametrize("executor", [BaseStepExecutor, PrometheusStepExecutor])
def test_good_cli_call(executor, tmp_path):
    """Test the generate_cli_call function with valid parameters and different executors.

    Args:
        executor: The step executor class to use (BaseStepExecutor or PrometheusStepExecutor).
        tmp_path: Temporary directory path provided by pytest.

    """
    out_path = tmp_path / "out"
    res = generate_cli_call(ManualMarkdownStep, [], out_path, executor=executor)
    comand = (
        f"wurzel run wurzel.steps.manual_markdown:ManualMarkdownStep -o {out_path.absolute()} -e {executor.__qualname__}  --encapsulate-env"  # noqa: E501
    )

    assert res == comand


def test_good_cli_call_with_input(tmp_path):
    out_path = tmp_path / "out"
    res = generate_cli_call(
        ManualMarkdownStep,
        [tmp_path],
        out_path,
        executor=BaseStepExecutor,
    )
    assert (
        res
        == f"wurzel run wurzel.steps.manual_markdown:ManualMarkdownStep -o {out_path.absolute()} -e BaseStepExecutor -i {tmp_path.absolute()} --encapsulate-env"  # noqa: E501
    )


def test_good_cli_call_with_inputs(tmp_path):
    out_path = tmp_path / "out"
    res = generate_cli_call(ManualMarkdownStep, [tmp_path, tmp_path], out_path, executor=BaseStepExecutor)
    assert (
        res
        == f"""wurzel run wurzel.steps.manual_markdown:ManualMarkdownStep -o {out_path.absolute()} -e BaseStepExecutor -i {tmp_path.absolute()} -i {tmp_path.absolute()} --encapsulate-env"""  # noqa: E501
    )


# @pytest.mark.parametrize("backend", ["DvcBackend", "ArgoBackend"])
# def test_backend_cli(tmp_path, backend):
#     cmd = [
#         "wurzel",
#         "generate",
#         "examples.pipeline.pipelinedemo:pipeline",
#         "--backend", backend
#     ]
#     proc = subprocess.run(cmd, capture_output=True, text=True)
#     assert proc.returncode == 0
