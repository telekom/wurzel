# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, cast

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
    # Check if backend has from_values method (like ArgoBackend and DvcBackend)
    from_values = getattr(backend, "from_values", None)
    if callable(from_values) and values:
        factory = cast(Callable[..., "Backend"], from_values)
        return factory(values, workflow_name=pipeline_name, executor=executor)
    if executor is not None:
        return backend(executer=executor)
    return backend()


def _write_output(content: str, output: Path) -> None:
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
