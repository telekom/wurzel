# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Middleware management commands."""

import inspect
from typing import Annotated

import typer

app = typer.Typer(
    no_args_is_help=True,
    help="Manage and inspect middlewares",
)


def middleware_name_autocomplete(incomplete: str) -> list[str]:
    """Autocomplete middleware names.

    Args:
        incomplete: The partial middleware name typed by the user

    Returns:
        List of matching middleware names
    """
    from wurzel.executors.middlewares import get_registry  # pylint: disable=import-outside-toplevel

    registry = get_registry()
    available = registry.list_available()
    return [name for name in available if name.startswith(incomplete.lower())]


@app.command("list", help="List all available middlewares")
def list_middlewares():
    """List all available middlewares with brief descriptions."""
    from wurzel.executors.middlewares import get_registry  # pylint: disable=import-outside-toplevel

    registry = get_registry()
    available_middlewares = registry.list_available()

    if not available_middlewares:
        typer.echo("No middlewares available.")
        return

    typer.echo("Available middlewares:\n")

    for middleware_name in sorted(available_middlewares):
        middleware_class = registry.get(middleware_name)
        if middleware_class:
            # Get the first line of the docstring as description
            doc = inspect.getdoc(middleware_class) or "No description available"
            first_line = doc.split("\n", maxsplit=1)[0]
            typer.echo(f"  {middleware_name:20s} {first_line}")
        else:
            typer.echo(f"  {middleware_name:20s} (Error loading middleware)")

    typer.echo("\nUse 'wurzel middlewares inspect <name>' for detailed information.")


@app.command("inspect", help="Display detailed information about a middleware")
def inspect_middleware(
    name: Annotated[
        str,
        typer.Argument(
            help="Name of the middleware to inspect",
            autocompletion=middleware_name_autocomplete,
        ),
    ],
):
    """Display detailed information about a specific middleware.

    Args:
        name: The name of the middleware to inspect
    """
    from wurzel.executors.middlewares import get_registry  # pylint: disable=import-outside-toplevel

    registry = get_registry()
    middleware_class = registry.get(name.lower())

    if not middleware_class:
        typer.secho(f"Error: Middleware '{name}' not found.", fg=typer.colors.RED, err=True)
        typer.echo(f"\nAvailable middlewares: {', '.join(sorted(registry.list_available()))}")
        raise typer.Exit(1)

    # Display middleware information
    typer.secho(f"\n{name.upper()} Middleware", fg=typer.colors.BRIGHT_CYAN, bold=True)
    typer.secho("=" * (len(name) + 11), fg=typer.colors.BRIGHT_CYAN)

    # Module and class info
    typer.echo(f"\nModule:  {middleware_class.__module__}")
    typer.echo(f"Class:   {middleware_class.__name__}")

    # Documentation
    doc = inspect.getdoc(middleware_class)
    if doc:
        typer.echo(f"\nDescription:\n{doc}\n")

    # Get settings class if available
    try:
        # Try to get settings from __init__ signature
        sig = inspect.signature(middleware_class.__init__)
        settings_class = None

        for param_name, param in sig.parameters.items():
            if param_name == "settings" and param.annotation != inspect.Parameter.empty:
                # Extract the settings class from Optional[SettingsClass]
                annotation = param.annotation
                if hasattr(annotation, "__args__"):
                    # Handle Optional[SettingsClass] which is Union[SettingsClass, None]
                    settings_class = annotation.__args__[0]
                else:
                    settings_class = annotation
                break

        if settings_class and hasattr(settings_class, "model_fields"):
            typer.secho("Configuration:", fg=typer.colors.BRIGHT_YELLOW, bold=True)
            typer.echo("Settings class: " + settings_class.__name__)
            typer.echo("\nAvailable settings:\n")

            # Display settings fields
            for field_name, field_info in settings_class.model_fields.items():
                default = field_info.default if field_info.default is not None else "None"
                description = field_info.description or "No description"
                typer.echo(f"  {field_name}")
                typer.echo(f"    Description: {description}")
                typer.echo(f"    Default:     {default}")
                typer.echo()
    except Exception as e:  # pylint: disable=broad-exception-caught
        typer.echo(f"  (Could not load configuration details: {e})")

    # Usage example
    typer.secho("Usage:", fg=typer.colors.BRIGHT_GREEN, bold=True)
    typer.echo("  # Via CLI:")
    typer.echo(f"  wurzel run --middlewares {name} <step>")
    typer.echo("\n  # Via environment:")
    typer.echo(f"  export MIDDLEWARES={name}")
    typer.echo("  wurzel run <step>")
    typer.echo("\n  # Via Python:")
    typer.echo("  from wurzel.executors import BaseStepExecutor")
    typer.echo(f"  with BaseStepExecutor(middlewares=['{name}']) as exc:")
    typer.echo("      exc(MyStep, inputs, output)")
    typer.echo()
