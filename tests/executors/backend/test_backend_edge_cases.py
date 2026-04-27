# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Edge case tests for backend implementations."""

from pathlib import Path

import pytest

from wurzel.core import NoSettings, TypedStep
from wurzel.datacontract.common import MarkdownDataContract
from wurzel.executors.backend.backend_dvc import DvcBackend, DvcBackendSettings
from wurzel.utils import HAS_HERA

from .helpers import DummyFollowStep, DummyStep

if HAS_HERA:
    from wurzel.executors.backend.backend_argo import ArgoBackend, WorkflowConfig


# ── path parametrization (module-level, not class-bound) ─────────────────────


@pytest.mark.parametrize(
    "sub_path",
    [
        pytest.param("path with spaces/and-dashes", id="spaces_and_dashes"),
        pytest.param("a/b/c/d/e/f/g", id="deeply_nested"),
        pytest.param("normal-path", id="normal"),
    ],
)
def test_generate_artifact_with_various_paths(tmp_path, sub_path):
    """Test DvcBackend handles various path structures without errors."""
    target_path = tmp_path / sub_path
    settings = DvcBackendSettings(DATA_DIR=target_path)
    backend = DvcBackend(settings=settings)
    yaml_output = backend.generate_artifact(DummyStep())
    assert yaml_output is not None
    # Check path component appears somewhere in the output (YAML may wrap long lines)
    assert target_path.name in yaml_output


# ── DVC edge cases ────────────────────────────────────────────────────────────


class TestDvcBackendEdgeCases:
    def test_generate_artifact_with_very_long_step_name(self):
        """Test DvcBackend handles very long step names."""

        class VeryLongStepNameThatExceedsNormalLengthLimits(TypedStep[NoSettings, None, MarkdownDataContract]):
            def run(self, inpt: None) -> MarkdownDataContract:
                return MarkdownDataContract(content="test")

        backend = DvcBackend()
        step = VeryLongStepNameThatExceedsNormalLengthLimits()
        yaml_output = backend.generate_artifact(step)

        assert "VeryLongStepNameThatExceedsNormalLengthLimits" in yaml_output

    def test_multiple_backends_with_different_settings(self, tmp_path):
        """Test creating multiple backend instances with different settings."""
        backend1 = DvcBackend(settings=DvcBackendSettings(DATA_DIR=tmp_path / "dir1"))
        backend2 = DvcBackend(settings=DvcBackendSettings(DATA_DIR=tmp_path / "dir2"))

        yaml1 = backend1.generate_artifact(DummyStep())
        yaml2 = backend2.generate_artifact(DummyStep())

        assert "dir1" in yaml1
        assert "dir2" in yaml2
        assert yaml1 != yaml2

    def test_backend_settings_with_relative_path(self):
        """Test DvcBackend with relative path in settings."""
        settings = DvcBackendSettings(DATA_DIR=Path("./relative/path"))
        backend = DvcBackend(settings=settings)
        assert backend.settings.DATA_DIR == Path("./relative/path")

    def test_generate_artifact_preserves_step_history(self):
        """Test that generate_artifact preserves step history in output."""
        backend = DvcBackend()
        step1 = DummyStep()
        step2 = DummyFollowStep()
        step3 = DummyFollowStep()
        step1 >> step2 >> step3

        yaml_output = backend.generate_artifact(step3)
        assert "DummyStep" in yaml_output
        assert "DummyFollowStep" in yaml_output


@pytest.mark.skipif(not HAS_HERA, reason="Hera not available")
class TestArgoBackendEdgeCases:
    def test_generate_artifact_with_very_long_step_name(self):
        """Test ArgoBackend handles very long step names."""

        class VeryLongStepNameThatExceedsNormalLengthLimits(TypedStep[NoSettings, None, MarkdownDataContract]):
            def run(self, inpt: None) -> MarkdownDataContract:
                return MarkdownDataContract(content="test")

        backend = ArgoBackend()
        step = VeryLongStepNameThatExceedsNormalLengthLimits()
        yaml_output = backend.generate_artifact(step)

        assert yaml_output is not None
        assert "kind:" in yaml_output

    def test_pipeline_name_with_maximum_length(self):
        """Test ArgoBackend with maximum allowed pipeline name length."""
        max_name = "a" * 63  # DNS labels can be up to 63 characters
        config = WorkflowConfig(name=max_name)
        backend = ArgoBackend(config=config)
        assert backend.config.name == max_name

    def test_multiple_s3_artifact_configurations(self):
        """Test creating multiple S3 artifact configurations."""
        from wurzel.executors.backend.backend_argo import S3ArtifactConfig  # noqa: PLC0415

        s3_config1 = S3ArtifactConfig(bucket="bucket1", endpoint="s3.region1.com")
        s3_config2 = S3ArtifactConfig(bucket="bucket2", endpoint="s3.region2.com")

        assert s3_config1.bucket != s3_config2.bucket
        assert s3_config1.endpoint != s3_config2.endpoint


