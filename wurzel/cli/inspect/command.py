# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""CLI command for inspecting step configurations and metadata."""

from __future__ import annotations

from typing import Annotated

import typer

from wurzel.cli.shared import complete_step_import
from wurzel.cli.shared.callbacks import step_callback

app = typer.Typer(
    no_args_is_help=True,
    help="Inspect step configurations, input/output types, and environment variables.",
)


@app.callback(invoke_without_command=True, help="Display information about a step")
def inspect(
    step: Annotated[
        str,
        typer.Argument(
            allow_dash=False,
            help="module path to step",
            autocompletion=complete_step_import,
        ),
    ],
    gen_env: Annotated[bool, typer.Option()] = False,
) -> None:
    """Inspect a step's configuration, input/output types, and environment variables."""
    from wurzel.cli.inspect import main as inspect_main  # pylint: disable=import-outside-toplevel

    # Validate and import the step (moved from callback to allow completion to work)
    step_class = step_callback(None, None, step)

    inspect_main(step_class, gen_env=gen_env)
