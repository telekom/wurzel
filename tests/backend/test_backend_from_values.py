# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend from_values functionality."""

from pathlib import Path

import pytest
import yaml

from wurzel.core import NoSettings, TypedStep
from wurzel.datacontract.common import MarkdownDataContract
from wurzel.executors.backend.backend_dvc import DvcBackend
from wurzel.utils import HAS_HERA


class DummyStep(TypedStep[NoSettings, None, MarkdownDataContract]):
    """A simple step with no dependencies for testing."""

    def run(self, inpt: None) -> MarkdownDataContract:
        return MarkdownDataContract(content="test")


class DummyFollowStep(TypedStep[NoSettings, MarkdownDataContract, MarkdownDataContract]):
    """A step that depends on another step."""

    def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
        return inpt


class TestDvcBackendFromValues:
    """Tests for DvcBackend.from_values method."""

    def test_from_values_basic(self, tmp_path):
        """Test DvcBackend.from_values with basic configuration."""
        values_file = tmp_path / "values.yaml"
        values_data = {
            "dvc": {
                "test-pipeline": {
                    "dataDir": "./custom-data",
                    "encapsulateEnv": False,
                }
            }
        }
        values_file.write_text(yaml.dump(values_data))

        backend = DvcBackend.from_values([values_file])

        assert backend.config.dataDir == Path("./custom-data")
        assert backend.config.encapsulateEnv is False

    def test_from_values_with_defaults(self, tmp_path):
        """Test DvcBackend.from_values with empty values file uses defaults."""
        values_file = tmp_path / "values.yaml"
        values_file.write_text(yaml.dump({"dvc": {}}))

        backend = DvcBackend.from_values([values_file])

        assert backend.config.dataDir == Path("./data")
        assert backend.config.encapsulateEnv is True

    def test_from_values_multiple_files(self, tmp_path):
        """Test DvcBackend.from_values merges multiple values files."""
        values_file1 = tmp_path / "values1.yaml"
        values_file1.write_text(yaml.dump({"dvc": {"test": {"dataDir": "./data1"}}}))

        values_file2 = tmp_path / "values2.yaml"
        values_file2.write_text(yaml.dump({"dvc": {"test": {"encapsulateEnv": False}}}))

        backend = DvcBackend.from_values([values_file1, values_file2])

        assert backend.config.dataDir == Path("./data1")
        assert backend.config.encapsulateEnv is False

    def test_from_values_override(self, tmp_path):
        """Test DvcBackend.from_values with later files overriding earlier ones."""
        values_file1 = tmp_path / "values1.yaml"
        values_file1.write_text(yaml.dump({"dvc": {"test": {"dataDir": "./data1"}}}))

        values_file2 = tmp_path / "values2.yaml"
        values_file2.write_text(yaml.dump({"dvc": {"test": {"dataDir": "./data2"}}}))

        backend = DvcBackend.from_values([values_file1, values_file2])

        assert backend.config.dataDir == Path("./data2")

    def test_from_values_generate_artifact(self, tmp_path):
        """Test that backend created from values can generate artifacts."""
        values_file = tmp_path / "values.yaml"
        values_file.write_text(yaml.dump({"dvc": {"test": {"dataDir": "./test-output"}}}))

        backend = DvcBackend.from_values([values_file])
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)

        assert "test-output" in yaml_output
        assert "DummyStep" in yaml_output
        assert "WURZEL_RUN_ID" in yaml_output


