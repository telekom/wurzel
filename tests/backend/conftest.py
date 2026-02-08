# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Shared fixtures for backend tests."""

import os
from pathlib import Path

import pytest
import yaml

from wurzel.utils import HAS_HERA

if HAS_HERA:
    from wurzel.core import NoSettings, TypedStep
    from wurzel.datacontract.common import MarkdownDataContract
    from wurzel.executors.backend.backend_argo import (
        ContainerConfig,
        S3ArtifactConfig,
        WorkflowConfig,
    )


@pytest.fixture(scope="function", autouse=True)
def setup_argo_test_env():
    """Preset environment variables for Argo tests.

    This fixture runs automatically before each test function to ensure
    a clean environment state. It clears any potentially interfering
    environment variables and sets up necessary defaults.
    """
    # Store original environment
    original_env = {}
    env_vars_to_clear = [
        "ARGO_NAMESPACE",
        "ARGO_SERVER",
        "ARGO_TOKEN",
        "KUBECONFIG",
    ]

    for var in env_vars_to_clear:
        if var in os.environ:
            original_env[var] = os.environ[var]
            del os.environ[var]

    yield

    # Restore original environment
    for var in env_vars_to_clear:
        if var in original_env:
            os.environ[var] = original_env[var]
        elif var in os.environ:
            del os.environ[var]


@pytest.fixture
def sample_workflow_config() -> "WorkflowConfig":
    """Create a sample WorkflowConfig for testing.

    Returns:
        WorkflowConfig with test-appropriate defaults.
    """
    if not HAS_HERA:
        pytest.skip("Hera is not available")

    return WorkflowConfig(
        name="test-workflow",
        namespace="test-namespace",
        schedule="0 4 * * *",
        entrypoint="test-pipeline",
        serviceAccountName="test-sa",
        container=ContainerConfig(
            image="test-image:latest",
            env={"TEST_VAR": "test_value"},
        ),
        artifacts=S3ArtifactConfig(
            bucket="test-bucket",
            endpoint="s3.test.com",
        ),
    )


@pytest.fixture
def workflow_config_no_schedule() -> "WorkflowConfig":
    """Create a WorkflowConfig without schedule for normal Workflow testing.

    Returns:
        WorkflowConfig with schedule=None for testing normal Workflows.
    """
    if not HAS_HERA:
        pytest.skip("Hera is not available")

    return WorkflowConfig(
        name="test-workflow-no-cron",
        namespace="test-namespace",
        schedule=None,  # Explicitly no schedule - creates normal Workflow
        entrypoint="test-pipeline",
        serviceAccountName="test-sa",
    )


@pytest.fixture
def sample_values_yaml(tmp_path: Path) -> Path:
    """Create a sample values.yaml file for testing.

    Args:
        tmp_path: Pytest temporary path fixture.

    Returns:
        Path to the created values.yaml file.
    """
    content = {
        "workflows": {
            "test-workflow": {
                "name": "test-wf",
                "namespace": "test-ns",
                "schedule": "0 0 * * *",
                "container": {
                    "image": "test-image:latest",
                    "env": {"KEY1": "value1"},
                },
            },
            "no-schedule-workflow": {
                "name": "no-schedule-wf",
                "namespace": "test-ns",
                "schedule": None,  # Normal Workflow, not CronWorkflow
                "container": {
                    "image": "test-image:latest",
                },
            },
        },
    }
    file_path = tmp_path / "values.yaml"
    file_path.write_text(yaml.safe_dump(content))
    return file_path


if HAS_HERA:

    class DummyStep(TypedStep[NoSettings, None, MarkdownDataContract]):
        """A simple step with no dependencies for testing."""

        def run(self, inpt: None) -> MarkdownDataContract:
            return MarkdownDataContract(content="test")

    class DummyFollowStep(TypedStep[NoSettings, MarkdownDataContract, MarkdownDataContract]):
        """A step that depends on another step."""

        def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
            return inpt

    @pytest.fixture
    def dummy_step() -> "DummyStep":
        """Create a simple dummy step for testing.

        Returns:
            DummyStep instance with no dependencies.
        """
        return DummyStep()

    @pytest.fixture
    def dummy_step_with_dependency() -> "DummyFollowStep":
        """Create a step with a dependency for testing pipelines.

        Returns:
            DummyFollowStep instance that depends on DummyStep.
        """
        step1 = DummyStep()
        step2 = DummyFollowStep()
        step1 >> step2
        return step2
