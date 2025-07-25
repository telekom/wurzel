# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


import pytest
import typer

import wurzel
import wurzel.steps
from wurzel.cli import _main as main
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor
from wurzel.steps.manual_markdown import ManualMarkdownStep


@pytest.mark.parametrize(
    "inpt_str, expected",
    [
        ("base", BaseStepExecutor),
        ("BASE", BaseStepExecutor),
        ("BaseStepExecutor", BaseStepExecutor),
        ("Prom", PrometheusStepExecutor),
        ("PROMETHEUS", PrometheusStepExecutor),
    ],
)
def test_executer_callback(inpt_str, expected):
    assert main.executer_callback(None, None, inpt_str) == expected


def test_executer_callback_bad():
    with pytest.raises(typer.BadParameter):
        main.executer_callback(None, None, "XX")


@pytest.mark.parametrize(
    "step_path",
    [
        "wurzel.steps.ManualMarkdownStep",
        "wurzel.steps:ManualMarkdownStep",
        "wurzel.steps.manual_markdown:ManualMarkdownStep",
        "wurzel.steps.manual_markdown.ManualMarkdownStep",
    ],
)
def test_step_callback(step_path):
    assert main.step_callback(None, None, step_path) == wurzel.steps.ManualMarkdownStep


@pytest.mark.parametrize(
    "step_path",
    [
        "wurzel.steps.NotExist",
        "Nope",
        "wurzel.cli._main:main",
        "doesnt_exist.steps.manual_markdown.ManualMarkdownStep",
    ],
)
def test_step_callback_bad(step_path):
    with pytest.raises(typer.BadParameter):
        main.step_callback(None, None, step_path)


def test_autocomplete_step_import():
    completion = main.complete_step_import("")
    assert completion
    assert "wurzel.steps.manual_markdown.ManualMarkdownStep" in completion


def test_run(tmp_path, env):
    out = tmp_path / "out"
    inp = tmp_path / "in"  #
    inp.mkdir()
    (inp / "file.md").write_text("#Hello\n world")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))
    main.run(
        step=ManualMarkdownStep,
        executor=BaseStepExecutor,
        input_folders=[],
        output_path=out,
    )
    assert list(out.glob("*"))
    assert (out / "ManualMarkdown.json").read_text()


@pytest.mark.parametrize("gen_env", [True, False])
def test_inspekt(gen_env):
    main.inspekt(ManualMarkdownStep, gen_env)
