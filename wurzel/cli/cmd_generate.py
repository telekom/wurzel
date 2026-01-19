# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wurzel.backend.backend import Backend
    from wurzel.step.typed_step import TypedStep


def _resolve_backend_instance(
    backend: type[Backend],
    values: list[Path] | None,
    pipeline_name: str | None,
    as_cron: bool | None = None,
) -> Backend:
    # Check if backend has from_values method (like ArgoBackend and DvcBackend)
    if hasattr(backend, "from_values") and values:
        kwargs = {"workflow_name": pipeline_name}
        # Pass as_cron only if it's not None and backend accepts it
        if as_cron is not None and hasattr(backend, "__init__"):
            import inspect  # noqa: PLC0415
            sig = inspect.signature(backend.__init__)
            if "as_cron" in sig.parameters:
                kwargs["as_cron"] = as_cron
        return backend.from_values(values, **kwargs)  # type: ignore[call-arg]
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
    as_cron: bool | None = None,
) -> str:
    """Generate backend-specific YAML for a pipeline."""
    adapter = _resolve_backend_instance(backend, list(values or []), pipeline_name, as_cron)
    yaml_content = adapter.generate_artifact(step)

    if output:
        _write_output(yaml_content, output)

    return yaml_content