@pytest.mark.skipif(not HAS_HERA, reason="Hera is not available")
class TestArgoBackendFromValues:
    """Tests for ArgoBackend.from_values method."""

    def test_from_values_basic(self, tmp_path):
        """Test ArgoBackend.from_values with basic workflow configuration."""
        from wurzel.executors.backend.backend_argo import ArgoBackend

        values_file = tmp_path / "values.yaml"
        values_data = {
            "workflows": {
                "test-workflow": {
                    "name": "test-pipeline",
                    "namespace": "test-namespace",
                    "schedule": "0 5 * * *",
                    "serviceAccountName": "test-sa",
                    "dataDir": "/test/data",
                }
            }
        }
        values_file.write_text(yaml.dump(values_data))

        backend = ArgoBackend.from_values([values_file])

        assert backend.config.name == "test-pipeline"
        assert backend.config.namespace == "test-namespace"
        assert backend.config.schedule == "0 5 * * *"
        assert backend.config.serviceAccountName == "test-sa"
        assert backend.config.dataDir == Path("/test/data")

    def test_from_values_with_workflow_name(self, tmp_path):
        """Test ArgoBackend.from_values selects specific workflow by name."""
        from wurzel.executors.backend.backend_argo import ArgoBackend

        values_file = tmp_path / "values.yaml"
        values_data = {
            "workflows": {
                "workflow1": {"name": "pipeline1", "namespace": "ns1"},
                "workflow2": {"name": "pipeline2", "namespace": "ns2"},
            }
        }
        values_file.write_text(yaml.dump(values_data))

        backend = ArgoBackend.from_values([values_file], workflow_name="workflow2")

        assert backend.config.name == "pipeline2"
        assert backend.config.namespace == "ns2"

    def test_from_values_first_workflow_default(self, tmp_path):
        """Test ArgoBackend.from_values uses first workflow when no name specified."""
        from wurzel.executors.backend.backend_argo import ArgoBackend

        values_file = tmp_path / "values.yaml"
        values_data = {
            "workflows": {
                "first": {"name": "first-pipeline"},
                "second": {"name": "second-pipeline"},
            }
        }
        values_file.write_text(yaml.dump(values_data))

        backend = ArgoBackend.from_values([values_file])

        # Should use first workflow (dict order is preserved in Python 3.7+)
        assert backend.config.name == "first-pipeline"

    def test_from_values_container_config(self, tmp_path):
        """Test ArgoBackend.from_values with container configuration."""
        from wurzel.executors.backend.backend_argo import ArgoBackend

        values_file = tmp_path / "values.yaml"
        values_data = {
            "workflows": {
                "test": {
                    "name": "test",
                    "container": {
                        "image": "custom-image:v1",
                        "env": {"MY_VAR": "my_value", "ANOTHER_VAR": "another_value"},
                    },
                }
            }
        }
        values_file.write_text(yaml.dump(values_data))

        backend = ArgoBackend.from_values([values_file])

        assert backend.config.container.image == "custom-image:v1"
        assert backend.config.container.env["MY_VAR"] == "my_value"
        assert backend.config.container.env["ANOTHER_VAR"] == "another_value"

    def test_from_values_s3_artifacts(self, tmp_path):
        """Test ArgoBackend.from_values with S3 artifact configuration."""
        from wurzel.executors.backend.backend_argo import ArgoBackend

        values_file = tmp_path / "values.yaml"
        values_data = {
            "workflows": {
                "test": {
                    "name": "test",
                    "artifacts": {
                        "bucket": "my-custom-bucket",
                        "endpoint": "s3.custom.com",
                        "defaultMode": 509,
                    },
                }
            }
        }
        values_file.write_text(yaml.dump(values_data))

        backend = ArgoBackend.from_values([values_file])

        assert backend.config.artifacts.bucket == "my-custom-bucket"
        assert backend.config.artifacts.endpoint == "s3.custom.com"
        assert backend.config.artifacts.defaultMode == 509

    def test_from_values_security_context(self, tmp_path):
        """Test ArgoBackend.from_values with security context configuration."""
        from wurzel.executors.backend.backend_argo import ArgoBackend

        values_file = tmp_path / "values.yaml"
        values_data = {
            "workflows": {
                "test": {
                    "name": "test",
                    "container": {
                        "securityContext": {
                            "runAsNonRoot": True,
                            "runAsUser": 1000,
                            "runAsGroup": 1000,
                            "allowPrivilegeEscalation": False,
                            "readOnlyRootFilesystem": True,
                        }
                    },
                }
            }
        }
        values_file.write_text(yaml.dump(values_data))

        backend = ArgoBackend.from_values([values_file])

        assert backend.config.container.securityContext.runAsNonRoot is True
        assert backend.config.container.securityContext.runAsUser == 1000
        assert backend.config.container.securityContext.runAsGroup == 1000
        assert backend.config.container.securityContext.allowPrivilegeEscalation is False
        assert backend.config.container.securityContext.readOnlyRootFilesystem is True

    def test_from_values_resources(self, tmp_path):
        """Test ArgoBackend.from_values with resource configuration."""
        from wurzel.executors.backend.backend_argo import ArgoBackend

        values_file = tmp_path / "values.yaml"
        values_data = {
            "workflows": {
                "test": {
                    "name": "test",
                    "container": {
                        "resources": {
                            "cpu_request": "200m",
                            "cpu_limit": "1000m",
                            "memory_request": "256Mi",
                            "memory_limit": "1Gi",
                        }
                    },
                }
            }
        }
        values_file.write_text(yaml.dump(values_data))

        backend = ArgoBackend.from_values([values_file])

        assert backend.config.container.resources.cpu_request == "200m"
        assert backend.config.container.resources.cpu_limit == "1000m"
        assert backend.config.container.resources.memory_request == "256Mi"
        assert backend.config.container.resources.memory_limit == "1Gi"

    def test_from_values_generate_artifact(self, tmp_path):
        """Test that ArgoBackend created from values can generate artifacts."""
        from wurzel.executors.backend.backend_argo import ArgoBackend

        values_file = tmp_path / "values.yaml"
        values_data = {
            "workflows": {
                "test": {
                    "name": "custom-workflow",
                    "namespace": "custom-ns",
                    "container": {"image": "custom-image:latest"},
                }
            }
        }
        values_file.write_text(yaml.dump(values_data))

        backend = ArgoBackend.from_values([values_file])
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)

        assert "custom-workflow" in yaml_output
        assert "custom-ns" in yaml_output
        assert "custom-image:latest" in yaml_output
        assert "WURZEL_RUN_ID" in yaml_output
        assert "{{workflow.uid}}" in yaml_output

    def test_from_values_multiple_files_merge(self, tmp_path):
        """Test ArgoBackend.from_values merges multiple values files."""
        from wurzel.executors.backend.backend_argo import ArgoBackend

        values_file1 = tmp_path / "values1.yaml"
        values_data1 = {
            "workflows": {
                "test": {
                    "name": "test",
                    "namespace": "default",
                    "container": {"image": "base-image:v1"},
                }
            }
        }
        values_file1.write_text(yaml.dump(values_data1))

        values_file2 = tmp_path / "values2.yaml"
        values_data2 = {
            "workflows": {
                "test": {
                    "namespace": "production",
                    "container": {"env": {"ENV": "prod"}},
                }
            }
        }
        values_file2.write_text(yaml.dump(values_data2))

        backend = ArgoBackend.from_values([values_file1, values_file2])

        assert backend.config.name == "test"
        assert backend.config.namespace == "production"  # Overridden
        assert backend.config.container.image == "base-image:v1"  # From first file
        assert backend.config.container.env["ENV"] == "prod"  # From second file

    def test_from_values_env_from_config(self, tmp_path):
        """Test ArgoBackend.from_values with envFrom configuration."""
        from wurzel.executors.backend.backend_argo import ArgoBackend

        values_file = tmp_path / "values.yaml"
        values_data = {
            "workflows": {
                "test": {
                    "name": "test",
                    "container": {
                        "envFrom": [
                            {"kind": "secret", "name": "my-secret", "prefix": "SECRET_", "optional": True},
                            {"kind": "configMap", "name": "my-config", "prefix": "CONFIG_", "optional": False},
                        ]
                    },
                }
            }
        }
        values_file.write_text(yaml.dump(values_data))

        backend = ArgoBackend.from_values([values_file])

        assert len(backend.config.container.envFrom) == 2
        assert backend.config.container.envFrom[0].kind == "secret"
        assert backend.config.container.envFrom[0].name == "my-secret"
        assert backend.config.container.envFrom[0].prefix == "SECRET_"
        assert backend.config.container.envFrom[1].kind == "configMap"
        assert backend.config.container.envFrom[1].name == "my-config"

    def test_from_values_invalid_workflow_name(self, tmp_path):
        """Test ArgoBackend.from_values raises error for invalid workflow name."""
        from wurzel.executors.backend.backend_argo import ArgoBackend

        values_file = tmp_path / "values.yaml"
        values_data = {"workflows": {"test": {"name": "test"}}}
        values_file.write_text(yaml.dump(values_data))

        with pytest.raises(ValueError, match="workflow 'nonexistent' not found"):
            ArgoBackend.from_values([values_file], workflow_name="nonexistent")

    def test_from_values_empty_workflows(self, tmp_path):
        """Test ArgoBackend.from_values with empty workflows uses defaults."""
        from wurzel.executors.backend.backend_argo import ArgoBackend

        values_file = tmp_path / "values.yaml"
        values_data = {"workflows": {}}
        values_file.write_text(yaml.dump(values_data))

        backend = ArgoBackend.from_values([values_file])

        # Should use default WorkflowConfig
        assert backend.config.name == "wurzel"
        assert backend.config.namespace == "argo-workflows"


