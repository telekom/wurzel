# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""CLI Entry."""

import importlib
import inspect
import logging
import logging.config
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, cast

import typer

app = typer.Typer(
    no_args_is_help=True,
)
log = logging.getLogger(__name__)


def executer_callback(_ctx: typer.Context, _param: typer.CallbackParam, value: str):
    """Convert a cli-str to a Type[BaseStepExecutor].

    Args:
        _ctx (typer.Context)
        _param (typer.CallbackParam):
        value (str): user typed string

    Raises:
        typer.BadParameter: If user typed string does not correlate with a Executor

    Returns:
        Type[BaseStepExecutor]: {BaseStepExecutor, PrometheusStepExecutor}

    """
    from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor  # pylint: disable=import-outside-toplevel

    if "BASESTEPEXECUTOR".startswith(value.upper()):
        return BaseStepExecutor
    if "PROMETHEUSSTEPEXECUTOR".startswith(value.upper()):
        return PrometheusStepExecutor
    raise typer.BadParameter(f"{value} is not a recognized executor")


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
    from wurzel.step import TypedStep  # pylint: disable=import-outside-toplevel

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
            # Handle cases like wurzel.step.TypedStep
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

    def scan_directory_for_typed_steps(search_path: Path, base_module: str = "") -> None:
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

        # First, scan Python files directly in the search path
        for py_file in search_path.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            _process_python_file(py_file, search_path, base_module, incomplete, hints)

        # Then scan top-level directories that might contain user steps
        for item in search_path.iterdir():
            if item.is_dir() and item.name not in exclude_dirs:
                # Only go 2 levels deep to avoid deep scanning
                for py_file in item.rglob("*.py"):
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

    import threading  # pylint: disable=import-outside-toplevel

    scan_threads = []

    def scan_wurzel():
        try:
            import wurzel  # pylint: disable=import-outside-toplevel

            wurzel_path = Path(wurzel.__file__).parent
            wurzel_steps_path = wurzel_path / "steps"
            wurzel_step_path = wurzel_path / "step"
            if wurzel_steps_path.exists():
                scan_directory_for_typed_steps(wurzel_steps_path, "wurzel.steps")
            if wurzel_step_path.exists():
                scan_directory_for_typed_steps(wurzel_step_path, "wurzel.step")
        except ImportError:
            pass

    def scan_current():
        try:
            current_dir = Path.cwd()
            scan_directory_for_typed_steps(current_dir)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def scan_installed():
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
                        scan_directory_for_typed_steps(pkg_path, pkg)
            elif incomplete in installed_pkgs:
                spec = find_spec(incomplete)
                if spec and spec.origin:
                    pkg_path = Path(spec.origin).parent
                    scan_directory_for_typed_steps(pkg_path, incomplete)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    # Start all scan threads
    scan_threads.append(threading.Thread(target=scan_wurzel))
    scan_threads.append(threading.Thread(target=scan_current))
    scan_threads.append(threading.Thread(target=scan_installed))
    for t in scan_threads:
        t.start()
    for t in scan_threads:
        t.join()

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
# pylint: disable-next=dangerous-default-value
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
            help="executor to use",
            callback=executer_callback,
            autocompletion=lambda: ["BaseStepExecutor", "PrometheusStepExecutor"],
        ),
    ] = "BaseStepExecutor",
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
                "encapsulate_env": encapsulate_env,
            }
        },
    )
    return cmd_run(step, output_path, input_folders, executor, encapsulate_env)


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


def backend_callback(_ctx: typer.Context, _param: typer.CallbackParam, backend: str):
    """Validates input and returns fitting backend. Currently always DVCBackend."""
    from wurzel.backend.backend_argo import ArgoBackend  # pylint: disable=import-outside-toplevel
    from wurzel.backend.backend_dvc import DvcBackend  # pylint: disable=import-outside-toplevel

    match backend:
        case DvcBackend.__name__:
            return DvcBackend
        case "ArgoBackend":
            from wurzel.utils import HAS_HERA  # pylint: disable=import-outside-toplevel
            if HAS_HERA:
                from wurzel.backend.backend_argo import ArgoBackend  # pylint: disable=import-outside-toplevel

                return ArgoBackend
            supported_backends = ["DvcBackend"]
            raise typer.BadParameter(
                f"Backend {backend} not supported. choose from {', '.join(supported_backends)} or install wurzel[argo]"
            )
        case _:
            supported_backends = ["DvcBackend"]
            if HAS_HERA:
                supported_backends.append("ArgoBackend")
            raise typer.BadParameter(f"Backend {backend} not supported. choose from {', '.join(supported_backends)}")


def pipeline_callback(_ctx: typer.Context, _param: typer.CallbackParam, import_path: str):
    """Based on step_callback transform them to WZ pipeline elements."""
    from wurzel.utils.meta_settings import WZ  # pylint: disable=import-outside-toplevel

    step = step_callback(_ctx, _param, import_path)
    if not hasattr(step, "required_steps"):
        step = WZ(step)
    return step


@app.command(no_args_is_help=True, help="generate a pipeline")
# pylint: disable-next=dangerous-default-value
def generate(
    pipeline: Annotated[
        str,
        typer.Argument(
            allow_dash=False,
            help="module path to step or pipeline(which is a chained step)",
            autocompletion=complete_step_import,
            callback=pipeline_callback,
        ),
    ],
    backend: Annotated[
        str,
        typer.Option(
            "-b",
            "--backend",
            callback=backend_callback,
            help="backend to use",
        ),
    ] = "DvcBackend",
):
    """Run."""
    from wurzel.backend.backend import Backend  # pylint: disable=import-outside-toplevel
    from wurzel.cli.cmd_generate import main as cmd_generate  # pylint: disable=import-outside-toplevel

    log.debug(
        "generate pipeline",
        extra={
            "parsed_args": {
                "pipeline": pipeline,
                "backend": backend,
            }
        },
    )
    return print(  # noqa: T201
        cmd_generate(
            pipeline,
            backend=cast(type[Backend], backend),
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
            autocompletion=lambda: ["CRITICAL", "FATAL", "ERROR", "WARN", "INFO"],
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
