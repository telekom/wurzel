# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for run_id functionality in backends."""

import pytest

from wurzel.core import NoSettings, TypedStep
from wurzel.datacontract.common import MarkdownDataContract
from wurzel.executors.backend import Backend
from wurzel.executors.backend.backend_dvc import DvcBackend
from wurzel.utils import HAS_HERA

if HAS_HERA:
    from wurzel.executors.backend.backend_argo import ArgoBackend


class DummyStep(TypedStep[NoSettings, None, MarkdownDataContract]):
    """A simple step for testing."""

    def run(self, inpt: None) -> MarkdownDataContract:
        return MarkdownDataContract(content="test")


class TestBackendRunId:
    def test_backend_has_run_id_property(self):
        """Test that Backend base class has run_id property."""
        backend = Backend()
        assert hasattr(backend, "run_id")

    def test_backend_run_id_reads_from_environment(self, monkeypatch):
        """Test that run_id property reads from WURZEL_RUN_ID environment variable."""
        test_run_id = "test-run-12345"
        monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

        backend = Backend()
        assert backend.run_id == test_run_id

    def test_backend_run_id_returns_empty_when_not_set(self, monkeypatch):
        """Test that run_id returns empty string when WURZEL_RUN_ID is not set."""
        monkeypatch.delenv("WURZEL_RUN_ID", raising=False)

        backend = Backend()
        assert backend.run_id == ""

    def test_backend_run_id_updates_when_env_changes(self, monkeypatch):
        """Test that run_id reflects changes to environment variable."""
        backend = Backend()

        monkeypatch.setenv("WURZEL_RUN_ID", "run-1")
        assert backend.run_id == "run-1"

        monkeypatch.setenv("WURZEL_RUN_ID", "run-2")
        assert backend.run_id == "run-2"


class TestDvcBackendRunId:
    def test_dvc_backend_has_run_id_property(self):
        """Test that DvcBackend inherits run_id property."""
        backend = DvcBackend()
        assert hasattr(backend, "run_id")

    def test_dvc_backend_run_id_reads_from_environment(self, monkeypatch):
        """Test that DvcBackend run_id reads from environment."""
        test_run_id = "dvc-run-67890"
        monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

        backend = DvcBackend()
        assert backend.run_id == test_run_id

    def test_dvc_generated_artifact_includes_wurzel_run_id(self):
        """Test that DVC generated artifacts include WURZEL_RUN_ID environment variable."""
        backend = DvcBackend()
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)

        # Check that WURZEL_RUN_ID is set in the command
        assert "WURZEL_RUN_ID=" in yaml_output
        assert "dvc-$(date" in yaml_output or "WURZEL_RUN_ID:-" in yaml_output

    def test_dvc_run_id_uses_timestamp_fallback(self):
        """Test that DVC uses timestamp-based fallback for run_id."""
        backend = DvcBackend()
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)

        # Verify the fallback pattern is present
        assert "${WURZEL_RUN_ID:-dvc-$(date +%Y%m%d-%H%M%S)-$$}" in yaml_output

    def test_dvc_run_id_in_all_stages(self):
        """Test that WURZEL_RUN_ID is set for all stages in a multi-step pipeline."""
        backend = DvcBackend()

        class Step1(TypedStep[NoSettings, None, MarkdownDataContract]):
            def run(self, inpt: None) -> MarkdownDataContract:
                return MarkdownDataContract(content="step1")

        class Step2(TypedStep[NoSettings, MarkdownDataContract, MarkdownDataContract]):
            def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
                return inpt

        step1 = Step1()
        step2 = Step2()
        step1 >> step2

        yaml_output = backend.generate_artifact(step2)

        # Count occurrences of WURZEL_RUN_ID in the output
        run_id_count = yaml_output.count("WURZEL_RUN_ID=")
        assert run_id_count >= 2  # Should appear for both steps


