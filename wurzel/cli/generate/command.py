# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""CLI command for generating backend-specific YAML from pipelines."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .backend_listing import get_available_backends
from .callbacks import backend_callback, pipeline_callback

app = typer.Typer(
    help="Generate backend-specific YAML artifacts (dvc.yaml, Argo workflow YAML, etc.) from a pipeline.",
    context_settings={"allow_interspersed_args": True},
)


@app.callback(invoke_without_command=True, help="Generate a pipeline artifact")
def generate(
    pipeline: Annotated[
        str | None,
        typer.Argument(
            allow_dash=False,
            help="module path to step or pipeline (which is a chained step)",
        ),
    ] = None,
    *,
    backend: Annotated[
        str,
        typer.Option(
            "-b",
            "--backend",
            help="backend to use",
        ),
    ] = "DvcBackend",
    values: Annotated[
        list[Path] | None,
        typer.Option(
            "--values",
            "-f",
            help="YAML values file(s) merged in order (Helm-style)",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ] = None,
    pipeline_name: Annotated[
        str | None,
        typer.Option("--pipeline-name", help="pipeline name to render from the provided values files"),
    ] = None,
    executor: Annotated[
        str | None,
        typer.Option(
            "-e",
            "--executor",
            help="Step executor class for generated commands (overrides defaults and PROMETHEUS_GATEWAY for Argo)",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="write generated manifests to this file (stdout when omitted)",
            file_okay=True,
            dir_okay=False,
            writable=True,
            resolve_path=True,
        ),
    ] = None,
    list_backends: Annotated[
        bool,
        typer.Option(
            "--list-backends",
            help="List all available backends and exit",
        ),
    ] = False,
) -> None:
    """Generate pipeline artifact or list available backends."""
    from wurzel.cli.generate import main as generate_main  # pylint: disable=import-outside-toplevel

    if list_backends:
        backends = get_available_backends()
        typer.echo("Available backends:")
        for backend_name in backends:
            typer.echo(f"  - {backend_name}")
        return

    if pipeline is None:
        raise typer.BadParameter("pipeline argument is required when not using --list-backends")

    # Process pipeline and backend through callbacks
    pipeline_obj = pipeline_callback(None, None, pipeline)
    backend_obj = backend_callback(None, None, backend)

    # Parse executor if provided
    executor_obj = None
    if executor:
        from wurzel.cli.run import executer_callback  # pylint: disable=import-outside-toplevel

        executor_obj = executer_callback(None, None, executor)

    result = generate_main(pipeline_obj, backend_obj, values=values, pipeline_name=pipeline_name, output=output, executor=executor_obj)
    if output is None:
        typer.echo(result)
        return
    typer.echo(f"Generated '{output}'.")
