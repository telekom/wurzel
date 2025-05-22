# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from wurzel.adapters import DvcBackend
from wurzel.step import Step
from wurzel.step_executor import BaseStepExecutor


def is_valid_dvc_yaml(path: Path) -> bool:
    import os
    shell = os.name == "nt"
    create_stdout = subprocess.getoutput(
        f"cd {path.parent} && git init && dvc init" if not shell else f"cd /d {path.parent} && git init && dvc init"
    )
    status_stdout = subprocess.getoutput(
        f"cd {path.parent} && dvc stage list" if not shell else f"cd /d {path.parent} && dvc stage list"
    )
    assert "Initialized empty Git repository in" in create_stdout, create_stdout
    assert "Initialized DVC repository." in create_stdout, create_stdout
    assert "is invalid" not in status_stdout


class StepImplementedLeaf(Step):
    def execute(self, inputs: set[Path], output: Path):
        assert not inputs
        with open(output / "dummy_output.md", "a") as file:
            file.write("#Lorem Ipsum")


class StepImplementedBranch(Step):
    def execute(self, inputs: set[Path], output: Path):
        shutil.copytree(inputs, output, dirs_exist_ok=True)
        for f in output.iterdir():
            shutil.move(output / f, output / (f.name + "_modified"))
        pass


@pytest.fixture(scope="function")
def nested_steps(tmp_path) -> tuple[Step, Step]:
    output_1 = tmp_path / f"{StepImplementedLeaf.__name__}_1"
    output_1.mkdir()
    output_2 = tmp_path / f"{StepImplementedLeaf.__name__}_2"
    output_2.mkdir()

    step1 = StepImplementedLeaf()
    step2 = StepImplementedBranch()
    step1 >> step2
    return (step1, output_1, step2, output_2)


def test_dvc_node_abstract(tmp_path: Path):
    output = tmp_path / "output"
    output.mkdir()
    with pytest.raises(Exception):
        BaseStepExecutor()(Step, {}, output)


def test_implement_DVC_node(tmp_path: Path):
    output = tmp_path / f"{StepImplementedLeaf.__name__}"
    output.mkdir(parents=True, exist_ok=True)

    assert not list(output.iterdir())
    StepImplementedLeaf().execute({}, output)
    assert list(output.iterdir())


def test_chain_implemented_DVC_modes(nested_steps: tuple[Step, Path, Step, Path]):
    step1, output_1, step2, output_2 = nested_steps
    step1.execute({}, output_1)
    assert output_1.iterdir()
    step2.execute(output_1, output_2)
    assert any(f.name.endswith("_modified") for f in output_2.iterdir())


def test_generate_dict(tmp_path: Path):
    dvc_pipe: dict = DvcBackend(tmp_path).generate_dict(StepImplementedLeaf())
    assert "StepImplementedLeaf" in dvc_pipe
    assert all(key in dvc_pipe["StepImplementedLeaf"] for key in ("deps", "outs", "cmd"))


def test_generate_nested_dict(nested_steps):
    step1, output_1, step2, output_2 = nested_steps
    step2: Step = step2
    dvc_pipe: dict = DvcBackend(output_2).generate_dict(step2)
    assert len(dvc_pipe) == 2
    assert all(key in dvc_pipe[step2.__class__.__name__] for key in ("deps", "outs", "cmd"))
    assert all(key in dvc_pipe[step1.__class__.__name__] for key in ("deps", "outs", "cmd"))


def test_save_yaml(nested_steps, tmp_path: Path):
    step1, output_1, step2, output_2 = nested_steps
    step2: Step = step2
    target_path = tmp_path / "dvc.yaml"
    yml = DvcBackend(tmp_path).generate_yaml(step2)
    DvcBackend.save_yaml(yml, target_path)
    assert target_path.exists()
    with open(target_path) as f:
        yaml.safe_load(f)
    is_valid_dvc_yaml(target_path)


def test_rshift_override(tmp_path):
    step1 = StepImplementedLeaf()
    step2 = StepImplementedBranch()
    step1 >> step2
    assert len(DvcBackend(tmp_path).generate_dict(step2)) == 2


def test_rshift_override_branched(tmp_path):
    class StepImplementedLeaf2(StepImplementedLeaf):
        pass

    target_path = tmp_path / "dvc.yaml"
    step1 = StepImplementedLeaf()
    step3 = StepImplementedLeaf2()
    step2 = StepImplementedBranch()

    step1 >> step2
    step3 >> step2
    backend = DvcBackend(tmp_path)
    backend.path = target_path
    yml = backend.generate_yaml(step2)
    backend.save_yaml(yml, target_path)
    assert len(DvcBackend(tmp_path).generate_dict(step2)) == 3
