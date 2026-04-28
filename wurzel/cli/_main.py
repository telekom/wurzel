# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""CLI Entry."""

from __future__ import annotations

import logging
import logging.config
import os
import sys
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console

# Import from command modules
from wurzel.cli.shared import (
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

    # Import and add command groups
    from wurzel.cli import cmd_manifest, cmd_middlewares  # pylint: disable=import-outside-toplevel
    from wurzel.cli.env.command import app as env_app  # pylint: disable=import-outside-toplevel
    from wurzel.cli.generate.command import app as generate_app  # pylint: disable=import-outside-toplevel
    from wurzel.cli.inspect.command import app as inspect_app  # pylint: disable=import-outside-toplevel
    from wurzel.cli.run.command import app as run_app  # pylint: disable=import-outside-toplevel

    app.add_typer(run_app, name="run")
    app.add_typer(inspect_app, name="inspect")
    app.add_typer(generate_app, name="generate")
    app.add_typer(env_app, name="env")
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
