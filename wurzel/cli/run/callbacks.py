# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Callbacks for the 'run' command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    pass


def executer_callback(_ctx: typer.Context, _param: typer.CallbackParam, value: str | None):
    """Convert a cli-str to a Type[BaseStepExecutor] or Backend.

    Args:
        _ctx (typer.Context)
        _param (typer.CallbackParam):
        value (str | None): user typed string, or None when option is omitted

    Raises:
        typer.BadParameter: If user typed string does not correlate with a Executor or Backend

    Returns:
        Type[BaseStepExecutor] | None: {BaseStepExecutor, ArgoBackend, DvcBackend, None}

    """
    from wurzel.executors import (  # pylint: disable=import-outside-toplevel
        BaseStepExecutor,
        DvcBackend,  # pylint: disable=import-outside-toplevel
    )
    from wurzel.utils import HAS_HERA  # pylint: disable=import-outside-toplevel

    if value is None:
        return None
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
