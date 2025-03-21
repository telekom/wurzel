# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from wurzel.adapters.dvc_adapter import Backend
from wurzel.step.typed_step import TypedStep


def main(step: TypedStep, data_dir: Path, backend: Backend) -> str:
    """
    Generates the yaml for the given backend
    """

    adapter: Backend = backend(data_dir)
    return adapter.generate_yaml(step)
