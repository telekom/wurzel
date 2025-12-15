# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""CLI Entry."""

from __future__ import annotations

import importlib
import inspect
import logging
import logging.config
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Import and add the middlewares command group
# ruff: noqa: E402
from wurzel.cli import cmd_middlewares  # pylint: disable=wrong-import-position

app.add_typer(cmd_middlewares.app, name="middlewares")

log = logging.getLogger(__name__)
console = Console()


if TYPE_CHECKING:  # pragma: no cover - only for typing
    from wurzel.cli.cmd_env import EnvValidationIssue
    from wurzel.core import TypedStep


def executer_callback(_ctx: typer.Context, _param: typer.CallbackParam, value: str):
    """Convert a cli-str to a Type[BaseStepExecutor] or Backend.

    Args:
        _ctx (typer.Context)
        _param (typer.CallbackParam):
        value (str): user typed string

    Raises:
        typer.BadParameter: If user typed string does not correlate with a Executor or Backend

    Returns:
        Type[BaseStepExecutor]: {BaseStepExecutor, ArgoBackend, DvcBackend}

    """
    from wurzel.executors import (  # pylint: disable=import-outside-toplevel
        BaseStepExecutor,
        DvcBackend,  # pylint: disable=import-outside-toplevel
    )
    from wurzel.utils import HAS_HERA  # pylint: disable=import-outside-toplevel

    # Check for executors
    if "BASESTEPEXECUTOR".startswith(value.upper()):
        return BaseStepExecutor

    # Check for backends
    if "DVCBACKEND".startswith(value.upper()):
        return DvcBackend
    if "ARGOBACKEND".startswith(value.upper()):
        if HAS_HERA:
            from wurzel.executors import ArgoBackend  # pylint: disable=import-outside-toplevel

            return ArgoBackend
        raise typer.BadParameter("ArgoBackend requires wurzel[argo] to be installed")

    raise typer.BadParameter(f"{value} is not a recognized executor or backend")


def step_callback(_ctx: typer.Context, _param: typer.CallbackParam, import_path: str):
    """Converts a cli-str to a TypedStep.

    Args:
        _ctx (typer.Context):
        _param (typer.CallbackParam):
        path (str): user-typed string

    Raises:
        typer.BadParameter: import not possible

    Returns:
        Type[TypedStep]: <<step>>

    """
    from wurzel.core import TypedStep  # pylint: disable=import-outside-toplevel

    try:
        if ":" in import_path:
            mod, kls = import_path.rsplit(":", 1)
        else:
            mod, kls = import_path.rsplit(".", 1)
        module = importlib.import_module(mod)
        step = getattr(module, kls)
        assert (inspect.isclass(step) and issubclass(step, TypedStep)) or isinstance(step, TypedStep)
    except ValueError as ve:
        raise typer.BadParameter("Path is not in correct format, should be module.submodule.Step") from ve
    except ModuleNotFoundError as me:
        raise typer.BadParameter(f"Module '{mod}' could not be imported") from me
    except AttributeError as ae:
        raise typer.BadParameter(f"Class '{kls}' not in module {module}") from ae
    except AssertionError as ae:
        raise typer.BadParameter(f"Class '{kls}' not a TypedStep") from ae
    return step


def _ensure_pipeline_obj(pipeline: TypedStep | str):
    """Resolve pipeline argument to a WZ pipeline instance."""
    if isinstance(pipeline, str):
        return pipeline_callback(None, None, pipeline)
    return pipeline


def _load_requirements(pipeline: TypedStep | str, include_optional: bool):
    from wurzel.cli.cmd_env import collect_env_requirements  # pylint: disable=import-outside-toplevel

    pipeline_obj = _ensure_pipeline_obj(pipeline)
    requirements = collect_env_requirements(pipeline_obj)
    filtered = requirements if include_optional else [req for req in requirements if req.required]
    return pipeline_obj, requirements, filtered


def _build_requirements_table(requirements):
    table = Table(title="Environment variables", header_style="bold magenta")
    table.add_column("ENV VAR", style="cyan", overflow="fold")
    table.add_column("REQ", justify="center", style="bold")
    table.add_column("STEP", style="green")
    table.add_column("DEFAULT", overflow="fold")
    table.add_column("DESCRIPTION", overflow="fold")

    for req in requirements:
        default = req.default or "-"
        required_flag = "yes" if req.required else "no"
        table.add_row(req.env_var, required_flag, req.step_name, default, req.description or "-")
    return table


