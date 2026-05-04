# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Orchestrate manifest → backend artifact generation."""
# pylint: disable=duplicate-code

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from wurzel.executors.backend import Backend
from wurzel.manifest.builder import ManifestBuilder
from wurzel.manifest.env_expander import EnvExpander
from wurzel.manifest.models import PipelineManifest


class ManifestGenerator:
    """Orchestrates manifest → backend artifact generation."""

    def __init__(self, manifest: PipelineManifest) -> None:
        self._manifest = manifest

    def collect_env_vars(self) -> dict[str, str]:
        """Build a flat env var dict from all step settings and middleware settings.

        Merges:
        - Per-step settings prefixed with ``{CLASS_NAME_UPPER}__``
        - Per-middleware settings prefixed with ``{MIDDLEWARE_NAME_UPPER}__``
        - ``MIDDLEWARES`` var listing ordered middleware names
        """
        env: dict[str, str] = {}

        for step in self._manifest.spec.steps:
            class_name = step.class_.rpartition(".")[2]
            env.update(EnvExpander.expand_step_settings(class_name, step.settings))

        for mw in self._manifest.spec.middlewares:
            env.update(EnvExpander.expand_middleware_settings(mw.name, mw.settings))

        env.update(EnvExpander.expand_middlewares_list([mw.name for mw in self._manifest.spec.middlewares]))

        return env

    def instantiate_backend(self) -> Backend:
        """Create the appropriate Backend instance from the manifest spec.

        Raises:
            ValueError: If spec.backend is not a registered backend name.
        """
        name = self._manifest.spec.backend
        raw_config = self._manifest.spec.backendConfig.get_for(name)
        # Inject top-level manifest fields so backends can consume them without
        # needing to know about the manifest schema.
        raw_config = {"schedule": self._manifest.spec.schedule, **raw_config}
        return Backend.create(name, raw_config)

    @contextmanager
    def _env_override(self, extra: dict[str, str]) -> Iterator[None]:
        """Temporarily inject env vars, restoring originals on exit."""
        original = {k: os.environ.get(k) for k in extra}
        os.environ.update(extra)
        try:
            yield
        finally:
            for key, old_value in original.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

    def generate(self, output_path: Path) -> None:
        """Build a backend artifact from the manifest and write it to output_path.

        Steps:
        1. Collect all env vars from the manifest.
        2. Inject env vars so the backend can read them during generation.
        3. Instantiate the backend.
        4. Build the TypedStep graph and locate terminal steps.
        5. Call generate_artifact on the first terminal step.
        6. Write the result to output_path.
        """
        env_vars = self.collect_env_vars()
        builder = ManifestBuilder(self._manifest)
        with self._env_override(env_vars):
            backend = self.instantiate_backend()
            graph = builder.build_step_graph()
            terminals = builder.find_terminal_steps(graph)
            artifact = backend.generate_artifact(terminals[0], env_vars=env_vars)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(artifact, encoding="utf-8")
