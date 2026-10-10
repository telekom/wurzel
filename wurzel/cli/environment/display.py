# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Display utilities for the 'env' command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from wurzel.cli.environment import EnvValidationIssue, EnvVarRequirement

console = Console()


def _build_requirements_table(requirements: list[EnvVarRequirement]) -> Table:
    """Build a Rich table for environment variable requirements."""
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


def _build_missing_table(issues: list[EnvValidationIssue]) -> Table:
    """Build a Rich table for missing environment variables."""
    table = Table(title="Missing environment variables", header_style="bold red")
    table.add_column("ENV VAR", style="cyan", overflow="fold")
    table.add_column("MESSAGE", overflow="fold")
    for issue in issues:
        table.add_row(issue.env_var, issue.message)
    return table


def _print_requirements(requirements: list[EnvVarRequirement]) -> None:
    """Print environment variable requirements as table or text."""
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


def _print_missing(issues: list[EnvValidationIssue]) -> None:
    """Print missing environment variables as table or text."""
    if console.is_terminal:
        console.print(_build_missing_table(issues))
        return

    lines = ["Missing environment variables:"]
    for issue in issues:
        lines.append(f"- {issue.env_var}: {issue.message}")
    typer.echo("\n".join(lines))
