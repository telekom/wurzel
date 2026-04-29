# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Shell completion installation for Wurzel CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    no_args_is_help=True,
    help="Manage shell completion for wurzel CLI.",
)


@app.command()
def install(
    shell: Annotated[
        str,
        typer.Option(
            "--shell",
            "-s",
            help="Shell to install completion for (bash, zsh, fish, powershell)",
        ),
    ] = "zsh",
) -> None:
    """Install shell completion for wurzel CLI.

    Supports bash, zsh, fish, and powershell.

    Examples:
        wurzel completion install --shell zsh
        wurzel completion install --shell bash
    """
    shell_lower = shell.lower()

    if shell_lower == "zsh":
        _install_zsh_completion()
    elif shell_lower == "bash":
        _install_bash_completion()
    elif shell_lower == "fish":
        _install_fish_completion()
    elif shell_lower == "powershell":
        _install_powershell_completion()
    else:
        typer.echo(f"Unsupported shell: {shell}", err=True)
        raise typer.Exit(1)


@app.command()
def uninstall(
    shell: Annotated[
        str,
        typer.Option(
            "--shell",
            "-s",
            help="Shell to uninstall completion for",
        ),
    ] = "zsh",
) -> None:
    """Uninstall shell completion for wurzel CLI."""
    shell_lower = shell.lower()

    if shell_lower == "zsh":
        _uninstall_zsh_completion()
    elif shell_lower == "bash":
        _uninstall_bash_completion()
    elif shell_lower == "fish":
        _uninstall_fish_completion()
    elif shell_lower == "powershell":
        _uninstall_powershell_completion()
    else:
        typer.echo(f"Unsupported shell: {shell}", err=True)
        raise typer.Exit(1)


def _install_zsh_completion() -> None:
    """Install zsh completion."""
    home = Path.home()
    zsh_completion_dir = home / ".zsh" / "completions"
    zsh_completion_dir.mkdir(parents=True, exist_ok=True)

    completion_file = zsh_completion_dir / "_wurzel"

    # Generate zsh completion script
    completion_script = _generate_zsh_completion()
    completion_file.write_text(completion_script)

    typer.echo(f"✓ Zsh completion installed to {completion_file}")
    typer.echo("  Add this to your ~/.zshrc if not already present:")
    typer.echo(f"  fpath=({zsh_completion_dir} $fpath)")
    typer.echo("  autoload -U compinit && compinit")


def _install_bash_completion() -> None:
    """Install bash completion."""
    home = Path.home()
    bash_completion_dir = home / ".bash_completion.d"
    bash_completion_dir.mkdir(parents=True, exist_ok=True)

    completion_file = bash_completion_dir / "wurzel"
    completion_script = _generate_bash_completion()
    completion_file.write_text(completion_script)

    typer.echo(f"✓ Bash completion installed to {completion_file}")
    typer.echo("  Add this to your ~/.bashrc if not already present:")
    typer.echo(f"  source {completion_file}")


def _install_fish_completion() -> None:
    """Install fish completion."""
    home = Path.home()
    fish_completion_dir = home / ".config" / "fish" / "completions"
    fish_completion_dir.mkdir(parents=True, exist_ok=True)

    completion_file = fish_completion_dir / "wurzel.fish"
    completion_script = _generate_fish_completion()
    completion_file.write_text(completion_script)

    typer.echo(f"✓ Fish completion installed to {completion_file}")


def _install_powershell_completion() -> None:
    """Install PowerShell completion."""
    # PowerShell completion is more complex; provide instructions
    typer.echo("PowerShell completion installation:")
    typer.echo("1. Find your PowerShell profile location:")
    typer.echo("   $PROFILE")
    typer.echo("2. Add the following to your profile:")
    typer.echo("   Register-ArgumentCompleter -Native -CommandName wurzel -ScriptBlock {")
    typer.echo("       param($wordToComplete, $commandAst, $cursorPosition)")
    typer.echo('       $Local:word = $wordToComplete.Replace("\\"","\\`\\"") ')
    typer.echo("       $Local:completions = @()")
    typer.echo("       wurzel completion powershell-script | ForEach-Object { $Local:completions += $_ }")
    typer.echo('       $Local:completions | Where-Object { $_ -like "$word*" } |')
    typer.echo('       ForEach-Object { [System.Management.Automation.CompletionResult]::new($_, $_, "ParameterValue", $_) }')
    typer.echo("   }")


def _uninstall_zsh_completion() -> None:
    """Uninstall zsh completion."""
    home = Path.home()
    completion_file = home / ".zsh" / "completions" / "_wurzel"
    if completion_file.exists():
        completion_file.unlink()
        typer.echo(f"✓ Zsh completion uninstalled from {completion_file}")
    else:
        typer.echo("Zsh completion not found")