@pytest.mark.skipif(not HAS_HERA, reason="Hera not available")
class TestArgoBackendRunId:
    def test_argo_backend_has_run_id_property(self):
        """Test that ArgoBackend inherits run_id property."""
        backend = ArgoBackend()
        assert hasattr(backend, "run_id")

    def test_argo_backend_run_id_reads_from_environment(self, monkeypatch):
        """Test that ArgoBackend run_id reads from environment."""
        test_run_id = "argo-workflow-abc123"
        monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

        backend = ArgoBackend()
        assert backend.run_id == test_run_id

    def test_argo_generated_artifact_includes_workflow_uid(self):
        """Test that Argo generated artifacts include workflow.uid as WURZEL_RUN_ID."""
        backend = ArgoBackend()
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)

        # Check that workflow.uid is used for WURZEL_RUN_ID
        assert "WURZEL_RUN_ID" in yaml_output
        assert "{{workflow.uid}}" in yaml_output

    def test_argo_run_id_in_environment_variables(self):
        """Test that WURZEL_RUN_ID is set as an environment variable in Argo tasks."""
        backend = ArgoBackend()
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)

        # Verify the environment variable is properly set
        assert "name: WURZEL_RUN_ID" in yaml_output or "name: 'WURZEL_RUN_ID'" in yaml_output
        assert "value: '{{workflow.uid}}'" in yaml_output or 'value: "{{workflow.uid}}"' in yaml_output

    def test_argo_run_id_in_all_tasks(self):
        """Test that WURZEL_RUN_ID is set for all tasks in a multi-step pipeline."""
        backend = ArgoBackend()

        class Step1(TypedStep[NoSettings, None, MarkdownDataContract]):
            def run(self, inpt: None) -> MarkdownDataContract:
                return MarkdownDataContract(content="step1")

        class Step2(TypedStep[NoSettings, MarkdownDataContract, MarkdownDataContract]):
            def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
                return inpt

        step1 = Step1()
        step2 = Step2()
        step1 >> step2

        yaml_output = backend.generate_artifact(step2)

        # Count occurrences of WURZEL_RUN_ID in the output
        run_id_count = yaml_output.count("WURZEL_RUN_ID")
        assert run_id_count >= 2  # Should appear for both tasks


class TestRunIdUseCases:
    def test_run_id_can_be_used_for_prometheus_job_name(self, monkeypatch):
        """Test that run_id can be used for Prometheus job naming."""
        test_run_id = "prometheus-job-12345"
        monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

        backend = DvcBackend()

        # Simulate using run_id for Prometheus job name
        prometheus_job_name = f"wurzel-pipeline-{backend.run_id}"
        assert prometheus_job_name == f"wurzel-pipeline-{test_run_id}"

    def test_run_id_can_be_used_for_logging(self, monkeypatch):
        """Test that run_id can be used for logging and tracing."""
        test_run_id = "log-trace-67890"
        monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

        backend = DvcBackend()

        # Simulate using run_id for logging
        log_message = f"Pipeline execution {backend.run_id} started"
        assert test_run_id in log_message

    def test_run_id_persists_across_backend_instances(self, monkeypatch):
        """Test that run_id is consistent across different backend instances."""
        test_run_id = "shared-run-id-999"
        monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

        backend1 = DvcBackend()
        backend2 = DvcBackend()

        assert backend1.run_id == backend2.run_id == test_run_id

    @pytest.mark.skipif(not HAS_HERA, reason="Hera not available")
    def test_run_id_different_between_dvc_and_argo_at_runtime(self, monkeypatch):
        """Test that run_id reflects the orchestrator-specific value at runtime."""
        # Simulate DVC runtime
        monkeypatch.setenv("WURZEL_RUN_ID", "dvc-20250120-123456-1234")
        dvc_backend = DvcBackend()
        dvc_run_id = dvc_backend.run_id

        # Simulate Argo runtime
        monkeypatch.setenv("WURZEL_RUN_ID", "argo-workflow-abc-def-123")
        argo_backend = ArgoBackend()
        argo_run_id = argo_backend.run_id

        # At runtime, they would have different values based on the orchestrator
        assert dvc_run_id != argo_run_id


class TestRunIdDocumentation:
    def test_backend_docstring_mentions_run_id(self):
        """Test that Backend class docstring documents run_id functionality."""
        assert "WURZEL_RUN_ID" in Backend.__doc__

    def test_backend_run_id_property_has_docstring(self):
        """Test that run_id property has documentation."""
        assert Backend.run_id.fget.__doc__ is not None
        assert "unique run id" in Backend.run_id.fget.__doc__.lower()
