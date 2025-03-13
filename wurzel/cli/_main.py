# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""CLI Entry"""

import os
import importlib
import inspect
from typing import Annotated
from pathlib import Path
import pkgutil
from datetime import datetime
import logging
import logging.config
import typer
import typer.core

from wurzel.utils.logging import get_logging_dict_config
from wurzel import TypedStep
from wurzel.steps import __all__ as all_steps
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor

from wurzel.cli.cmd_run import main as cmd_run
from wurzel.cli.cmd_inspect import main as cmd_inspect

app = typer.Typer(
    no_args_is_help=True,
)
log = logging.getLogger(__name__)
packages = [
    p
    for p in pkgutil.iter_modules()
    if p.ispkg and p.name.startswith(("steps", "wurzel"))
]


def executer_callback(_ctx: typer.Context, _param: typer.CallbackParam, value: str):
    """Convert a cli-str to a Type[BaseStepExecutor]

    Args:
        _ctx (typer.Context)
        _param (typer.CallbackParam):
        value (str): user typed string

    Raises:
        typer.BadParameter: If user typed string does not correlate with a Executor

    Returns:
        Type[BaseStepExecutor]: {BaseStepExecutor, PrometheusStepExecutor}
    """
    if "BASESTEPEXECUTOR".startswith(value.upper()):
        return BaseStepExecutor
    if "PROMETHEUSSTEPEXECUTOR".startswith(value.upper()):
        return PrometheusStepExecutor
    raise typer.BadParameter(f"{value} is not a recognized executor")


def step_callback(_ctx: typer.Context, _param: typer.CallbackParam, import_path: str):
    """Converts a cli-str to a TypedStep

    Args:
        _ctx (typer.Context):
        _param (typer.CallbackParam):
        path (str): user-typed string

    Raises:
        typer.BadParameter: import not possible

    Returns:
        Type[TypedStep]: <<step>>
    """
    try:
        if ":" in import_path:
            mod, kls = import_path.rsplit(":", 1)
        else:
            mod, kls = import_path.rsplit(".", 1)
        module = importlib.import_module(mod)
        step = getattr(module, kls)
        assert inspect.isclass(step) and issubclass(step, TypedStep)
    except ValueError as ve:
        raise typer.BadParameter(
            "Path is not in correct format, should be module.submodule.Step"
        ) from ve
    except ModuleNotFoundError as me:
        raise typer.BadParameter(f"Module '{mod}' could not be imported") from me
    except AttributeError as ae:
        raise typer.BadParameter(f"Class '{kls}' not in module {module}") from ae
    except AssertionError as ae:
        raise typer.BadParameter(f"Class '{kls}' not a TypedStep") from ae
    return step


def complete_step_import(_incomplete: str):
    """AutoComplete for steps
    Currently only supports library steps"""
    hints = [
        f"wurzel.steps.{step}"
        for step in all_steps
        if step.endswith("Step") and step != "TypedStep"
    ]
    return hints


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
    """run"""
    output_path = Path(output_path.as_posix().replace("<step-name>", step.__name__))
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
    """inspect"""
    return cmd_inspect(step, gen_env)


def update_log_level(log_level: str):
    """Fix for typer logs"""
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
    """global settings, main"""
    if not os.isatty(1):
        typer.core.rich = None
        logging.config.dictConfig(get_logging_dict_config(log_level))
        app.pretty_exceptions_enable = False
        app.pretty_exceptions_show_locals = False
    else:
        update_log_level(log_level)
        app.pretty_exceptions_enable = True
        app.pretty_exceptions_show_locals = True
        app.pretty_exceptions_short = not verbose


def main():
    """main"""
    app()
