# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from wurzel.step import TypedStep


def main(  # pylint: disable=too-many-positional-arguments
    step: "type[TypedStep[Any, Any, Any]]",
    output_path: Path,
    input_folders: set[Path],
    executor_str_value: Any,  # Executor instance  # noqa: ANN401
    encapsulate_env: bool = True,
    middlewares: str = "",
):
    """Execute."""
    # Lazy import to avoid loading heavy dependencies at import time
    # Note: executor_str_value should actually be the executor instance
    executor = executor_str_value

    # Parse middlewares if provided
    middleware_list = None
    if middlewares:
        middleware_list = [m.strip() for m in middlewares.split(",") if m.strip()]

    with executor(
        dont_encapsulate=not encapsulate_env,
        middlewares=middleware_list,
        load_middlewares_from_env=not middleware_list,  # Only load from env if not explicitly set
    ) as ex:
        ex(step, input_folders, output_path)
