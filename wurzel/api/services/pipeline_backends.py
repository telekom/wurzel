# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Backend adapter abstraction for API-triggered pipeline runs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir
from typing import Protocol

from wurzel.executors.backend import get_backend_by_name
from wurzel.manifest.builder import ManifestBuilder
from wurzel.manifest.generator import ManifestGenerator
from wurzel.manifest.models import PipelineManifest
from wurzel.utils.env import env_override


@dataclass
class BackendExecutionResult:
    """Result metadata returned by backend run adapters."""

    backend_run_id: str
    logs_url: str | None = None
    artifacts_url: str | None = None


class PipelineRunAdapter(Protocol):
    """Protocol for backend-specific API run execution."""

    async def execute(self, manifest: PipelineManifest, run_id: uuid.UUID) -> BackendExecutionResult:
        """Execute one API-triggered run for a manifest."""


class RegisteredBackendRunAdapter:
    """Adapter that executes a run against a registered Wurzel backend."""

    def __init__(self, backend_name: str) -> None:
        self.backend_name = backend_name

    async def execute(self, manifest: PipelineManifest, run_id: uuid.UUID) -> BackendExecutionResult:
        """Execute one API-triggered run for the registered backend."""
        if manifest.spec.backend != self.backend_name:
            raise ValueError(f"Run backend mismatch. Expected '{self.backend_name}', got '{manifest.spec.backend}'.")

        run_dir = Path(gettempdir()) / "wurzel-api-runs" / str(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        logs_path = run_dir / "run.log"
        artifact_path = run_dir / "artifact.yaml"

        backend_run_id = str(run_id)
        generator = ManifestGenerator(manifest)
        env_vars = generator.collect_env_vars() | {"WURZEL_RUN_ID": backend_run_id}
        builder = ManifestBuilder(manifest)

        with env_override(env_vars):
            backend = generator.instantiate_backend()
            graph = builder.build_step_graph()
            terminals = builder.find_terminal_steps(graph)

            if len(terminals) == 1:
                artifact_content = backend.generate_artifact(terminals[0], env_vars=env_vars)
            else:
                artifact_content = (
                    "# Multiple terminal steps detected during API run execution.\n"
                    "# Artifact rendering is omitted for multi-terminal DAGs.\n"
                )
            artifact_path.write_text(artifact_content, encoding="utf-8")

            for step in terminals:
                backend.execute_step(type(step), None, None)

        logs_path.write_text(
            f"run_id={backend_run_id}\nbackend={self.backend_name}\nstatus=succeeded\n",
            encoding="utf-8",
        )
        return BackendExecutionResult(
            backend_run_id=backend_run_id,
            logs_url=logs_path.as_uri(),
            artifacts_url=artifact_path.as_uri(),
        )


def get_pipeline_run_adapter(backend_name: str) -> PipelineRunAdapter:
    """Resolve the API run adapter for a backend name."""
    backend_cls = get_backend_by_name(backend_name)
    if backend_cls is None:
        raise ValueError(f"Backend '{backend_name}' is not available.")
    return RegisteredBackendRunAdapter(backend_name)
