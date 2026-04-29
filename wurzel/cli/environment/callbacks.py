# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Callbacks for the 'env' command."""

from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    pass


def step_callback(_ctx: typer.Context, _param: typer.CallbackParam, import_path: str):
    """Converts a cli-str to a TypedStep.

    Args:
        _ctx (typer.Context):
        _param (typer.CallbackParam):
        import_path (str): user-typed string

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


def pipeline_callback(_ctx: typer.Context, _param: typer.CallbackParam, import_path: str):
    """Based on step_callback transform them to WZ pipeline elements."""
    from wurzel.core.meta import WZ  # pylint: disable=import-outside-toplevel

    step = step_callback(_ctx, _param, import_path)
    if not hasattr(step, "required_steps"):
        step = WZ(step)
    return step
