# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Edge case tests for backend implementations."""

from pathlib import Path

import pytest

from wurzel.core import NoSettings, TypedStep
from wurzel.core.settings import SettingsLeaf
from wurzel.datacontract.common import MarkdownDataContract
from wurzel.executors.backend.backend_dvc import DvcBackend, DvcBackendSettings
from wurzel.utils import HAS_HERA

if HAS_HERA:
    from wurzel.executors.backend.backend_argo import ArgoBackend, WorkflowConfig


class DummyStep(TypedStep[NoSettings, None, MarkdownDataContract]):
    """A simple step with no dependencies for testing."""

    def run(self, inpt: None) -> MarkdownDataContract:
        return MarkdownDataContract(content="test")


class DummyFollowStep(TypedStep[NoSettings, MarkdownDataContract, MarkdownDataContract]):
    """A step that accepts MarkdownDataContract as input."""

    def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
        return inpt


class StepWithSettings(TypedStep["CustomSettings", None, MarkdownDataContract]):
    """A step with custom settings for testing."""

    def run(self, inpt: None) -> MarkdownDataContract:
        return MarkdownDataContract(content=f"test-{self.settings.value}")


class CustomSettings(SettingsLeaf):
    """Custom settings for testing."""

    value: str = "default"


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

    def test_generate_artifact_with_special_characters_in_path(self, tmp_path):
        """Test DvcBackend handles paths with special characters."""
        special_path = tmp_path / "path with spaces" / "and-dashes"
        settings = DvcBackendSettings(DATA_DIR=special_path)
        backend = DvcBackend(settings=settings)
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)
        assert yaml_output is not None

    def test_generate_artifact_with_deeply_nested_path(self, tmp_path):
        """Test DvcBackend handles deeply nested directory paths."""
        deep_path = tmp_path / "a" / "b" / "c" / "d" / "e" / "f" / "g"
        settings = DvcBackendSettings(DATA_DIR=deep_path)
        backend = DvcBackend(settings=settings)
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)
        assert str(deep_path) in yaml_output

    def test_multiple_backends_with_different_settings(self, tmp_path):
        """Test creating multiple backend instances with different settings."""
        backend1 = DvcBackend(settings=DvcBackendSettings(DATA_DIR=tmp_path / "dir1"))
        backend2 = DvcBackend(settings=DvcBackendSettings(DATA_DIR=tmp_path / "dir2"))

        step = DummyStep()
        yaml1 = backend1.generate_artifact(step)
        yaml2 = backend2.generate_artifact(step)

        assert "dir1" in yaml1
        assert "dir2" in yaml2
        assert yaml1 != yaml2

    def test_backend_with_empty_middlewares_list(self):
        """Test DvcBackend with empty middlewares list."""
        backend = DvcBackend(middlewares=[])
        assert backend is not None

    def test_backend_settings_with_relative_path(self):
        """Test DvcBackend with relative path in settings."""
        settings = DvcBackendSettings(DATA_DIR=Path("./relative/path"))
        backend = DvcBackend(settings=settings)
        assert backend.settings.DATA_DIR == Path("./relative/path")

    def test_backend_with_both_middlewares_and_dont_encapsulate(self):
        """Test DvcBackend with both middlewares and dont_encapsulate set."""
        backend = DvcBackend(middlewares=["prometheus"], dont_encapsulate=True)
        assert backend is not None

    def test_generate_artifact_preserves_step_history(self):
        """Test that generate_artifact preserves step history in output."""
        backend = DvcBackend()
        step1 = DummyStep()
        step2 = DummyFollowStep()
        step3 = DummyFollowStep()
        step1 >> step2 >> step3

        yaml_output = backend.generate_artifact(step3)
        # Should contain all steps in the chain
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
        # DNS labels can be up to 63 characters
        max_name = "a" * 63
        config = WorkflowConfig(name=max_name)
        backend = ArgoBackend(config=config)
        assert backend.config.name == max_name

    def test_multiple_s3_artifact_configurations(self):
        """Test creating multiple S3 artifact configurations."""
        from wurzel.executors.backend.backend_argo import S3ArtifactConfig

        s3_config1 = S3ArtifactConfig(bucket="bucket1", endpoint="s3.region1.com")
        s3_config2 = S3ArtifactConfig(bucket="bucket2", endpoint="s3.region2.com")

        assert s3_config1.bucket != s3_config2.bucket
        assert s3_config1.endpoint != s3_config2.endpoint


