# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Optional, Type

from wurzel.adapters.dvc_adapter import Backend
from wurzel.step.typed_step import TypedStep


def main(step: Optional[Type[TypedStep]], data_dir: Path, backend: Backend):
    """
    Generates the yaml for the given backend
    """
    adapter: Backend = backend()
    adapter.generate_yaml(step, data_output_folder=data_dir)
