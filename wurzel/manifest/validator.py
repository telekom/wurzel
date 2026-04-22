# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Semantic validation of a PipelineManifest (DAG structure, class paths, middleware names).

All methods return a list of human-readable error strings. An empty list means no errors.
No exceptions are raised here — callers decide what to do with the errors.
"""

from __future__ import annotations

from wurzel.manifest.models import PipelineManifest


class ManifestValidator:
    """Validates a PipelineManifest for structural and semantic correctness."""

    def __init__(self, manifest: PipelineManifest) -> None:
        self._manifest = manifest

    def validate_step_refs(self) -> list[str]:
        """Return errors for any dependsOn name that does not refer to a defined step."""
        defined = {step.name for step in self._manifest.spec.steps}
        errors: list[str] = []
        for step in self._manifest.spec.steps:
            for dep in step.dependsOn:
                if dep not in defined:
                    errors.append(f"Step '{step.name}' depends on '{dep}', which is not defined in steps.")
        return errors

    def validate_no_cycles(self) -> list[str]:
        """Return errors if the dependency graph contains cycles (including self-references)."""
        adjacency: dict[str, list[str]] = {step.name: list(step.dependsOn) for step in self._manifest.spec.steps}
        WHITE, GRAY, BLACK = 0, 1, 2  # pylint: disable=invalid-name
        colour: dict[str, int] = dict.fromkeys(adjacency, WHITE)
        errors: list[str] = []

        def dfs(node: str) -> None:
            colour[node] = GRAY
            for neighbour in adjacency.get(node, []):
                if neighbour not in colour:
                    continue  # undefined refs are caught by validate_step_refs
                if colour[neighbour] == GRAY:
                    errors.append(f"Cycle detected involving step '{node}' \u2192 '{neighbour}'.")
                elif colour[neighbour] == WHITE:
                    dfs(neighbour)
            colour[node] = BLACK

        for name in adjacency:
            if colour[name] == WHITE:
                dfs(name)

        return errors

    def validate_class_paths(self) -> list[str]:
        """Return errors for any step whose class path cannot be imported."""
        from wurzel.manifest.builder import ManifestBuilder  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

        errors: list[str] = []
        for step in self._manifest.spec.steps:
            if "." not in step.class_:
                errors.append(f"Step '{step.name}': class path '{step.class_}' has no module component.")
                continue
            try:
                ManifestBuilder.import_step_class(step.class_)
            except ImportError as exc:
                errors.append(f"Step '{step.name}': cannot import '{step.class_}': {exc}")
        return errors

    def validate_middleware_names(self) -> list[str]:
        """Return errors for any middleware name not registered in the global registry."""
        from wurzel.executors.middlewares import get_registry  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

        registry = get_registry()
        available = set(registry.list_available())
        errors: list[str] = []
        for mw in self._manifest.spec.middlewares:
            if mw.name.lower() not in available:
                errors.append(f"Middleware '{mw.name}' is not registered. Available: {sorted(available)}")
        return errors

    def validate_all(self) -> list[str]:
        """Run all validators and return a combined list of errors."""
        errors: list[str] = []
        errors.extend(self.validate_step_refs())
        errors.extend(self.validate_no_cycles())
        errors.extend(self.validate_class_paths())
        errors.extend(self.validate_middleware_names())
        return errors
