# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import inspect
from pathlib import Path
from typing import Any, TypedDict

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

import wurzel
import wurzel.cli
from wurzel.backend.backend import Backend
from wurzel.step import TypedStep
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor


class DvcDict(TypedDict):
    """Internal Representation."""

    cmd: str
    deps: list[str]
    outs: list[str]
    always_changed: bool


class DvcBackendSettings(BaseSettings):
    """Settings object which is infusable through ENV variables like DVCBACKEND__ENCAPSULATE_ENV."""

    model_config = SettingsConfigDict(env_prefix="DVCBACKEND__")
    DATA_DIR: Path = Path("./data")
    ENCAPSULATE_ENV: bool = True


class DvcBackend(Backend):
    """'Adapter' which creates DVC yamls."""

    def __init__(
        self,
        settings: DvcBackendSettings | None = None,
        executer: BaseStepExecutor = PrometheusStepExecutor,
    ) -> None:
        self.executor: type[BaseStepExecutor] = executer
        self.settings = settings if settings else DvcBackendSettings()
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
        output_path = self.settings.DATA_DIR / step.__class__.__name__
        cmd = wurzel.cli.generate_cli_call(
            step.__class__,
            inputs=outputs_of_deps,
            output=output_path,
            executor=self.executor,
            encapsulate_env=self.settings.ENCAPSULATE_ENV,
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