# ── settings validation ───────────────────────────────────────────────────────


class TestBackendSettingsValidation:
    def test_dvc_settings_with_invalid_path_type(self):
        """Test DvcBackendSettings rejects invalid path types."""
        with pytest.raises(Exception):
            DvcBackendSettings(DATA_DIR=123)  # type: ignore

    @pytest.mark.parametrize("value", [True, False])
    def test_dvc_settings_encapsulate_env_type_validation(self, value):
        """Test DvcBackendSettings stores the ENCAPSULATE_ENV value correctly."""
        settings = DvcBackendSettings(ENCAPSULATE_ENV=value)
        assert settings.ENCAPSULATE_ENV is value

    @pytest.mark.skipif(not HAS_HERA, reason="Hera not available")
    def test_argo_workflow_config_validation(self):
        """Test WorkflowConfig validates fields correctly."""
        config = WorkflowConfig(name="test", namespace="test-ns")
        assert config.name == "test"
        assert config.namespace == "test-ns"


# ── environment variable handling ────────────────────────────────────────────


class TestBackendEnvironmentVariableHandling:
    def test_dvc_backend_clears_env_after_settings_load(self, monkeypatch):
        """Test that environment variables don't persist between backend instances."""
        monkeypatch.setenv("DVCBACKEND__DATA_DIR", "/tmp/test1")
        backend1 = DvcBackend(settings=DvcBackendSettings())

        monkeypatch.setenv("DVCBACKEND__DATA_DIR", "/tmp/test2")
        backend2 = DvcBackend(settings=DvcBackendSettings())

        assert backend1.settings.DATA_DIR != backend2.settings.DATA_DIR

    def test_dvc_backend_env_override_precedence(self, monkeypatch, tmp_path):
        """Test that environment variables take precedence over defaults."""
        custom_path = tmp_path / "custom"
        monkeypatch.setenv("DVCBACKEND__DATA_DIR", str(custom_path))
        assert DvcBackendSettings().DATA_DIR == custom_path

    @pytest.mark.skipif(not HAS_HERA, reason="Hera not available")
    def test_argo_backend_custom_config(self):
        """Test ArgoBackend with custom WorkflowConfig."""
        config = WorkflowConfig(name="my-pipeline", namespace="prod")
        config.container.image = "custom:v1"

        backend = ArgoBackend(config=config)
        assert backend.config.name == "my-pipeline"
        assert backend.config.namespace == "prod"
        assert backend.config.container.image == "custom:v1"


# ── YAML output format ────────────────────────────────────────────────────────


class TestBackendOutputFormat:
    def test_dvc_output_is_valid_yaml_structure(self):
        """Test that DvcBackend generates valid YAML structure."""
        yaml_output = DvcBackend().generate_artifact(DummyStep())
        assert "stages:" in yaml_output
        assert "cmd:" in yaml_output
        assert "deps:" in yaml_output or "outs:" in yaml_output

    @pytest.mark.skipif(not HAS_HERA, reason="Hera not available")
    def test_argo_output_is_valid_yaml_structure(self):
        """Test that ArgoBackend generates valid YAML structure."""
        yaml_output = ArgoBackend().generate_artifact(DummyStep())
        assert "apiVersion:" in yaml_output
        assert "kind:" in yaml_output
        assert "metadata:" in yaml_output
        assert "spec:" in yaml_output

    def test_dvc_output_contains_wurzel_command(self):
        """Test that DVC output contains wurzel run command."""
        assert "wurzel run" in DvcBackend().generate_artifact(DummyStep())

    def test_dvc_output_contains_step_name(self):
        """Test that DVC output contains the step's class name."""
        assert "DummyStep" in DvcBackend().generate_artifact(DummyStep())
