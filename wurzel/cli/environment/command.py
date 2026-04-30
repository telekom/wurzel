# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""CLI command for managing environment variables for pipelines."""

from __future__ import annotations

import os
from typing import Annotated

import typer
from rich.console import Console

from wurzel.cli.shared import complete_step_import, run_with_progress

app = typer.Typer(
    no_args_is_help=True,
    help="Inspect or validate environment variables for a pipeline.",
)

console = Console()


@app.callback(invoke_without_command=True, help="Inspect or validate environment variables for a pipeline")
def env(
    pipeline: Annotated[
        str,
        typer.Argument(
            allow_dash=False,
            help="module path to step or pipeline",
            autocompletion=complete_step_import,
        ),
    ],
    include_optional: Annotated[
        bool,
        typer.Option("--include-optional/--only-required", help="display optional variables as well"),
    ] = True,
    gen_env: Annotated[
        bool,
        typer.Option("--gen-env", help="emit .env content instead of a table"),
    ] = False,
    check: Annotated[
        bool,
        typer.Option("--check", help="validate that required env vars are set"),
    ] = False,
    allow_extra_fields: Annotated[
        bool,
        typer.Option("--allow-extra-fields", help="allow unknown settings when validating"),
    ] = False,
) -> None:
    """Inspect or validate pipeline environment configuration."""
    # Lazy imports to avoid circular dependency
    from wurzel.cli.environment.display import (  # pylint: disable=import-outside-toplevel
        _print_missing,
        _print_requirements,
    )
    from wurzel.cli.environment.pipeline_loading import _load_requirements  # pylint: disable=import-outside-toplevel
    from wurzel.cli.environment.requirements import (  # pylint: disable=import-outside-toplevel
        format_env_snippet,
        validate_env_vars,
    )

    pipeline_obj, requirements, to_display = run_with_progress(
        "Collecting step settings...",
        lambda: _load_requirements(pipeline, include_optional),
    )

    if check:
        issues = run_with_progress(
            "Validating environment variables...",
            lambda: validate_env_vars(pipeline_obj, allow_extra_fields=allow_extra_fields),
        )
        if not issues:
            console.print("[green]All required environment variables are set.[/green]")
            return
        _print_missing(issues)
        console.print("[yellow]Hint: run 'wurzel env --gen-env <pipeline>' to see the expected values.[/yellow]")
        raise typer.Exit(code=1)

    if not requirements:
        console.print("[green]Pipeline does not require any environment variables.[/green]")
        return

    if not to_display:
        console.print("[yellow]Pipeline has no required environment variables.[/yellow]")
        return

    if gen_env:
        typer.echo(format_env_snippet(to_display, current_env=os.environ))
        return

    _print_requirements(to_display)
