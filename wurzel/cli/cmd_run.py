# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from typing import Type
from pathlib import Path
from wurzel import TypedStep


def main(
    step: Type[TypedStep],
    output_path: Path,
    input_folders: set[Path],
    executor_str_value: str,
    encapsulate_env=True,
):
    """Execute"""
    executor = executor_str_value
    with executor(dont_encapsulate=not encapsulate_env) as ex:
        ex(step, input_folders, output_path)