class TestBackendSettingsValidation:
    def test_dvc_settings_with_invalid_path_type(self):
        """Test DvcBackendSettings rejects invalid path types."""
        with pytest.raises(Exception):
            DvcBackendSettings(DATA_DIR=123)  # type: ignore

    def test_dvc_settings_encapsulate_env_type_validation(self):
        """Test DvcBackendSettings validates ENCAPSULATE_ENV type."""
        settings = DvcBackendSettings(ENCAPSULATE_ENV=True)
        assert settings.ENCAPSULATE_ENV is True

        settings = DvcBackendSettings(ENCAPSULATE_ENV=False)
        assert settings.ENCAPSULATE_ENV is False

    @pytest.mark.skipif(not HAS_HERA, reason="Hera not available")
    def test_argo_workflow_config_validation(self):
        """Test WorkflowConfig validates fields correctly."""
        config = WorkflowConfig(name="test", namespace="test-ns")
        assert config.name == "test"
        assert config.namespace == "test-ns"


class TestBackendEnvironmentVariableHandling:
    def test_dvc_backend_clears_env_after_settings_load(self, monkeypatch):
        """Test that environment variables don't persist between backend instances."""
        monkeypatch.setenv("DVCBACKEND__DATA_DIR", "/tmp/test1")
        backend1 = DvcBackend(settings=DvcBackendSettings())

        monkeypatch.setenv("DVCBACKEND__DATA_DIR", "/tmp/test2")
        backend2 = DvcBackend(settings=DvcBackendSettings())

        # Each backend should have its own settings
        assert backend1.settings.DATA_DIR != backend2.settings.DATA_DIR

    def test_dvc_backend_env_override_precedence(self, monkeypatch, tmp_path):
        """Test that environment variables take precedence over defaults."""
        custom_path = tmp_path / "custom"
        monkeypatch.setenv("DVCBACKEND__DATA_DIR", str(custom_path))

        settings = DvcBackendSettings()
        assert settings.DATA_DIR == custom_path

    @pytest.mark.skipif(not HAS_HERA, reason="Hera not available")
    def test_argo_backend_custom_config(self):
        """Test ArgoBackend with custom WorkflowConfig."""
        config = WorkflowConfig(
            name="my-pipeline",
            namespace="prod",
        )
        config.container.image = "custom:v1"

        backend = ArgoBackend(config=config)
        assert backend.config.name == "my-pipeline"
        assert backend.config.namespace == "prod"
        assert backend.config.container.image == "custom:v1"


class TestBackendOutputFormat:
    def test_dvc_output_is_valid_yaml_structure(self):
        """Test that DvcBackend generates valid YAML structure."""
        backend = DvcBackend()
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        # Basic YAML structure checks
        assert "stages:" in yaml_output
        assert "cmd:" in yaml_output
        assert "deps:" in yaml_output or "outs:" in yaml_output

    @pytest.mark.skipif(not HAS_HERA, reason="Hera not available")
    def test_argo_output_is_valid_yaml_structure(self):
        """Test that ArgoBackend generates valid YAML structure."""
        backend = ArgoBackend()
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        # Basic YAML structure checks
        assert "apiVersion:" in yaml_output
        assert "kind:" in yaml_output
        assert "metadata:" in yaml_output
        assert "spec:" in yaml_output

    def test_dvc_output_contains_wurzel_command(self):
        """Test that DVC output contains wurzel run command."""
        backend = DvcBackend()
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        assert "wurzel run" in yaml_output

    def test_dvc_output_contains_step_module_path(self):
        """Test that DVC output contains the step's module path."""
        backend = DvcBackend()
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        # Should contain reference to the test module
        assert "DummyStep" in yaml_output
