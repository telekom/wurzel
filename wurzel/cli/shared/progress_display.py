# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Progress display helper for CLI operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from rich.console import Console

T = TypeVar("T")
console = Console()


def run_with_progress(description: str, func: Callable[..., T]) -> T:
    """Run a function with a progress spinner in terminal mode."""
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
