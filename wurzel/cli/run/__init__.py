# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Run command module for executing steps and pipelines."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from wurzel.cli.shared.callbacks import step_callback  # pylint: disable=unused-import

from .callbacks import executer_callback

if TYPE_CHECKING:
    from wurzel.core import TypedStep


def main(  # pylint: disable=too-many-positional-arguments
    step: type[TypedStep[Any, Any, Any]],
    output_path: Path,
    input_folders: set[Path],
    executor_str_value: Any,  # Executor instance  # noqa: ANN401
    encapsulate_env: bool = True,
    middlewares: str = "",
):
    """Execute a step or pipeline.

    Args:
        step: The step or pipeline class to execute
        output_path: Output directory for results
        input_folders: Set of input folder paths
        executor_str_value: The executor instance to use
        encapsulate_env: Whether to encapsulate environment variables
        middlewares: Comma-separated middleware names
    """
    # Parse middlewares if provided
    middleware_list = None
    if middlewares:
        middleware_list = [m.strip() for m in middlewares.split(",") if m.strip()]

    with executor_str_value(
        dont_encapsulate=not encapsulate_env,
        middlewares=middleware_list,
        load_middlewares_from_env=not middleware_list,  # Only load from env if not explicitly set
    ) as ex:
        ex(step, input_folders, output_path)


__all__ = ["executer_callback", "step_callback", "main"]
