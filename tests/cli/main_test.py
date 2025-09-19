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


def test_autocomplete_step_import_installed_package(tmp_path, monkeypatch):
    """Test that complete_step_import finds TypedStep classes from installed packages."""
    # Create a fake installed package structure
    fake_pkg_dir = tmp_path / "fake_package"
    fake_pkg_dir.mkdir()

    # Create __init__.py
    (fake_pkg_dir / "__init__.py").write_text("")

    # Create a subdirectory with a TypedStep class
    sub_dir = fake_pkg_dir / "steps"
    sub_dir.mkdir()
    (sub_dir / "__init__.py").write_text("")

    # Create a Python file with a TypedStep class
    step_file = sub_dir / "test_step.py"
    step_file.write_text("""
from wurzel.step import TypedStep
from typing import List
from wurzel.datacontract import MarkdownDataContract

class FakeTestStep(TypedStep[None, None, List[MarkdownDataContract]]):
    def run(self, input_data=None):
        return []
""")

    # Mock importlib.metadata.distributions to return our fake package
    from unittest.mock import Mock

    fake_dist = Mock()
    fake_dist.name = "fake_package"

    def mock_distributions():
        return [fake_dist]

    # Mock importlib.util.find_spec to return our fake package path
    fake_spec = Mock()
    fake_spec.origin = str(fake_pkg_dir / "__init__.py")

    def mock_find_spec(name):
        if name == "fake_package":
            return fake_spec
        return None

    monkeypatch.setattr("importlib.metadata.distributions", mock_distributions)
    monkeypatch.setattr("importlib.util.find_spec", mock_find_spec)

    # Test completion for the exact package name
    completion = main.complete_step_import("fake_package")
    assert "fake_package.steps.test_step.FakeTestStep" in completion

    # Test completion for package with submodule
    completion = main.complete_step_import("fake_package.steps")
    assert "fake_package.steps.test_step.FakeTestStep" in completion


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
