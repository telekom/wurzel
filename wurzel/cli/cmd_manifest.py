# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""CLI commands for working with pipeline manifests."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    no_args_is_help=True,
    help="Generate and validate Wurzel pipeline manifests.",
)


@app.command("validate")
def validate_manifest(
    manifest_path: Annotated[Path, typer.Argument(help="Path to the pipeline manifest YAML file.")],
) -> None:
    """Validate a pipeline manifest file and report all errors."""
    from wurzel.manifest.loader import ManifestLoader  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
    from wurzel.manifest.validator import ManifestValidator  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    try:
        manifest = ManifestLoader.load(manifest_path)
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    except Exception as exc:  # pylint: disable=broad-except
        typer.echo(f"Schema error: {exc}", err=True)
        raise typer.Exit(1) from exc

    validator = ManifestValidator(manifest)
    errors: list[str] = []
    errors.extend(validator.validate_step_refs())
    errors.extend(validator.validate_no_cycles())
    errors.extend(validator.validate_class_paths())
    errors.extend(validator.validate_middleware_names())

    if errors:
        typer.echo("Validation failed:\n", err=True)
        for error in errors:
            typer.echo(f"  - {error}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Manifest '{manifest_path}' is valid.")


@app.command("generate")
def generate_manifest(
    manifest_path: Annotated[Path, typer.Argument(help="Path to the pipeline manifest YAML file.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path for the generated artifact."),
    ] = None,
) -> None:
    """Generate a backend artifact (dvc.yaml or Argo Workflow YAML) from a manifest."""
    from wurzel.manifest.generator import ManifestGenerator  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
    from wurzel.manifest.loader import ManifestLoader  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    try:
        manifest = ManifestLoader.load(manifest_path)
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    except Exception as exc:  # pylint: disable=broad-except
        typer.echo(f"Schema error: {exc}", err=True)
        raise typer.Exit(1) from exc

    backend = manifest.spec.backend
    _default_artifact_names: dict[str, str] = {
        "dvc": "dvc.yaml",
        "argo": "workflow.yaml",
    }
    default_name = _default_artifact_names.get(backend, f"{backend}.yaml")
    out_path = output or (manifest_path.parent / default_name)

    try:
        ManifestGenerator(manifest).generate(out_path)
    except Exception as exc:  # pylint: disable=broad-except
        typer.echo(f"Generation error: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"Generated '{out_path}'.")