def _build_missing_table(issues: list[EnvValidationIssue]):
    table = Table(title="Missing environment variables", header_style="bold red")
    table.add_column("ENV VAR", style="cyan", overflow="fold")
    table.add_column("MESSAGE", overflow="fold")
    for issue in issues:
        table.add_row(issue.env_var, issue.message)
    return table


def _print_requirements(requirements):
    if console.is_terminal:
        console.print(_build_requirements_table(requirements))
        return

    lines = ["Environment variables"]
    for req in requirements:
        default = req.default or "-"
        required_flag = "required" if req.required else "optional"
        description = req.description or "-"
        lines.append(f"{req.env_var} ({required_flag}) step={req.step_name} default={default} desc={description}")
    typer.echo("\n".join(lines))


def _print_missing(issues: list[EnvValidationIssue]):
    if console.is_terminal:
        console.print(_build_missing_table(issues))
        return

    lines = ["Missing environment variables:"]
    for issue in issues:
        lines.append(f"- {issue.env_var}: {issue.message}")
    typer.echo("\n".join(lines))


def _process_python_file(py_file: Path, search_path: Path, base_module: str, incomplete: str, hints: list) -> None:
    """Process a single Python file to find TypedStep classes."""
    import ast  # pylint: disable=import-outside-toplevel

    try:
        # Fast AST parsing without executing code
        with open(py_file, encoding="utf-8") as f:
            content = f.read()

        # Quick regex check before AST parsing (even faster)
        if "TypedStep" not in content:
            return

        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _check_if_typed_step(node):
                # Create module path based on file location
                try:
                    module_path = _build_module_path(py_file, search_path, base_module)
                    full_name = f"{module_path}.{node.name}"
                    if full_name.startswith(incomplete):
                        hints.append(full_name)
                except ValueError:
                    # File is not relative to search_path, skip it
                    continue

    except (OSError, SyntaxError, UnicodeDecodeError):
        # Skip files that can't be parsed
        pass


def _check_if_typed_step(node) -> bool:
    """Check if a class node inherits from TypedStep."""
    import ast  # pylint: disable=import-outside-toplevel

    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "TypedStep":
            return True
        if isinstance(base, ast.Subscript):
            # Handle generic TypedStep like TypedStep[Input, Output, Settings]
            if isinstance(base.value, ast.Name) and base.value.id == "TypedStep":
                return True
            if isinstance(base.value, ast.Attribute) and base.value.attr == "TypedStep":
                return True
        if isinstance(base, ast.Attribute):
            # Handle cases like wurzel.core.TypedStep
            if base.attr == "TypedStep":
                return True
    return False


def _build_module_path(py_file: Path, search_path: Path, base_module: str) -> str:
    """Build module path from file location."""
    rel_path = py_file.relative_to(search_path)
    path_parts = list(rel_path.parts[:-1]) + [rel_path.stem]
    if base_module:
        # For wurzel built-in steps
        return f"{base_module}.{'.'.join(path_parts)}"
    # For user project steps - use relative path as module
    if path_parts:
        return ".".join(path_parts)
    return rel_path.stem


