# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import inspect
from pathlib import Path
from typing import Any, Type, TypedDict

import yaml
from wurzel import BaseStepExecutor, PrometheusStepExecutor, TypedStep

import wurzel
import wurzel.cli


class DvcDict(TypedDict):
    """Internal Representation"""

    cmd: str
    deps: list[str]
    outs: list[str]
    always_changed: bool


class DvcAdapter:
    """'Adapter' which creates DVC yamls"""

    @classmethod
    def generate_dict(
        cls,
        step: TypedStep,
        data_output_folder: Path,
        executor: Type[BaseStepExecutor] = PrometheusStepExecutor,
        encapsulate_env: bool = True,
    ) -> dict[str, DvcDict]:
        """generates the resulting dvc.yaml as dict by calling all
        its required steps as well, in recursive manner.

        Returns
        -------
        dict
            _description_
        """
        if not isinstance(data_output_folder, Path):
            data_output_folder = Path(data_output_folder)
        result: dict[str, Any] = {}
        outputs_of_deps: list[Path] = []
        for o_step in step.required_steps:
            dep_result = cls.generate_dict(o_step, data_output_folder)
            result |= dep_result
            outputs_of_deps += dep_result[o_step.__class__.__name__]["outs"]
        output_path = data_output_folder / step.__class__.__name__
        cmd = wurzel.cli.generate_cli_call(
            step.__class__,
            inputs=outputs_of_deps,
            output=output_path,
            executor=executor,
            encapsulate_env=encapsulate_env,
        )
        return result | {
            step.__class__.__name__: {
                "cmd": cmd,
                "deps": [inspect.getfile(step.__class__), *outputs_of_deps],
                "outs": [output_path],
                "always_changed": step.is_leaf(),
            }
        }

    @classmethod
    def generate_yaml(cls, step, path: Path, data_output_folder: Path):
        """generates the dvc.yaml"""
        with open(path, "w", encoding="utf-8") as file:
            data = cls.generate_dict(step, data_output_folder)
            for k in data:
                for key in ["outs", "deps"]:
                    data[k][key] = [str(p) for p in data[k][key]]
            yaml.dump({"stages": data}, file)
