# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest
from pydantic import ValidationError

from tests.manifest.conftest import FULL_MANIFEST_YAML, MINIMAL_MANIFEST_YAML
from wurzel.manifest.models import (
    BackendConfig,
    Metadata,
    MiddlewareSpec,
    PipelineManifest,
    PipelineSpec,
    StepSpec,
)


class TestStepSpec:
    def test_class_alias_resolves(self):
        step = StepSpec.model_validate({"name": "src", "class": "some.module.Step"})
        assert step.class_ == "some.module.Step"

    def test_depends_on_defaults_empty(self):
        step = StepSpec.model_validate({"name": "src", "class": "some.Step"})
        assert step.dependsOn == []

    def test_settings_defaults_empty(self):
        step = StepSpec.model_validate({"name": "src", "class": "some.Step"})
        assert step.settings == {}

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            StepSpec.model_validate({"class": "some.Step"})

    def test_missing_class_raises(self):
        with pytest.raises(ValidationError):
            StepSpec.model_validate({"name": "src"})


class TestMiddlewareSpec:
    def test_settings_defaults_empty(self):
        mw = MiddlewareSpec(name="prometheus")
        assert mw.settings == {}

    def test_settings_preserved(self):
        mw = MiddlewareSpec(name="prometheus", settings={"GATEWAY": "host:9091"})
        assert mw.settings["GATEWAY"] == "host:9091"

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            MiddlewareSpec.model_validate({})


class TestPipelineSpec:
    def test_backend_registry_populated_when_models_imported(self):
        """models.py must import Backend from the package (not the submodule) so that
        DvcBackend and ArgoBackend are registered before validation runs.
        """
        from wurzel.executors.backend.backend import Backend  # noqa: PLC0415

        registry = Backend.get_registry()
        assert "dvc" in registry, "DvcBackend must be registered when wurzel.manifest.models is imported"

    def test_backend_argo_valid(self):
        pytest.importorskip("hera")
        spec = PipelineSpec(
            backend="argo",
            steps=[StepSpec.model_validate({"name": "s", "class": "a.B"})],
        )
        assert spec.backend == "argo"

    def test_backend_dvc_valid(self):
        spec = PipelineSpec(
            backend="dvc",
            steps=[StepSpec.model_validate({"name": "s", "class": "a.B"})],
        )
        assert spec.backend == "dvc"

    def test_invalid_backend_raises(self):
        with pytest.raises(ValidationError):
            PipelineSpec(
                backend="invalid",
                steps=[StepSpec.model_validate({"name": "s", "class": "a.B"})],
            )

    def test_schedule_optional(self):
        spec = PipelineSpec(
            backend="dvc",
            steps=[StepSpec.model_validate({"name": "s", "class": "a.B"})],
        )
        assert spec.schedule is None

    def test_middlewares_order_preserved(self):
        pytest.importorskip("hera")
        spec = PipelineSpec(
            backend="argo",
            middlewares=[
                MiddlewareSpec(name="secret_resolver"),
                MiddlewareSpec(name="prometheus"),
            ],
            steps=[StepSpec.model_validate({"name": "s", "class": "a.B"})],
        )
        assert [m.name for m in spec.middlewares] == ["secret_resolver", "prometheus"]

    def test_empty_steps_raises(self):
        with pytest.raises(ValidationError):
            PipelineSpec(backend="dvc", steps=[])


class TestPipelineManifest:
    def test_kind_must_be_pipeline(self):
        with pytest.raises(ValidationError):
            PipelineManifest(
                kind="Workflow",
                metadata=Metadata(name="x"),
                spec=PipelineSpec(
                    backend="dvc",
                    steps=[StepSpec.model_validate({"name": "s", "class": "a.B"})],
                ),
            )

    def test_valid_manifest_round_trips(self):
        pytest.importorskip("hera")
        import yaml

        data = yaml.safe_load(FULL_MANIFEST_YAML)
        manifest = PipelineManifest.model_validate(data)
        assert manifest.metadata.name == "full-pipeline"
        assert manifest.spec.backend == "argo"
        assert len(manifest.spec.steps) == 3
        assert len(manifest.spec.middlewares) == 2

    def test_minimal_manifest_valid(self):
        import yaml

        data = yaml.safe_load(MINIMAL_MANIFEST_YAML)
        manifest = PipelineManifest.model_validate(data)
        assert manifest.spec.backend == "dvc"
        assert manifest.spec.middlewares == []

    def test_backend_config_optional(self):
        manifest = PipelineManifest(
            metadata=Metadata(name="x"),
            spec=PipelineSpec(
                backend="dvc",
                steps=[StepSpec.model_validate({"name": "s", "class": "a.B"})],
            ),
        )
        assert manifest.spec.backendConfig == BackendConfig()

    def test_dvc_manifest_config(self):
        import yaml

        data = yaml.safe_load(MINIMAL_MANIFEST_YAML)
        data["spec"]["backendConfig"] = {"dvc": {"dataDir": "./mydata", "encapsulateEnv": False}}
        manifest = PipelineManifest.model_validate(data)
        dvc_cfg = manifest.spec.backendConfig.get_for("dvc")
        assert dvc_cfg["dataDir"] == "./mydata"
        assert dvc_cfg["encapsulateEnv"] is False
