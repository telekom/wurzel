# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""CLI program."""

import importlib.metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from wurzel.step import TypedStep
    from wurzel.step_executor import BaseStepExecutor

__all__ = ["generate_cli_call"]
try:
    __version__ = importlib.metadata.version("wurzel")
# pylint: disable-next=bare-except
except:  # noqa: E722
    __version__ = "dev"
__version_info__ = __version__.split(".")


def generate_cli_call(
    step_cls: "type[TypedStep]",
    inputs: "list[Path]",
    output: "Path",
    executor: "type[BaseStepExecutor] | None" = None,
    encapsulate_env: bool = True,
) -> str:
    """Generate the cli call to execute a given step with its
    inputs and output.

    Args:
        step_cls (type[TypedStep]): Step to execute
        inputs (list[Path]): list of Directories
        output (Path): Output Directory

    Returns:
        str: cmd

    """
    # Lazy import to avoid loading heavy dependencies at package import time
    from pathlib import Path  # pylint: disable=import-outside-toplevel

    # Ensure we have Path type available at runtime
    _ = Path

    # These imports are for runtime type checking if needed
    # from wurzel.step import TypedStep
    # from wurzel.step_executor import BaseStepExecutor

    if inputs:
        inputs_str = "-i " + " -i ".join(str(i) for i in inputs)
    else:
        inputs_str = ""
    return " ".join(
        [
            "wurzel run",
            f"{step_cls.__module__}:{step_cls.__qualname__}",
            "-o",
            str(output.absolute()),
            "" if executor is None else f"-e {executor.__qualname__}",
            inputs_str,
            "--encapsulate-env" if encapsulate_env else "--no-encapsulate-env",
        ]
    )
