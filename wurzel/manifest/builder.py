# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Build a TypedStep graph from a validated PipelineManifest.

```python
from wurzel.manifest.builder import ManifestBuilder
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
            },
        ],
    },
}
manifest = PipelineManifest.model_validate(raw)
builder = ManifestBuilder(manifest)
graph = builder.build_step_graph()
print("ingest" in graph)
#> True
```
"""

from __future__ import annotations

from wurzel.core import TypedStep
from wurzel.manifest.class_import import import_step_class
from wurzel.manifest.models import PipelineManifest
from wurzel.utils import WZ


class ManifestBuilder:
    """Builds a TypedStep execution graph from a validated PipelineManifest."""

    def __init__(self, manifest: PipelineManifest) -> None:
        self._manifest = manifest

    @staticmethod
    def import_step_class(class_path: str) -> type[TypedStep]:
        """Dynamically import a TypedStep subclass by its dotted Python path.

        Raises:
            ImportError: If the module or class cannot be found.
        """
        return import_step_class(class_path)

    def build_step_graph(self) -> dict[str, TypedStep]:
        """Instantiate and wire all steps from the manifest.

        Returns a mapping of step name → WZ-wrapped TypedStep instance.
        Dependencies are wired via the ``>>`` operator so that
        ``parent in child.required_steps`` holds for each declared dependsOn.

        Raises:
            ValueError: If manifest semantic validation fails.
            ImportError: If any step class cannot be imported.
        """
        from wurzel.manifest.validator import ManifestValidator  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

        errors = ManifestValidator(self._manifest).validate_all()
        if errors:
            raise ValueError("Manifest validation failed:\n" + "\n".join(f"- {error}" for error in errors))

        graph: dict[str, TypedStep] = {}
        for spec in self._manifest.spec.steps:
            cls = self.import_step_class(spec.class_)
            graph[spec.name] = WZ(cls)

        for spec in self._manifest.spec.steps:
            for parent_name in spec.dependsOn:
                graph[parent_name] >> graph[spec.name]  # pylint: disable=pointless-statement

        return graph

    def find_terminal_steps(self, graph: dict[str, TypedStep]) -> list[TypedStep]:
        """Return steps that are not referenced as a dependency by any other step.

        These are the "sinks" / leaf nodes of the pipeline DAG.
        """
        referenced: set[str] = set()
        for spec in self._manifest.spec.steps:
            referenced.update(spec.dependsOn)
        return [step for name, step in graph.items() if name not in referenced]
