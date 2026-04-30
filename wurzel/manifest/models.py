# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Pydantic models for the Wurzel pipeline manifest format.

A manifest is a YAML file that describes which steps to run, how they depend on
each other, which middlewares to activate, and which backend should produce the
execution artifact (DVC pipeline file, Argo Workflow, …).

Minimal valid manifest:

```yaml
apiVersion: wurzel.dev/v1alpha1
kind: Pipeline
metadata:
  name: my-pipeline
spec:
  backend: dvc
  steps:
    - name: ingest
      class: wurzel.steps.manual_markdown.ManualMarkdownStep
```

```python
from wurzel.manifest.models import PipelineManifest

raw = {
    "apiVersion": "wurzel.dev/v1alpha1",
    "kind": "Pipeline",
    "metadata": {"name": "demo"},
    "spec": {
        "backend": "dvc",
        "steps": [
            {
                "name": "ingest",
                "class": "wurzel.steps.manual_markdown.ManualMarkdownStep",
            }
        ],
    },
}
manifest = PipelineManifest.model_validate(raw)
print(manifest.metadata.name)
#> demo
print(manifest.spec.backend)
#> dvc
print(manifest.spec.steps[0].name)
#> ingest
```
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StepSpec(BaseModel):
    """Declaration of a single pipeline step."""

    name: str
    class_: str = Field(..., alias="class")
    dependsOn: list[str] = Field(default_factory=list)
    settings: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class MiddlewareSpec(BaseModel):
    """Declaration of a middleware with its own settings."""

    name: str
    settings: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class BackendConfig(BaseModel):
    """Open container for backend-specific configurations.

    Any extra keys are preserved and forwarded to the corresponding backend's
    ``from_manifest_config`` factory via ``get_for(backend_name)``.

    Example manifest excerpt::

        backendConfig:
          dvc:
            dataDir: ./data
          argo:
            namespace: my-namespace
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def get_for(self, backend_name: str) -> dict[str, Any]:
        """Return the raw config dict for a specific backend.

        Args:
            backend_name: Registered backend name, e.g. ``"dvc"`` or ``"argo"``.

        Returns:
            The config dict for that backend, or an empty dict if not present.

        """
        return (self.model_extra or {}).get(backend_name) or {}


class Metadata(BaseModel):
    """Manifest metadata block."""

    name: str
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class PipelineSpec(BaseModel):
    """Core pipeline specification."""

    backend: str
    schedule: str | None = None
    middlewares: list[MiddlewareSpec] = Field(default_factory=list)
    steps: Annotated[list[StepSpec], Field(min_length=1)]
    backendConfig: BackendConfig = Field(default_factory=BackendConfig)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("backend", mode="after")
    @classmethod
    def _validate_backend(cls, v: str) -> str:
        # Import triggers backend registration side-effects (DvcBackend, ArgoBackend).
        from wurzel.executors.backend import Backend  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

        registry = Backend.get_registry()
        if registry and v not in registry:
            known = ", ".join(f"'{k}'" for k in sorted(registry))
            raise ValueError(f"Unknown backend '{v}'. Registered backends: {known}.")
        return v


class PipelineManifest(BaseModel):
    """Root model for a Wurzel pipeline manifest file."""

    apiVersion: str = "wurzel.dev/v1alpha1"
    kind: Literal["Pipeline"] = "Pipeline"
    metadata: Metadata
    spec: PipelineSpec

    model_config = ConfigDict(populate_by_name=True)
