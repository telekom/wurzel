# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Callbacks for the 'env' command."""

from __future__ import annotations

import typer

from wurzel.cli.shared.callbacks import step_callback


def pipeline_callback(_ctx: typer.Context, _param: typer.CallbackParam, import_path: str):
    """Based on step_callback transform them to WZ pipeline elements."""
    from wurzel.core.meta import WZ  # pylint: disable=import-outside-toplevel

    step = step_callback(_ctx, _param, import_path)
    if not hasattr(step, "required_steps"):
        step = WZ(step)
    return step


__all__ = ["step_callback", "pipeline_callback"]
