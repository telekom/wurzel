# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import inspect
from pathlib import Path
from typing import Any, TypedDict

import yaml

import wurzel
from wurzel.backend.backend import Backend
import wurzel.cli
from wurzel.step import TypedStep
from wurzel.step.typed_step import MODEL_TYPE
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor

from hera.workflows import DAG, Workflow, script,Artifact

class DvcDict(TypedDict):
    """Internal Representation."""

    cmd: str
    deps: list[str]
    outs: list[str]
    always_changed: bool





class DvcBackend(Backend):
    """'Adapter' which creates DVC yamls."""

    def __init__(
        self,
        data_dir: Path = Path("./data"),
        executer: BaseStepExecutor = PrometheusStepExecutor,
        encapsulate_env: bool = True,
    ) -> None:
        if not isinstance(data_dir, Path):
            data_dir = Path(data_dir)
        self.executor: type[BaseStepExecutor] = executer
        self.data_dir = data_dir
        self.encapsulate_env = encapsulate_env
        super().__init__()

    def generate_dict(
        self,
        step: TypedStep,
    ) -> dict[str, DvcDict]:
        """Generates the resulting dvc.yaml as dict by calling all
        its required steps as well, in recursive manner.

        Returns
        -------
        dict
            _description_

        """
        result: dict[str, Any] = {}
        outputs_of_deps: list[Path] = []
        for o_step in step.required_steps:
            dep_result = self.generate_dict(o_step)
            result |= dep_result
            outputs_of_deps += dep_result[o_step.__class__.__name__]["outs"]
        output_path = self.data_dir / step.__class__.__name__
        cmd = wurzel.cli.generate_cli_call(
            step.__class__,
            inputs=outputs_of_deps,
            output=output_path,
            executor=self.executor,
            encapsulate_env=self.encapsulate_env,
        )
        return result | {
            step.__class__.__name__: {
                "cmd": cmd,
                "deps": [inspect.getfile(step.__class__), *outputs_of_deps],
                "outs": [output_path],
                "always_changed": step.is_leaf(),
            }
        }

    def generate_yaml(
        self,
        step: TypedStep,
    ) -> str:
        """Generates the dvc.yaml."""
        data = self.generate_dict(step)
        for k in data:
            for key in ["outs", "deps"]:
                data[k][key] = [str(p) for p in data[k][key]]
        return yaml.dump({"stages": data})