def _uninstall_bash_completion() -> None:
    """Uninstall bash completion."""
    home = Path.home()
    completion_file = home / ".bash_completion.d" / "wurzel"
    if completion_file.exists():
        completion_file.unlink()
        typer.echo(f"✓ Bash completion uninstalled from {completion_file}")
    else:
        typer.echo("Bash completion not found")


def _uninstall_fish_completion() -> None:
    """Uninstall fish completion."""
    home = Path.home()
    completion_file = home / ".config" / "fish" / "completions" / "wurzel.fish"
    if completion_file.exists():
        completion_file.unlink()
        typer.echo(f"✓ Fish completion uninstalled from {completion_file}")
    else:
        typer.echo("Fish completion not found")


def _uninstall_powershell_completion() -> None:
    """Uninstall PowerShell completion."""
    typer.echo("PowerShell completion removal:")
    typer.echo("1. Edit your PowerShell profile:")
    typer.echo("   $PROFILE")
    typer.echo("2. Remove the Register-ArgumentCompleter block for wurzel")


def _generate_zsh_completion() -> str:
    """Generate zsh completion script."""
    # Dynamically get commands from CLI app
    from wurzel.cli._main import app as cli_app

    # Extract commands from the Typer/Click app
    commands_list = []
    if hasattr(cli_app, "registered_commands"):
        for cmd_info in cli_app.registered_commands:
            cmd_name = cmd_info[0]
            cmd_obj = cmd_info[1]
            help_text = (cmd_obj.help or "").split("\n")[0] if cmd_obj else ""
            commands_list.append(f'        "{cmd_name}:{help_text}"')
    else:
        # Fallback: try to get from the Click group
        try:
            click_app = cli_app
            if hasattr(click_app, "commands"):
                for cmd_name, cmd_obj in click_app.commands.items():
                    help_text = (cmd_obj.help or "").split("\n")[0] if cmd_obj else ""
                    commands_list.append(f'        "{cmd_name}:{help_text}"')
        except Exception:
            pass

    if not commands_list:
        # Hardcoded fallback with all commands
        commands_list = [
            '        "run:Run a step"',
            '        "inspect:Display information about a step"',
            '        "generate:Generate a pipeline artifact"',
            '        "env:Inspect or validate environment variables"',
            '        "completion:Manage shell completion"',
            '        "middlewares:Manage and inspect middlewares"',
            '        "manifest:Generate and validate Wurzel pipeline manifests"',
        ]

    commands_str = "\n".join(commands_list)

    # This is a zsh completion that calls wurzel for step suggestions
    return f"""#compdef wurzel

_wurzel() {{
    local -a commands
    local -a arguments
    local cmd state

    commands=(
{commands_str}
    )

    _arguments -C \\
        "1: :{{_describe 'command' commands}}" \\
        "*::args:->args"

    case $state in
        args)
            case $words[2] in
                run|generate|inspect|env)
                    # For step completion, use dynamic completion
                    _values "step" $(python -c "from wurzel.cli.shared import complete_step_import; steps = complete_step_import(''); print(' '.join(steps[:50]))" 2>/dev/null)
                    ;;
            esac
            ;;
    esac
}}

_wurzel
"""


def _generate_bash_completion() -> str:
    """Generate bash completion script."""
    return """#!/bin/bash

_wurzel_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # All available commands in the CLI
    commands="run inspect generate env completion middlewares manifest"

    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$commands" -- ${cur}) )
    else
        case "${COMP_WORDS[1]}" in
            run|generate|inspect|env)
                # For step completion, try to use Python completion function
                steps=$(python -c "from wurzel.cli.shared import complete_step_import; print(' '.join(complete_step_import('')))" 2>/dev/null)
                COMPREPLY=( $(compgen -W "$steps" -- ${cur}) )
                ;;
        esac
    fi

    return 0
}

complete -o bashdefault -o default -o nospace -F _wurzel_completion wurzel
"""


def _generate_fish_completion() -> str:
    """Generate fish completion script."""
    return """#!/usr/bin/env fish

# Wurzel CLI completion for fish shell

# Main commands
complete -c wurzel -f -n "__fish_use_subcommand_from_list run inspect generate env completion middlewares manifest"

# run command
complete -c wurzel -f -n "__fish_seen_subcommand_from run" -d "Run a step"

# inspect command
complete -c wurzel -f -n "__fish_seen_subcommand_from inspect" -d "Display information about a step"

# generate command
complete -c wurzel -f -n "__fish_seen_subcommand_from generate" -d "Generate a pipeline artifact"

# env command
complete -c wurzel -f -n "__fish_seen_subcommand_from env" -d "Inspect or validate environment variables"

# completion command
complete -c wurzel -f -n "__fish_seen_subcommand_from completion" -d "Manage shell completion"

# middlewares command
complete -c wurzel -f -n "__fish_seen_subcommand_from middlewares" -d "Manage and inspect middlewares"

# manifest command
complete -c wurzel -f -n "__fish_seen_subcommand_from manifest" -d "Generate and validate pipeline manifests"
"""
