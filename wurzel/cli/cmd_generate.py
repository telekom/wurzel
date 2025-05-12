# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from wurzel.adapters.dvc_adapter import Backend
from wurzel.step.typed_step import TypedStep
from wurzel.step_executor.base_executor import BaseStepExecutor
from wurzel.utils import create_model


def main(step: TypedStep, data_dir: Path, backend: Backend) -> str:
    """Generates the yaml for the given backend."""
    adapter: Backend = backend(data_dir)
    # validate the envs of the steps
    create_model(
        list(step.traverse()),
        allow_extra_fields=BaseStepExecutor.is_allow_extra_settings(),
    )()

    return adapter.generate_yaml(step)
