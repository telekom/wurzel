# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""CLI command for executing steps in a pipeline."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from wurzel.cli.shared import complete_step_import
from wurzel.cli.shared.callbacks import step_callback

from .callbacks import executer_callback

app = typer.Typer(
    no_args_is_help=True,
    help="Execute a step or pipeline with the specified executor.",
)

log = logging.getLogger(__name__)


@app.callback(invoke_without_command=True, help="Run a step")
def run(
    step: Annotated[
        str,
        typer.Argument(
            allow_dash=False,
            help="module path to step",
            autocompletion=complete_step_import,
        ),
    ],
    *,
    output_path: Annotated[
        Path,
        typer.Option("-o", "--output", file_okay=False, help="Folder with outputs"),
    ] = Path(f"<step-name>-{datetime.now().isoformat(timespec='milliseconds')}"),
    input_folders: Annotated[
        list[Path] | None,
        typer.Option(
            "-i",
            "--inputs",
            help="input folders",
            file_okay=False,
            exists=True,
        ),
    ] = None,
    executor: Annotated[
        str,
        typer.Option(
            "-e",
            "--executor",
            help="executor or backend to use for execution",
            callback=executer_callback,
            autocompletion=lambda: ["BaseStepExecutor", "DvcBackend", "ArgoBackend"],
        ),
    ] = "BaseStepExecutor",
    middlewares: Annotated[
        str,
        typer.Option(
            "-m",
            "--middlewares",
            help="comma-separated list of middlewares to enable (e.g., 'prometheus')",
        ),
    ] = "",
    encapsulate_env: Annotated[bool, typer.Option()] = True,
) -> None:
    """Execute a step or pipeline."""
    from wurzel.cli.run import main as run_main  # pylint: disable=import-outside-toplevel

    # Validate and import the step (moved from callback to allow completion to work)
    step_class = step_callback(None, None, step)

    output_path = Path(str(output_path.absolute()).replace("<step-name>", step_class.__name__))
    # Handle None default for input_folders
    input_folders_set = set(input_folders) if input_folders else set()

    log.debug(
        "executing run",
        extra={
            "parsed_args": {
                "step": step_class,
                "output_path": output_path,
                "input_folders": input_folders_set,
                "executor": executor,
                "middlewares": middlewares,
                "encapsulate_env": encapsulate_env,
            }
        },
    )
    run_main(step_class, output_path, input_folders_set, executor, encapsulate_env, middlewares)
