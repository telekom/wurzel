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
    """Internal representation of a DVC pipeline stage.

    This dictionary maps directly to the format used in `dvc.yaml` for each stage.

    Fields:
        cmd (str): The command to execute this step.
        deps (list[str]): File paths that are inputs/dependencies to this step.
        outs (list[str]): Output file paths generated by this step.
        always_changed (bool): Indicates if this step should always re-run (typically True for leaf steps).
    """

    cmd: str
    deps: list[str]
    outs: list[str]
    always_changed: bool


class DvcBackendSettings(BaseSettings):
    """Settings object for DVC backend configuration, injectable via environment variables.

    Environment Variables:
        - DVCBACKEND__DATA_DIR: Directory path to place generated output artifacts.
        - DVCBACKEND__ENCAPSULATE_ENV: Whether to encapsulate the environment (True/False).

    Attributes:
        DATA_DIR (Path): Output directory for generated step artifacts.
        ENCAPSULATE_ENV (bool): Flag to determine if environment encapsulation is used in CLI generation.

    """

    model_config = SettingsConfigDict(env_prefix="DVCBACKEND__")
    DATA_DIR: Path = Path("./data")
    ENCAPSULATE_ENV: bool = True


class DvcBackend(Backend):
    """DVC-specific backend implementation for the Wurzel abstraction layer.

    This adapter generates DVC-compatible `dvc.yaml` files from typed step definitions.
    It recursively resolves all step dependencies and constructs CLI commands for DVC execution.

    Args:
        settings (DvcBackendSettings | None): Optional settings object; if not provided,
            defaults will be loaded from environment or defaults.
        executer (BaseStepExecutor): Executor class used to wrap the CLI call.

    """

    def __init__(
        self,
        settings: DvcBackendSettings | None = None,
        executer: type[BaseStepExecutor] = PrometheusStepExecutor,
    ) -> None:
        self.executor: type[BaseStepExecutor] = executer
        self.settings = settings if settings else DvcBackendSettings()
        super().__init__()

    def _generate_dict(
        self,
        step: TypedStep,
    ) -> dict[str, DvcDict]:
        """Recursively generates a dictionary representing a full DVC pipeline,
        including all dependencies of the given step.

        Each step is represented as a `stage` entry in the DVC pipeline, with corresponding
        `cmd`, `deps`, `outs`, and `always_changed` fields.

        Args:
            step (TypedStep): The root step from which to generate the pipeline DAG.

        Returns:
            dict[str, DvcDict]: A dictionary mapping step names to their DVC-compatible stage configurations.

        """
        result: dict[str, Any] = {}
        outputs_of_deps: list[Path] = []

        for o_step in step.required_steps:
            dep_result = self._generate_dict(o_step)
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
                "always_changed": step.is_leaf(),  # Forces re-run for leaf steps
            }
        }

    def generate_artifact(
        self,
        step: TypedStep,
    ) -> str:
        """Converts the full step graph into a valid `dvc.yaml` file content.

        Ensures all paths (in `outs` and `deps`) are converted to strings for YAML serialization.

        Args:
            step (TypedStep): Root step of the pipeline.

        Returns:
            str: A YAML string containing the full DVC pipeline definition.

        """
        data = self._generate_dict(step)

        # Convert all Path objects to strings for YAML compatibility
        for k in data:
            for key in ["outs", "deps"]:
                data[k][key] = [str(p) for p in data[k][key]]

        return yaml.dump({"stages": data})
