# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""CLI Entry."""

from __future__ import annotations

import logging
import logging.config
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, cast

import typer
from rich.console import Console

# Import from command modules
from wurzel.cli.env import (
    _load_requirements,
    _print_missing,
    _print_requirements,
)
from wurzel.cli.generate import (
    backend_callback,
    get_available_backends,
    pipeline_callback,
)
from wurzel.cli.run import executer_callback, step_callback
from wurzel.cli.shared import (
    complete_step_import,
    run_with_progress,
    update_log_level,
)

app = typer.Typer(
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Track whether command groups have been initialized
_COMMAND_GROUPS_INITIALIZED = False


def _setup_command_groups():
    """Lazy initialization of command groups (deferred to first use)."""
    global _COMMAND_GROUPS_INITIALIZED  # pylint: disable=global-statement
    if _COMMAND_GROUPS_INITIALIZED:
        return
    _COMMAND_GROUPS_INITIALIZED = True

    # Import and add the middlewares command group (lazy)
    from wurzel.cli import (  # pylint: disable=import-outside-toplevel
        cmd_manifest,
        cmd_middlewares,
    )

    app.add_typer(cmd_middlewares.app, name="middlewares")
    app.add_typer(cmd_manifest.app, name="manifest")


# Initialize command groups at module import time
_setup_command_groups()


# Lazy loading of AST helpers via module-level __getattr__
_ast_helpers_cache = {}


def __getattr__(name: str):  # pylint: disable=too-many-return-statements
    """Lazily load AST helpers when accessed directly from this module."""
    if name == "_check_if_typed_step":
        if name not in _ast_helpers_cache:
            from wurzel.core.meta.ast_steps import (  # pylint: disable=import-outside-toplevel
                check_if_typed_step,
            )

            _ast_helpers_cache[name] = check_if_typed_step
        return _ast_helpers_cache[name]
    if name == "_build_module_path":
        if name not in _ast_helpers_cache:
            from wurzel.core.meta.ast_steps import (  # pylint: disable=import-outside-toplevel
                build_module_path,
            )

            _ast_helpers_cache[name] = build_module_path
        return _ast_helpers_cache[name]
    if name == "_process_python_file":
        if name not in _ast_helpers_cache:
            from wurzel.cli.shared.autocompletion import (  # pylint: disable=import-outside-toplevel
                _process_python_file,
            )

            _ast_helpers_cache[name] = _process_python_file
        return _ast_helpers_cache[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


log = logging.getLogger(__name__)
console = Console()


if TYPE_CHECKING:  # pragma: no cover - only for typing
    pass


@app.command(no_args_is_help=True, help="Run a step")
# pylint: disable-next=dangerous-default-value,too-many-positional-arguments
def run(
    step: Annotated[
        str,
        typer.Argument(
            allow_dash=False,
            help="module path to step",
            autocompletion=complete_step_import,
        ),
    ],
    output_path: Annotated[
        Path,
        typer.Option("-o", "--output", file_okay=False, help="Folder with outputs"),
    ] = Path(f"<step-name>-{datetime.now().isoformat(timespec='milliseconds')}"),
    input_folders: Annotated[
        list[Path],
        typer.Option(
            "-i",
            "--inputs",
            help="input folders",
            file_okay=False,
            exists=True,
        ),
    ] = [],
    executor: Annotated[
        str,
        typer.Option(
            # "",
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
):
    """Run."""
    from wurzel.cli.cmd_run import main as cmd_run  # pylint: disable=import-outside-toplevel

    # Validate and import the step (moved from callback to allow completion to work)
    step_class = step_callback(None, None, step)

    output_path = Path(str(output_path.absolute()).replace("<step-name>", step_class.__name__))
    log.debug(
        "executing run",
        extra={
            "parsed_args": {
                "step": step_class,
                "output_path": output_path,
                "input_folders": input_folders,
                "executor": executor,
                "middlewares": middlewares,
                "encapsulate_env": encapsulate_env,
            }
        },
    )
    return cmd_run(step_class, output_path, input_folders, executor, encapsulate_env, middlewares)


@app.command("inspect", no_args_is_help=True, help="Display information about a step")
def inspekt(
    step: Annotated[
        str,
        typer.Argument(
            allow_dash=False,
            help="module path to step",
            autocompletion=complete_step_import,
        ),
    ],
    gen_env: Annotated[bool, typer.Option()] = False,
):
    """Inspect."""
    from wurzel.cli.cmd_inspect import main as cmd_inspect  # pylint: disable=import-outside-toplevel

    # Validate and import the step (moved from callback to allow completion to work)
    step_class = step_callback(None, None, step)

    return cmd_inspect(step_class, gen_env)


# Env helpers -----------------------------------------------------------------


@app.command("env", help="Inspect or validate environment variables for a pipeline")
def env_cmd(
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
):
    """Inspect or validate pipeline env configuration."""
    from wurzel.cli.cmd_env import format_env_snippet, validate_env_vars  # pylint: disable=import-outside-toplevel

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


@app.command(help="generate a pipeline")
# pylint: disable-next=dangerous-default-value
def generate(  # pylint: disable=too-many-positional-arguments
    pipeline: Annotated[
        str | None,
        typer.Argument(
            allow_dash=False,
            help="module path to step or pipeline(which is a chained step)",
            autocompletion=complete_step_import,
        ),
    ] = None,
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
            callback=executer_callback,
            autocompletion=lambda: ["BaseStepExecutor", "PrometheusStepExecutor"],
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
):
    """Generate pipeline or list available backends."""
    if list_backends:
        backends = get_available_backends()
        print("Available backends:")  # noqa: T201
        for backend_name in backends:
            print(f"  - {backend_name}")  # noqa: T201
        return None

    if pipeline is None:
        raise typer.BadParameter("pipeline argument is required when not using --list-backends")

    # Process pipeline and backend
    pipeline_obj = pipeline_callback(None, None, pipeline)
    backend_obj = backend_callback(None, None, backend)

    from wurzel.cli.cmd_generate import main as cmd_generate  # pylint: disable=import-outside-toplevel
    from wurzel.executors.backend import Backend  # pylint: disable=import-outside-toplevel
    from wurzel.executors.backend.values import ValuesFileError  # pylint: disable=import-outside-toplevel

    log.debug(
        "generate pipeline",
        extra={
            "parsed_args": {
                "pipeline": pipeline_obj,
                "backend": backend_obj,
                "values": values,
                "pipeline_name": pipeline_name,
                "output": output,
                "executor": executor,
            }
        },
    )
    try:
        rendered = cmd_generate(
            pipeline_obj,
            backend=cast(type[Backend], backend_obj),
            values=values or [],
            pipeline_name=pipeline_name,
            output=output,
            executor=executor,
        )
    except ValuesFileError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if output is None:
        print(rendered)  # noqa: T201
    return None


@app.callback()
def main_args(
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            autocompletion=lambda: ["CRITICAL", "FATAL", "ERROR", "WARN", "INFO", "DEBUG"],
        ),
    ] = "INFO",
):
    """Global settings, main."""
    from wurzel.core.logging import get_logging_dict_config  # pylint: disable=import-outside-toplevel

    if not os.isatty(1):
        # typer.core.rich = None  # This may not be available in all typer versions
        logging.config.dictConfig(get_logging_dict_config(log_level, "wurzel.core.logging.JsonStringFormatter"))
        app.pretty_exceptions_enable = False
        app.pretty_exceptions_show_locals = False
    else:
        # Interactive Session
        update_log_level(log_level)
        app.pretty_exceptions_enable = True
        app.pretty_exceptions_show_locals = True
        app.pretty_exceptions_short = not verbose


def main():
    """Main."""
    sys.path.append(os.getcwd())  # needed fo find the files relative to cwd
    app()
