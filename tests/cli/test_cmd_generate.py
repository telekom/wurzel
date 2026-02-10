# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from wurzel.cli import cmd_generate
from wurzel.executors.backend.backend import Backend
from wurzel.utils import HAS_HERA

if HAS_HERA:
    from wurzel.executors.backend.backend_argo import ArgoBackend
else:  # pragma: no cover - optional dependency guard
    ArgoBackend = None


class _MinimalBackend(Backend):
    def generate_artifact(self, step):  # pragma: no cover - helper stub
        raise NotImplementedError


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

    def fake_resolve(backend, values, pipeline_name):  # noqa: ANN001, ANN002, ANN003
        captured["backend"] = backend
        captured["values"] = values
        captured["pipeline_name"] = pipeline_name
        return Adapter()

    monkeypatch.setattr(cmd_generate, "_resolve_backend_instance", fake_resolve)

    step = object()
    result = cmd_generate.main(step, _MinimalBackend, values=values_iterable, pipeline_name="wf-name")

    assert result == "rendered"
    assert captured["backend"] is _MinimalBackend
    assert captured["values"] == [values_file]
    assert captured["pipeline_name"] == "wf-name"


def test_cmd_generate_main_writes_to_output(monkeypatch, tmp_path):
    class Adapter:
        def generate_artifact(self, step):  # noqa: ARG002
            return "artifact-yaml"

    def fake_resolve(backend, values, pipeline_name):  # noqa: ANN001, ANN002, ANN003
        assert backend is _MinimalBackend
        assert values == []
        assert pipeline_name is None
        return Adapter()

    monkeypatch.setattr(cmd_generate, "_resolve_backend_instance", fake_resolve)

    output_path = tmp_path / "manifest.yaml"

    result = cmd_generate.main("pipeline", _MinimalBackend, output=output_path)

    assert result == "artifact-yaml"
    assert output_path.read_text(encoding="utf-8") == "artifact-yaml"
