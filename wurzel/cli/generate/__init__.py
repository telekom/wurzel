# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Generate command module for creating backend-specific YAML artifacts."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, cast

from .backend_listing import get_available_backends
from .callbacks import backend_callback, pipeline_callback

if TYPE_CHECKING:
    from wurzel.core.typed_step import TypedStep
    from wurzel.executors.backend.backend import Backend
    from wurzel.executors.base_executor import BaseStepExecutor


def _resolve_backend_instance(
    backend: type[Backend],
    values: list[Path] | None,
    pipeline_name: str | None,
    executor: type[BaseStepExecutor] | None = None,
) -> Backend:
    """Resolve a backend class to an instance.

    For backends that support from_values (ArgoBackend, DvcBackend), uses that method.
    Otherwise, instantiates the backend directly.
    """
    # Check if backend has from_values method (like ArgoBackend and DvcBackend)
    from_values = getattr(backend, "from_values", None)
    if callable(from_values) and values:
        factory = cast(Callable[..., "Backend"], from_values)
        return factory(values, workflow_name=pipeline_name, executor=executor)
    if executor is not None:
        return backend(executer=executor)
    return backend()


def _write_output(content: str, output: Path) -> None:
    """Write content to output file, creating parent directories as needed."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def main(
    step: TypedStep,
    backend: type[Backend],
    *,
    values: Iterable[Path] | None = None,
    pipeline_name: str | None = None,
    output: Path | None = None,
    executor: type[BaseStepExecutor] | None = None,
) -> str:
    """Generate backend-specific YAML for a pipeline."""
    adapter = _resolve_backend_instance(backend, list(values or []), pipeline_name, executor)
    yaml_content = adapter.generate_artifact(step)

    if output:
        _write_output(yaml_content, output)

    return yaml_content


__all__ = [
    "get_available_backends",
    "backend_callback",
    "pipeline_callback",
    "main",
    "_resolve_backend_instance",
    "_write_output",
]