def complete_step_import(incomplete: str) -> list[str]:  # pylint: disable=too-many-statements
    """AutoComplete for steps - discover TypedStep classes from current project and wurzel."""
    hints: list[str] = []

    # Early optimization: If we have a specific prefix, we can limit scanning
    should_scan_wurzel = not incomplete or incomplete.startswith("wurzel")
    should_scan_current = not incomplete or not incomplete.startswith("wurzel")
    should_scan_installed = "." in incomplete and not incomplete.startswith("wurzel")

    def scan_directory_for_typed_steps(search_path: Path, base_module: str = "", max_files: int = 200) -> None:
        """Scan a directory for TypedStep classes and add them to hints."""
        if not search_path.exists():
            return

        # Directories to exclude from scanning (performance optimization)
        exclude_dirs = {
            ".venv",
            "venv",
            ".env",
            "env",
            "__pycache__",
            ".git",
            ".svn",
            ".hg",
            "node_modules",
            ".tox",
            ".pytest_cache",
            "build",
            "dist",
            ".egg-info",
            "site-packages",
            "tests",  # Skip test directories - unlikely to contain user steps
            "test",
            "testing",
            "docs",  # Skip documentation
            "doc",
        }

        files_processed = 0

        # First, scan Python files directly in the search path
        for py_file in search_path.glob("*.py"):
            if files_processed >= max_files:
                break
            if py_file.name == "__init__.py":
                continue
            _process_python_file(py_file, search_path, base_module, incomplete, hints)
            files_processed += 1

        # Then scan top-level directories that might contain user steps
        for item in search_path.iterdir():
            if files_processed >= max_files:
                break
            if item.is_dir() and item.name not in exclude_dirs:
                # Only go 2 levels deep to avoid deep scanning
                for py_file in item.rglob("*.py"):
                    if files_processed >= max_files:
                        break
                    if py_file.name == "__init__.py":
                        continue

                    # Check if file is in excluded directory
                    if any(exclude_dir in py_file.parts for exclude_dir in exclude_dirs):
                        continue

                    # Limit depth to 3 levels max
                    relative_parts = py_file.relative_to(search_path).parts
                    if len(relative_parts) > 3:
                        continue

                    _process_python_file(py_file, search_path, base_module, incomplete, hints)
                    files_processed += 1

    import threading  # pylint: disable=import-outside-toplevel

    scan_threads = []

    def scan_wurzel():
        if not should_scan_wurzel:
            return
        try:
            import wurzel  # pylint: disable=import-outside-toplevel

            wurzel_path = Path(wurzel.__file__).parent
            wurzel_steps_path = wurzel_path / "steps"
            wurzel_step_path = wurzel_path / "step"
            if wurzel_steps_path.exists():
                scan_directory_for_typed_steps(wurzel_steps_path, "wurzel.steps", max_files=100)
            if wurzel_step_path.exists():
                scan_directory_for_typed_steps(wurzel_step_path, "wurzel.step", max_files=50)
        except ImportError:
            pass

    def scan_current():
        if not should_scan_current:
            return
        try:
            current_dir = Path.cwd()
            scan_directory_for_typed_steps(current_dir, max_files=50)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def scan_installed():
        if not should_scan_installed:
            return
        try:
            from importlib.metadata import distributions  # pylint: disable=import-outside-toplevel
            from importlib.util import find_spec  # pylint: disable=import-outside-toplevel

            installed_pkgs = {dist.name for dist in distributions()}
            if "." in incomplete:
                pkg = incomplete.split(".")[0]
                if pkg in installed_pkgs:
                    spec = find_spec(pkg)
                    if spec and spec.origin:
                        pkg_path = Path(spec.origin).parent
                        scan_directory_for_typed_steps(pkg_path, pkg, max_files=50)
            elif incomplete in installed_pkgs:
                spec = find_spec(incomplete)
                if spec and spec.origin:
                    pkg_path = Path(spec.origin).parent
                    scan_directory_for_typed_steps(pkg_path, incomplete, max_files=50)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    # Start all scan threads (only those that are needed)
    if should_scan_wurzel:
        scan_threads.append(threading.Thread(target=scan_wurzel))
    if should_scan_current:
        scan_threads.append(threading.Thread(target=scan_current))
    if should_scan_installed:
        scan_threads.append(threading.Thread(target=scan_installed))

    for t in scan_threads:
        t.start()
    for t in scan_threads:
        t.join(timeout=1.0)  # Add timeout to prevent hanging

    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique_hints: list[str] = []
    for hint in hints:
        if hint not in seen:
            seen.add(hint)
            unique_hints.append(hint)

    logging.debug("found possible steps:", extra={"hints": unique_hints[:10]})  # Log first 10

    # Filter by incomplete prefix
    return [hint for hint in unique_hints if hint.startswith(incomplete)]