class TestBackendFromValuesIntegration:
    """Integration tests for from_values across backends."""

    def test_dvc_backend_from_values_workflow(self, tmp_path):
        """Test complete DVC workflow with from_values."""
        values_file = tmp_path / "dvc-values.yaml"
        values_file.write_text(
            yaml.dump(
                {
                    "dvc": {
                        "test": {
                            "dataDir": str(tmp_path / "output"),
                            "encapsulateEnv": True,
                        }
                    }
                }
            )
        )

        backend = DvcBackend.from_values([values_file])
        step1 = DummyStep()
        step2 = DummyFollowStep()
        step1 >> step2

        yaml_output = backend.generate_artifact(step2)

        assert str(tmp_path / "output") in yaml_output
        assert "WURZEL_RUN_ID" in yaml_output
        assert "DummyStep" in yaml_output
        assert "DummyFollowStep" in yaml_output

    @pytest.mark.skipif(not HAS_HERA, reason="Hera is not available")
    def test_argo_backend_from_values_workflow(self, tmp_path):
        """Test complete Argo workflow with from_values."""
        from wurzel.executors.backend.backend_argo import ArgoBackend

        values_file = tmp_path / "argo-values.yaml"
        values_file.write_text(
            yaml.dump(
                {
                    "workflows": {
                        "integration-test": {
                            "name": "integration-pipeline",
                            "namespace": "integration-ns",
                            "schedule": "0 6 * * *",
                            "container": {
                                "image": "integration-image:v1",
                                "env": {"TEST_VAR": "test_value"},
                            },
                            "artifacts": {"bucket": "integration-bucket"},
                        }
                    }
                }
            )
        )

        backend = ArgoBackend.from_values([values_file])
        step1 = DummyStep()
        step2 = DummyFollowStep()
        step1 >> step2

        yaml_output = backend.generate_artifact(step2)

        assert "integration-pipeline" in yaml_output
        assert "integration-ns" in yaml_output
        assert "0 6 * * *" in yaml_output
        assert "integration-image:v1" in yaml_output
        assert "integration-bucket" in yaml_output
        assert "WURZEL_RUN_ID" in yaml_output
        assert "{{workflow.uid}}" in yaml_output
        assert "TEST_VAR" in yaml_output
        assert "test_value" in yaml_output
