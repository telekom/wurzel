# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from wurzel.backend.backend import Backend
    from wurzel.step.typed_step import TypedStep


def _resolve_backend_instance(
    backend: "type[Backend]",
    values: list[Path] | None,
    workflow: str | None,
) -> "Backend":
    from wurzel.backend.backend_argo import ArgoBackend  # pylint: disable=import-outside-toplevel

    if issubclass(backend, ArgoBackend):
        if values:
            return backend.from_values(values, workflow_name=workflow)  # type: ignore[call-arg]
        return backend()  # type: ignore[call-arg]
    return backend()


def _write_output(content: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def main(
    step: "TypedStep",
    backend: "type[Backend]",
    *,
    values: Iterable[Path] | None = None,
    workflow: str | None = None,
    output: Path | None = None,
) -> str:
    """Generate backend-specific YAML for a pipeline."""
    adapter = _resolve_backend_instance(backend, list(values or []), workflow)
    yaml_content = adapter.generate_artifact(step)

    if output:
        _write_output(yaml_content, output)

    return yaml_content
