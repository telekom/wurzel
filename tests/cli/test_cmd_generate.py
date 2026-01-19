# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from wurzel.backend.backend import Backend
from wurzel.cli import cmd_generate
from wurzel.utils import HAS_HERA

if HAS_HERA:
    from wurzel.backend.backend_argo import ArgoBackend
else:  # pragma: no cover - optional dependency guard
    ArgoBackend = None


class _MinimalBackend(Backend):
    def generate_artifact(self, step):  # pragma: no cover - helper stub
        raise NotImplementedError


@pytest.mark.skipif(not HAS_HERA, reason="Argo backend requires Hera extras")
def test_resolve_backend_instance_uses_from_values_for_argo(monkeypatch, tmp_path):
    values_file = tmp_path / "values.yaml"
    values_file.write_text("workflows: {}")

    sentinel = object()
    captured: dict[str, object] = {}

    def fake_from_values(cls, files, workflow_name=None, as_cron=None):  # noqa: ANN001
        captured["files"] = files
        captured["workflow"] = workflow_name
        captured["as_cron"] = as_cron
        return sentinel

    monkeypatch.setattr(ArgoBackend, "from_values", classmethod(fake_from_values))

    adapter = cmd_generate._resolve_backend_instance(ArgoBackend, [values_file], "demo")

    assert adapter is sentinel
    assert captured["files"] == [values_file]
    assert captured["workflow"] == "demo"
    assert captured["as_cron"] is None


@pytest.mark.skipif(not HAS_HERA, reason="Argo backend requires Hera extras")
def test_resolve_backend_instance_passes_as_cron_to_argo(monkeypatch, tmp_path):
    values_file = tmp_path / "values.yaml"
    values_file.write_text("workflows: {}")

    sentinel = object()
    captured: dict[str, object] = {}

    def fake_from_values(cls, files, workflow_name=None, as_cron=None):  # noqa: ANN001
        captured["files"] = files
        captured["workflow"] = workflow_name
        captured["as_cron"] = as_cron
        return sentinel

    monkeypatch.setattr(ArgoBackend, "from_values", classmethod(fake_from_values))

    adapter = cmd_generate._resolve_backend_instance(ArgoBackend, [values_file], "demo", as_cron=True)

    assert adapter is sentinel
    assert captured["files"] == [values_file]
    assert captured["workflow"] == "demo"
    assert captured["as_cron"] is True


@pytest.mark.skipif(not HAS_HERA, reason="Argo backend requires Hera extras")
def test_resolve_backend_instance_inits_argo_without_values(monkeypatch):
    init_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_init(self, *args, **kwargs):  # noqa: ANN002, ANN003
        init_calls.append((args, kwargs))

    monkeypatch.setattr(ArgoBackend, "__init__", fake_init)

    adapter = cmd_generate._resolve_backend_instance(ArgoBackend, None, None)

    assert isinstance(adapter, ArgoBackend)
    assert init_calls == [((), {})]


def test_resolve_backend_instance_for_non_argo_backend(tmp_path):
    class DummyBackend(Backend):
        def __init__(self):
            self.initialized = True

        def generate_artifact(self, step):  # pragma: no cover - helper stub
            return f"yaml:{step}"

    adapter = cmd_generate._resolve_backend_instance(DummyBackend, [tmp_path / "ignored"], None)

    assert isinstance(adapter, DummyBackend)
    assert adapter.initialized is True


def test_cmd_generate_main_resolves_backend_with_iterable_values(monkeypatch, tmp_path):
    values_file = tmp_path / "values.yaml"
    values_file.write_text("workflows: {}")
    values_iterable = (path for path in [values_file])

    class Adapter:
        def __init__(self):
            self.steps: list[object] = []

        def generate_artifact(self, step):
            self.steps.append(step)
            return "rendered"

    captured: dict[str, object] = {}

    def fake_resolve(backend, values, pipeline_name, as_cron=None):  # noqa: ANN001, ANN002, ANN003
        captured["backend"] = backend
        captured["values"] = values
        captured["pipeline_name"] = pipeline_name
        captured["as_cron"] = as_cron
        return Adapter()

    monkeypatch.setattr(cmd_generate, "_resolve_backend_instance", fake_resolve)

    step = object()
    result = cmd_generate.main(step, _MinimalBackend, values=values_iterable, pipeline_name="wf-name")

    assert result == "rendered"
    assert captured["backend"] is _MinimalBackend
    assert captured["values"] == [values_file]
    assert captured["pipeline_name"] == "wf-name"
    assert captured["as_cron"] is None


def test_cmd_generate_main_writes_to_output(monkeypatch, tmp_path):
    class Adapter:
        def generate_artifact(self, step):  # noqa: ARG002
            return "artifact-yaml"

    def fake_resolve(backend, values, pipeline_name, as_cron=None):  # noqa: ANN001, ANN002, ANN003
        assert backend is _MinimalBackend
        assert values == []
        assert pipeline_name is None
        assert as_cron is None
        return Adapter()

    monkeypatch.setattr(cmd_generate, "_resolve_backend_instance", fake_resolve)

    output_path = tmp_path / "manifest.yaml"

    result = cmd_generate.main("pipeline", _MinimalBackend, output=output_path)

    assert result == "artifact-yaml"
    assert output_path.read_text(encoding="utf-8") == "artifact-yaml"


def test_cmd_generate_main_passes_as_cron_parameter(monkeypatch, tmp_path):
    class Adapter:
        def generate_artifact(self, step):  # noqa: ARG002
            return "artifact-yaml"

    captured: dict[str, object] = {}

    def fake_resolve(backend, values, pipeline_name, as_cron=None):  # noqa: ANN001, ANN002, ANN003
        captured["backend"] = backend
        captured["values"] = values
        captured["pipeline_name"] = pipeline_name
        captured["as_cron"] = as_cron
        return Adapter()

    monkeypatch.setattr(cmd_generate, "_resolve_backend_instance", fake_resolve)

    output_path = tmp_path / "manifest.yaml"

    # Test with as_cron=True
    result = cmd_generate.main("pipeline", _MinimalBackend, output=output_path, as_cron=True)
    assert result == "artifact-yaml"
    assert captured["as_cron"] is True

    # Test with as_cron=False
    result = cmd_generate.main("pipeline", _MinimalBackend, output=output_path, as_cron=False)
    assert result == "artifact-yaml"
    assert captured["as_cron"] is False