@app.command(no_args_is_help=True, help="Run a step")
# pylint: disable-next=dangerous-default-value,too-many-positional-arguments
def run(
    step: Annotated[
        str,
        typer.Argument(
            allow_dash=False,
            help="module path to step",
            autocompletion=complete_step_import,
            callback=step_callback,
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

    output_path = Path(str(output_path.absolute()).replace("<step-name>", step.__name__))
    log.debug(
        "executing run",
        extra={
            "parsed_args": {
                "step": step,
                "output_path": output_path,
                "input_folders": input_folders,
                "executor": executor,
                "middlewares": middlewares,
                "encapsulate_env": encapsulate_env,
            }
        },
    )
    return cmd_run(step, output_path, input_folders, executor, encapsulate_env, middlewares)


@app.command("inspect", no_args_is_help=True, help="Display information about a step")
def inspekt(
    step: Annotated[
        str,
        typer.Argument(
            allow_dash=False,
            help="module path to step",
            autocompletion=complete_step_import,
            callback=step_callback,
        ),
    ],
    gen_env: Annotated[bool, typer.Option()] = False,
):
    """Inspect."""
    from wurzel.cli.cmd_inspect import main as cmd_inspect  # pylint: disable=import-outside-toplevel

    return cmd_inspect(step, gen_env)


# Env helpers -----------------------------------------------------------------


def _run_with_progress(description: str, func):
    if not console.is_terminal:
        return func()

    from rich.progress import Progress, SpinnerColumn, TextColumn  # pylint: disable=import-outside-toplevel

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task(description=description, total=None)
        return func()


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

    pipeline_obj, requirements, to_display = _run_with_progress(
        "Collecting step settings...",
        lambda: _load_requirements(pipeline, include_optional),
    )

    if check:
        issues = _run_with_progress(
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


def get_available_backends() -> list[str]:
    """Get list of available backend names.

    Returns:
        list[str]: List of available backend names (e.g., ['DvcBackend', 'ArgoBackend'])
    """
    from wurzel.utils import HAS_HERA  # pylint: disable=import-outside-toplevel

    backends = ["DvcBackend"]
    if HAS_HERA:
        backends.append("ArgoBackend")
    return backends


def backend_callback(_ctx: typer.Context, _param: typer.CallbackParam, backend: str):
    """Validates input and returns fitting backend. Case-insensitive."""
    from wurzel.executors.backend.backend_dvc import DvcBackend  # pylint: disable=import-outside-toplevel

    backend_normalized = backend.lower()
    available_backends = get_available_backends()
    available_backends_lower = [b.lower() for b in available_backends]

    # Map normalized backend names to their classes
    if backend_normalized == "dvcbackend":
        if "dvcbackend" in available_backends_lower:
            return DvcBackend
    elif backend_normalized == "argobackend":
        if "argobackend" in available_backends_lower:
            from wurzel.executors.backend.backend_argo import ArgoBackend  # pylint: disable=import-outside-toplevel

            return ArgoBackend
        raise typer.BadParameter(f"Backend {backend} not supported. Choose from {', '.join(available_backends)} or install wurzel[argo]")

    raise typer.BadParameter(f"Backend {backend} not supported. Choose from {', '.join(available_backends)}")


def pipeline_callback(_ctx: typer.Context, _param: typer.CallbackParam, import_path: str):
    """Based on step_callback transform them to WZ pipeline elements."""
    from wurzel.utils.meta_settings import WZ  # pylint: disable=import-outside-toplevel

    step = step_callback(_ctx, _param, import_path)
    if not hasattr(step, "required_steps"):
        step = WZ(step)
    return step


@app.command(help="generate a pipeline")
# pylint: disable-next=dangerous-default-value
def generate(
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

    log.debug(
        "generate pipeline",
        extra={
            "parsed_args": {
                "pipeline": pipeline_obj,
                "backend": backend_obj,
            }
        },
    )
    return print(  # noqa: T201
        cmd_generate(
            pipeline_obj,
            backend=cast(type[Backend], backend_obj),
        )
    )


def update_log_level(log_level: str):
    """Fix for typer logs."""
    from wurzel.utils.logging import get_logging_dict_config  # pylint: disable=import-outside-toplevel

    log_config = get_logging_dict_config(log_level)
    log_config["formatters"]["default"] = {
        "()": "wurzel.cli.logger.WithExtraFormatter",
        "reduced": ["INFO"],
    }
    log_config["handlers"]["default"] = {
        "()": "rich.logging.RichHandler",
        "formatter": "default",
    }
    logging.config.dictConfig(log_config)


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
    from wurzel.utils.logging import get_logging_dict_config  # pylint: disable=import-outside-toplevel

    if not os.isatty(1):
        # typer.core.rich = None  # This may not be available in all typer versions
        logging.config.dictConfig(get_logging_dict_config(log_level, "wurzel.utils.logging.JsonStringFormatter"))
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
