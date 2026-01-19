# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for ArgoBackend with refactored structure."""

import pytest

from wurzel.utils import HAS_HERA

if not HAS_HERA:
    pytest.skip("Hera is not available", allow_module_level=True)

from wurzel.core import NoSettings, TypedStep
from wurzel.datacontract.common import MarkdownDataContract
from wurzel.executors.backend.backend_argo import ArgoBackend, ArgoBackendSettings, S3ArtifactTemplate


class DummyStep(TypedStep[NoSettings, None, MarkdownDataContract]):
    """A simple step with no dependencies for testing."""

    def run(self, inpt: None) -> MarkdownDataContract:
        return MarkdownDataContract(content="test")


class DummyFollowStep(TypedStep[NoSettings, MarkdownDataContract, MarkdownDataContract]):
    """A step that depends on another step."""

    def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
        return inpt


class TestArgoBackend:
    def test_backend_initialization(self):
        """Test ArgoBackend can be initialized."""
        backend = ArgoBackend()
        assert backend is not None
        assert isinstance(backend.settings, ArgoBackendSettings)

    def test_backend_with_custom_settings(self):
        """Test ArgoBackend with custom settings."""
        settings = ArgoBackendSettings(IMAGE="custom-image:latest", PIPELINE_NAME="test-pipeline", NAMESPACE="test-ns")
        backend = ArgoBackend(settings=settings)
        assert backend.settings.IMAGE == "custom-image:latest"
        assert backend.settings.PIPELINE_NAME == "test-pipeline"
        assert backend.settings.NAMESPACE == "test-ns"

    def test_generate_artifact_single_step(self):
        """Test generating Argo Workflow YAML for a single step."""
        backend = ArgoBackend()
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)

        assert yaml_output is not None
        assert "apiVersion:" in yaml_output
        assert "kind: CronWorkflow" in yaml_output
        assert "spec:" in yaml_output

    def test_generate_artifact_chained_steps(self):
        """Test generating Argo Workflow YAML for chained steps."""
        backend = ArgoBackend()
        step1 = DummyStep()
        step2 = DummyFollowStep()
        step1 >> step2

        yaml_output = backend.generate_artifact(step2)

        assert "DummyStep" in yaml_output
        assert "DummyFollowStep" in yaml_output
        assert "tasks:" in yaml_output

    def test_backend_settings_from_env(self, monkeypatch):
        """Test ArgoBackend settings can be loaded from environment."""
        monkeypatch.setenv("ARGOWORKFLOWBACKEND__IMAGE", "test-image:v1")
        monkeypatch.setenv("ARGOWORKFLOWBACKEND__NAMESPACE", "custom-ns")
        monkeypatch.setenv("ARGOWORKFLOWBACKEND__PIPELINE_NAME", "my-pipeline")

        settings = ArgoBackendSettings()
        assert settings.IMAGE == "test-image:v1"
        assert settings.NAMESPACE == "custom-ns"
        assert settings.PIPELINE_NAME == "my-pipeline"

    def test_s3_artifact_template_settings(self):
        """Test S3ArtifactTemplate settings."""
        s3_config = S3ArtifactTemplate(bucket="my-bucket", endpoint="s3.example.com")
        assert s3_config.bucket == "my-bucket"
        assert s3_config.endpoint == "s3.example.com"

    def test_inline_step_settings_disabled_by_default(self):
        """Test INLINE_STEP_SETTINGS is disabled by default."""
        settings = ArgoBackendSettings()
        assert settings.INLINE_STEP_SETTINGS is False

    def test_inline_step_settings_can_be_enabled(self, monkeypatch):
        """Test INLINE_STEP_SETTINGS can be enabled via environment."""
        monkeypatch.setenv("ARGOWORKFLOWBACKEND__INLINE_STEP_SETTINGS", "true")
        settings = ArgoBackendSettings()
        assert settings.INLINE_STEP_SETTINGS is True

    def test_is_available(self):
        """Test ArgoBackend.is_available() returns True when Hera is installed."""
        assert ArgoBackend.is_available() is True

    def test_pipeline_name_validation(self):
        """Test pipeline name must follow DNS label rules."""
        # Valid names
        ArgoBackendSettings(PIPELINE_NAME="valid-name")
        ArgoBackendSettings(PIPELINE_NAME="name123")

        # Invalid names should raise validation error
        with pytest.raises(Exception):  # Pydantic ValidationError
            ArgoBackendSettings(PIPELINE_NAME="Invalid_Name")

        with pytest.raises(Exception):
            ArgoBackendSettings(PIPELINE_NAME="-invalid")

        with pytest.raises(Exception):
            ArgoBackendSettings(PIPELINE_NAME="invalid-")
