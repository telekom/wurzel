# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for pipeline backend adapters."""

from __future__ import annotations

import asyncio
import os
import uuid
from unittest.mock import patch

import pytest

from wurzel.api.services.pipeline_backends import (
    RegisteredBackendRunAdapter,
    _env_override,
    get_pipeline_run_adapter,
)
from wurzel.manifest.models import PipelineManifest

_RUN_ID = uuid.uuid4()
_MANIFEST = PipelineManifest.model_validate(
    {
        "apiVersion": "wurzel.dev/v1alpha1",
        "kind": "Pipeline",
        "metadata": {"name": "test-pipeline"},
        "spec": {
            "backend": "dvc",
            "steps": [
                {
                    "name": "source",
                    "class": "wurzel.steps.manual_markdown.ManualMarkdownStep",
                }
            ],
        },
    }
)


def test_get_pipeline_run_adapter_returns_registered_adapter():
    with patch("wurzel.api.services.pipeline_backends.get_backend_by_name", return_value=object()):
        adapter = get_pipeline_run_adapter("dvc")
    assert isinstance(adapter, RegisteredBackendRunAdapter)


def test_get_pipeline_run_adapter_raises_for_unknown_backend():
    with patch("wurzel.api.services.pipeline_backends.get_backend_by_name", return_value=None):
        with pytest.raises(ValueError, match="not available"):
            get_pipeline_run_adapter("unknown")


def test_env_override_sets_and_restores_variables():
    os.environ["PIPELINE_BACKENDS_TEST"] = "before"
    with _env_override({"PIPELINE_BACKENDS_TEST": "inside", "PIPELINE_BACKENDS_NEW": "value"}):
        assert os.environ["PIPELINE_BACKENDS_TEST"] == "inside"
        assert os.environ["PIPELINE_BACKENDS_NEW"] == "value"
    assert os.environ["PIPELINE_BACKENDS_TEST"] == "before"
    assert "PIPELINE_BACKENDS_NEW" not in os.environ


def test_registered_backend_adapter_executes_single_terminal(tmp_path):
    class _Backend:
        def __init__(self):
            self.generate_calls = 0
            self.execute_calls = 0

        def generate_artifact(self, _step, *, env_vars=None):  # noqa: ANN001
            _ = env_vars
            self.generate_calls += 1
            return "kind: Workflow"

        def execute_step(self, _step_type, _input, _output):  # noqa: ANN001
            self.execute_calls += 1

    class _Generator:
        def __init__(self, manifest):  # noqa: ANN001
            self._manifest = manifest
            self.backend = _Backend()

        def collect_env_vars(self):
            return {"EXAMPLE": "1"}

        def instantiate_backend(self):
            return self.backend

    class _Builder:
        def __init__(self, manifest):  # noqa: ANN001
            self._manifest = manifest

        def build_step_graph(self):
            return {"source": object()}

        def find_terminal_steps(self, _graph):  # noqa: ANN001
            return [object()]

    with (
        patch("wurzel.api.services.pipeline_backends.ManifestGenerator", _Generator),
        patch("wurzel.api.services.pipeline_backends.ManifestBuilder", _Builder),
        patch("wurzel.api.services.pipeline_backends.gettempdir", return_value=str(tmp_path)),
    ):
        result = asyncio.run(RegisteredBackendRunAdapter("dvc").execute(_MANIFEST, _RUN_ID))

    assert result.backend_run_id == str(_RUN_ID)
    assert result.logs_url is not None and result.logs_url.startswith("file://")
    assert result.artifacts_url is not None and result.artifacts_url.startswith("file://")


def test_registered_backend_adapter_executes_multi_terminal_without_artifact_render(tmp_path):
    class _Backend:
        def __init__(self):
            self.execute_calls = 0

        def generate_artifact(self, _step, *, env_vars=None):  # noqa: ANN001
            _ = env_vars
            return "should-not-be-used"

        def execute_step(self, _step_type, _input, _output):  # noqa: ANN001
            self.execute_calls += 1

    class _Generator:
        def __init__(self, manifest):  # noqa: ANN001
            self._manifest = manifest
            self.backend = _Backend()

        def collect_env_vars(self):
            return {}

        def instantiate_backend(self):
            return self.backend

    class _Builder:
        def __init__(self, manifest):  # noqa: ANN001
            self._manifest = manifest

        def build_step_graph(self):
            return {"a": object(), "b": object()}

        def find_terminal_steps(self, _graph):  # noqa: ANN001
            return [object(), object()]

    with (
        patch("wurzel.api.services.pipeline_backends.ManifestGenerator", _Generator),
        patch("wurzel.api.services.pipeline_backends.ManifestBuilder", _Builder),
        patch("wurzel.api.services.pipeline_backends.gettempdir", return_value=str(tmp_path)),
    ):
        result = asyncio.run(RegisteredBackendRunAdapter("dvc").execute(_MANIFEST, _RUN_ID))

    assert result.logs_url is not None
    assert result.artifacts_url is not None


def test_registered_backend_adapter_validates_manifest_backend_name():
    adapter = RegisteredBackendRunAdapter("argo")
    with pytest.raises(ValueError, match="mismatch"):
        asyncio.run(adapter.execute(_MANIFEST, _RUN_ID))
