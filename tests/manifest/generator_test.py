# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.manifest.generator import ManifestGenerator
from wurzel.manifest.models import (
    BackendConfig,
    Metadata,
    MiddlewareSpec,
    PipelineManifest,
    PipelineSpec,
    StepSpec,
)


def _manifest(
    backend: str, steps: list[dict], middlewares: list[dict] | None = None, backend_config: dict | None = None
) -> PipelineManifest:
    bc = BackendConfig(**(backend_config or {}))
    return PipelineManifest(
        metadata=Metadata(name="test"),
        spec=PipelineSpec(
            backend=backend,
            middlewares=[MiddlewareSpec(**m) for m in (middlewares or [])],
            steps=[StepSpec.model_validate(s) for s in steps],
            backendConfig=bc,
        ),
    )


class TestCollectEnvVars:
    def test_step_settings_expanded(self):
        manifest = _manifest(
            "dvc",
            steps=[{"name": "src", "class": "x.A", "settings": {"FOLDER_PATH": "./data"}}],
        )
        env = ManifestGenerator(manifest).collect_env_vars()
        assert env["A__FOLDER_PATH"] == "./data"

    def test_middleware_settings_expanded(self):
        manifest = _manifest(
            "dvc",
            steps=[{"name": "src", "class": "x.A"}],
            middlewares=[{"name": "prometheus", "settings": {"GATEWAY": "host:9091"}}],
        )
        env = ManifestGenerator(manifest).collect_env_vars()
        assert env["PROMETHEUS__GATEWAY"] == "host:9091"

    def test_middlewares_list_var_set(self):
        manifest = _manifest(
            "dvc",
            steps=[{"name": "src", "class": "x.A"}],
            middlewares=[
                {"name": "secret_resolver"},
                {"name": "prometheus"},
            ],
        )
        env = ManifestGenerator(manifest).collect_env_vars()
        assert env["MIDDLEWARES"] == "secret_resolver,prometheus"

    def test_no_middlewares_sets_empty_string(self):
        manifest = _manifest("dvc", steps=[{"name": "src", "class": "x.A"}])
        env = ManifestGenerator(manifest).collect_env_vars()
        assert env["MIDDLEWARES"] == ""

    def test_multiple_steps_all_expanded(self):
        manifest = _manifest(
            "dvc",
            steps=[
                {"name": "a", "class": "mod.StepA", "settings": {"K": "1"}},
                {"name": "b", "class": "mod.StepB", "settings": {"K": "2"}},
            ],
        )
        env = ManifestGenerator(manifest).collect_env_vars()
        assert "STEPA__K" in env
        assert "STEPB__K" in env


class TestInstantiateBackend:
    def test_dvc_backend_registered_without_explicit_import(self):
        """DvcBackend must be registered via the wurzel.executors.backend package import
        in generator.py — no explicit DvcBackend import needed in the test.
        """
        from wurzel.executors.backend.backend import Backend  # noqa: PLC0415

        registry = Backend.get_registry()
        assert "dvc" in registry, "DvcBackend must be in the registry when generator is imported"

    def test_dvc_backend_returned_for_dvc(self):
        from wurzel.executors.backend.backend_dvc import DvcBackend

        manifest = _manifest(
            "dvc",
            steps=[{"name": "src", "class": "x.A"}],
            backend_config={"dvc": {"dataDir": "./data"}},
        )
        backend = ManifestGenerator(manifest).instantiate_backend()
        assert isinstance(backend, DvcBackend)

    def test_argo_backend_returned_for_argo(self):
        pytest.importorskip("hera")
        from wurzel.executors.backend.backend_argo import ArgoBackend

        manifest = _manifest(
            "argo",
            steps=[{"name": "src", "class": "x.A"}],
            backend_config={"argo": {"namespace": "test-ns"}},
        )
        backend = ManifestGenerator(manifest).instantiate_backend()
        assert isinstance(backend, ArgoBackend)

    def test_unknown_backend_raises(self):
        manifest = _manifest("dvc", steps=[{"name": "src", "class": "x.A"}])
        manifest.spec.__dict__["backend"] = "unknown"  # force invalid after validation
        with pytest.raises(ValueError, match="unknown"):
            ManifestGenerator(manifest).instantiate_backend()


class TestEnvOverride:
    def test_injects_and_restores(self, monkeypatch):
        monkeypatch.delenv("_TEST_WURZEL_KEY_", raising=False)
        manifest = _manifest("dvc", steps=[{"name": "src", "class": "x.A"}])
        gen = ManifestGenerator(manifest)
        import os

        with gen._env_override({"_TEST_WURZEL_KEY_": "injected"}):
            assert os.environ["_TEST_WURZEL_KEY_"] == "injected"
        assert "_TEST_WURZEL_KEY_" not in os.environ

    def test_restores_original_value(self, monkeypatch):
        import os

        monkeypatch.setenv("_TEST_WURZEL_KEY_", "original")
        manifest = _manifest("dvc", steps=[{"name": "src", "class": "x.A"}])
        gen = ManifestGenerator(manifest)
        with gen._env_override({"_TEST_WURZEL_KEY_": "overridden"}):
            assert os.environ["_TEST_WURZEL_KEY_"] == "overridden"
        assert os.environ["_TEST_WURZEL_KEY_"] == "original"


class TestGenerate:
    def test_generate_writes_dvc_yaml(self, tmp_path):
        manifest = _manifest(
            "dvc",
            steps=[{"name": "src", "class": "wurzel.steps.manual_markdown.ManualMarkdownStep", "settings": {"FOLDER_PATH": "./data"}}],
        )
        output = tmp_path / "dvc.yaml"
        ManifestGenerator(manifest).generate(output)
        assert output.exists()
        import yaml

        parsed = yaml.safe_load(output.read_text())
        assert "stages" in parsed
