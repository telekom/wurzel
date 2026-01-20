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
from wurzel.executors.backend.backend_argo import ArgoBackend, S3ArtifactConfig, WorkflowConfig


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
        assert isinstance(backend.config, WorkflowConfig)

    def test_backend_with_custom_config(self):
        """Test ArgoBackend with custom config."""
        config = WorkflowConfig(name="test-pipeline", namespace="test-ns")
        backend = ArgoBackend(config=config)
        assert backend.config.name == "test-pipeline"
        assert backend.config.namespace == "test-ns"

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

    def test_workflow_config_defaults(self):
        """Test WorkflowConfig has correct defaults."""
        config = WorkflowConfig()
        assert config.name == "wurzel"
        assert config.namespace == "argo-workflows"
        assert config.schedule == "0 4 * * *"

    def test_s3_artifact_config(self):
        """Test S3ArtifactConfig settings."""
        s3_config = S3ArtifactConfig(bucket="my-bucket", endpoint="s3.example.com")
        assert s3_config.bucket == "my-bucket"
        assert s3_config.endpoint == "s3.example.com"

    def test_workflow_config_custom_image(self):
        """Test WorkflowConfig with custom container image."""
        config = WorkflowConfig()
        config.container.image = "custom-image:v1"
        assert config.container.image == "custom-image:v1"

    def test_is_available(self):
        """Test ArgoBackend.is_available() returns True when Hera is installed."""
        assert ArgoBackend.is_available() is True

    def test_workflow_config_schedule_optional(self):
        """Test WorkflowConfig schedule can be None for manual workflows."""
        config = WorkflowConfig(schedule=None)
        assert config.schedule is None

    def test_generate_workflow_returns_dict(self):
        """Test _generate_workflow returns a workflow object."""
        backend = ArgoBackend()
        step = DummyStep()

        workflow = backend._generate_workflow(step)

        assert workflow is not None
        assert hasattr(workflow, "to_dict")

    def test_wurzel_run_id_in_output(self):
        """Test that WURZEL_RUN_ID is included in generated workflow."""
        backend = ArgoBackend()
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)

        assert "WURZEL_RUN_ID" in yaml_output
        assert "{{workflow.uid}}" in yaml_output

    def test_backend_with_custom_executor(self):
        """Test ArgoBackend can be initialized with custom executor."""
        from wurzel.executors.base_executor import BaseStepExecutor

        backend = ArgoBackend(executor=BaseStepExecutor)
        assert backend is not None
        assert backend.executor == BaseStepExecutor

    def test_s3_artifact_config_defaults(self):
        """Test S3ArtifactConfig has correct defaults."""
        s3_config = S3ArtifactConfig()
        assert s3_config.bucket == "wurzel-bucket"
        assert s3_config.endpoint == "s3.amazonaws.com"
