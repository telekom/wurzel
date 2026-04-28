# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Callbacks for the 'generate' command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    pass


def pipeline_callback(_ctx: typer.Context, _param: typer.CallbackParam, import_path: str):
    """Based on step_callback transform them to WZ pipeline elements."""
    from wurzel.cli.shared.callbacks import step_callback  # pylint: disable=import-outside-toplevel
    from wurzel.core.meta import WZ  # pylint: disable=import-outside-toplevel

    step = step_callback(_ctx, _param, import_path)
    if not hasattr(step, "required_steps"):
        step = WZ(step)
    return step


def backend_callback(_ctx: typer.Context, _param: typer.CallbackParam, backend: str):
    """Validates input and returns fitting backend. Case-insensitive."""
    from wurzel.cli.generate.backend_listing import get_available_backends  # pylint: disable=import-outside-toplevel
    from wurzel.executors.backend import get_backend_by_name  # pylint: disable=import-outside-toplevel

    backend_cls = get_backend_by_name(backend)
    if backend_cls is not None:
        return backend_cls

    available = get_available_backends()
    if backend.lower() == "argobackend":
        raise typer.BadParameter(f"Backend {backend} not supported. Choose from {', '.join(available)} or install wurzel[argo]")
    raise typer.BadParameter(f"Backend {backend} not supported. Choose from {', '.join(available)}")
