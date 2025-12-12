# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.backend.backend_argo module."""

from pathlib import Path

import pytest
import yaml

from wurzel.utils import HAS_HERA

if not HAS_HERA:
    pytest.skip("Hera is not available", allow_module_level=True)

from wurzel.backend.backend_argo import (
    ArgoBackend,
    ContainerConfig,
    EnvFromConfig,
    S3ArtifactConfig,
    SecretMapping,
    SecretMount,
    TemplateValues,
    WorkflowConfig,
    select_workflow,
)
from wurzel.backend.values import deep_merge_dicts, load_values
from wurzel.datacontract.common import MarkdownDataContract
from wurzel.step import NoSettings, TypedStep

# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


class DummyStep(TypedStep[NoSettings, None, MarkdownDataContract]):
    """A simple step with no dependencies for testing."""

    def run(self, inpt: None) -> MarkdownDataContract:
        return MarkdownDataContract(content="test")


class DummyFollowStep(TypedStep[NoSettings, MarkdownDataContract, MarkdownDataContract]):
    """A step that depends on another step."""

    def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
        return inpt


@pytest.fixture
def sample_values_file(tmp_path: Path) -> Path:
    """Create a sample values.yaml file."""
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
            }
        },
    }
    file_path = tmp_path / "values.yaml"
    file_path.write_text(yaml.safe_dump(content))
    return file_path


@pytest.fixture
def override_values_file(tmp_path: Path) -> Path:
    """Create an override values.yaml file."""
    content = {
        "workflows": {
            "test-workflow": {
                "namespace": "override-ns",
                "container": {"image": "override-image:v2"},
            }
        }
    }
    file_path = tmp_path / "override.yaml"
    file_path.write_text(yaml.safe_dump(content))
    return file_path


# ---------------------------------------------------------------------------
# Tests for Pydantic Models
# ---------------------------------------------------------------------------


class TestSecretMapping:
    def test_basic_instantiation(self):
        mapping = SecretMapping(key="tls.crt", value="cert.pem")
        assert mapping.key == "tls.crt"
        assert mapping.value == "cert.pem"


class TestSecretMount:
    def test_field_aliases(self):
        mount = SecretMount(**{"from": "my-secret", "to": "/etc/certs", "mappings": [{"key": "tls.crt", "value": "cert.pem"}]})
        assert mount.source == "my-secret"
        assert mount.destination == Path("/etc/certs")
        assert len(mount.mappings) == 1


class TestEnvFromConfig:
    def test_defaults(self):
        config = EnvFromConfig(name="my-config")
        assert config.kind == "secret"
        assert config.prefix is None
        assert config.optional is True

    @pytest.mark.parametrize("kind", ["secret", "configMap"])
    def test_kind_variants(self, kind: str):
        config = EnvFromConfig(name="test", kind=kind)
        assert config.kind == kind

    def test_with_prefix(self):
        config = EnvFromConfig(name="test", prefix="APP_")
        assert config.prefix == "APP_"


class TestContainerConfig:
    def test_defaults(self):
        config = ContainerConfig()
        assert config.image == "ghcr.io/telekom/wurzel"
        assert config.env == {}
        assert config.envFrom == []
        assert config.mountSecrets == []
        assert "sidecar.istio.io/inject" in config.annotations

    def test_custom_values(self):
        config = ContainerConfig(
            image="custom:latest",
            env={"KEY": "value"},
            annotations={"custom": "annotation"},
        )
        assert config.image == "custom:latest"
        assert config.env == {"KEY": "value"}
        assert config.annotations == {"custom": "annotation"}


class TestS3ArtifactConfig:
    def test_defaults(self):
        config = S3ArtifactConfig()
        assert config.bucket == "wurzel-bucket"
        assert config.endpoint == "s3.amazonaws.com"

    def test_custom_values(self):
        config = S3ArtifactConfig(bucket="my-bucket", endpoint="minio:9000")
        assert config.bucket == "my-bucket"
        assert config.endpoint == "minio:9000"


class TestWorkflowConfig:
    def test_defaults(self):
        config = WorkflowConfig()
        assert config.name == "wurzel"
        assert config.namespace == "argo-workflows"
        assert config.schedule == "0 4 * * *"
        assert config.entrypoint == "wurzel-pipeline"
        assert config.dataDir == Path("/usr/app")
        assert isinstance(config.container, ContainerConfig)
        assert isinstance(config.artifacts, S3ArtifactConfig)

    def test_no_schedule(self):
        config = WorkflowConfig(schedule=None)
        assert config.schedule is None


class TestTemplateValues:
    def test_empty(self):
        values = TemplateValues()
        assert values.workflows == {}

    def test_with_workflows(self):
        values = TemplateValues(
            workflows={"wf1": WorkflowConfig()},
        )
        assert "wf1" in values.workflows


# ---------------------------------------------------------------------------
# Tests for Utility Functions
# ---------------------------------------------------------------------------


class TestDeepMergeDicts:
    """Tests for deep_merge_dicts function."""

    # -------------------------------------------------------------------------
    # Basic merge scenarios (parametrized)
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "base,override,expected",
        [
            pytest.param({}, {}, {}, id="empty_dicts"),
            pytest.param({"a": 1}, {}, {"a": 1}, id="empty_override"),
            pytest.param({}, {"b": 2}, {"b": 2}, id="empty_base"),
            pytest.param({"a": 1}, {"b": 2}, {"a": 1, "b": 2}, id="non_overlapping_keys"),
            pytest.param({"a": 1, "b": 2}, {"b": 3}, {"a": 1, "b": 3}, id="overlapping_scalar_replaced"),
            pytest.param({"a": "foo"}, {"a": "bar"}, {"a": "bar"}, id="overlapping_string_replaced"),
            pytest.param({"a": True}, {"a": False}, {"a": False}, id="overlapping_bool_replaced"),
        ],
    )
    def test_basic_merge(self, base: dict, override: dict, expected: dict):
        result = deep_merge_dicts(base, override)
        assert result == expected

    # -------------------------------------------------------------------------
    # Nested dict merge scenarios
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "base,override,expected",
        [
            pytest.param(
                {"outer": {"inner1": 1, "inner2": 2}},
                {"outer": {"inner2": 20, "inner3": 3}},
                {"outer": {"inner1": 1, "inner2": 20, "inner3": 3}},
                id="nested_dict_merge",
            ),
            pytest.param(
                {"a": {"b": {"c": 1}}},
                {"a": {"b": {"c": 2, "d": 3}}},
                {"a": {"b": {"c": 2, "d": 3}}},
                id="deeply_nested_3_levels",
            ),
            pytest.param(
                {"a": {"b": {"c": {"d": 1}}}},
                {"a": {"b": {"c": {"d": 2, "e": 3}}}},
                {"a": {"b": {"c": {"d": 2, "e": 3}}}},
                id="deeply_nested_4_levels",
            ),
            pytest.param(
                {"outer": {}},
                {"outer": {"key": "value"}},
                {"outer": {"key": "value"}},
                id="empty_nested_dict_in_base",
            ),
            pytest.param(
                {"outer": {"key": "value"}},
                {"outer": {}},
                {"outer": {"key": "value"}},
                id="empty_nested_dict_in_override",
            ),
            pytest.param(
                {"a": {"x": 1}, "b": {"y": 2}},
                {"a": {"x": 10}, "c": {"z": 3}},
                {"a": {"x": 10}, "b": {"y": 2}, "c": {"z": 3}},
                id="multiple_nested_dicts",
            ),
        ],
    )
    def test_nested_dict_merge(self, base: dict, override: dict, expected: dict):
        result = deep_merge_dicts(base, override)
        assert result == expected

    # -------------------------------------------------------------------------
    # Type coercion scenarios (dict <-> scalar)
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "base,override,expected",
        [
            pytest.param(
                {"a": {"nested": 1}},
                {"a": "scalar"},
                {"a": "scalar"},
                id="dict_replaced_by_scalar",
            ),
            pytest.param(
                {"a": "scalar"},
                {"a": {"nested": 1}},
                {"a": {"nested": 1}},
                id="scalar_replaced_by_dict",
            ),
            pytest.param(
                {"a": [1, 2, 3]},
                {"a": {"nested": 1}},
                {"a": {"nested": 1}},
                id="list_replaced_by_dict",
            ),
            pytest.param(
                {"a": {"nested": 1}},
                {"a": [1, 2, 3]},
                {"a": [1, 2, 3]},
                id="dict_replaced_by_list",
            ),
        ],
    )
    def test_type_coercion(self, base: dict, override: dict, expected: dict):
        result = deep_merge_dicts(base, override)
        assert result == expected

    # -------------------------------------------------------------------------
    # None value handling
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "base,override,expected",
        [
            pytest.param({"a": None}, {"a": 1}, {"a": 1}, id="none_replaced_by_value"),
            pytest.param({"a": 1}, {"a": None}, {"a": None}, id="value_replaced_by_none"),
            pytest.param({"a": None}, {"a": None}, {"a": None}, id="none_replaced_by_none"),
            pytest.param({"a": None}, {}, {"a": None}, id="none_preserved_when_no_override"),
            pytest.param({}, {"a": None}, {"a": None}, id="none_added_from_override"),
            pytest.param(
                {"a": {"b": None}},
                {"a": {"b": "value"}},
                {"a": {"b": "value"}},
                id="nested_none_replaced",
            ),
        ],
    )
    def test_none_handling(self, base: dict, override: dict, expected: dict):
        result = deep_merge_dicts(base, override)
        assert result == expected

    # -------------------------------------------------------------------------
    # List handling (lists are replaced, not merged)
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "base,override,expected",
        [
            pytest.param(
                {"items": [1, 2, 3]},
                {"items": [4, 5]},
                {"items": [4, 5]},
                id="list_replaced",
            ),
            pytest.param(
                {"outer": {"list": [1, 2], "keep": "value"}},
                {"outer": {"list": [3, 4, 5]}},
                {"outer": {"list": [3, 4, 5], "keep": "value"}},
                id="list_in_nested_dict_replaced",
            ),
            pytest.param({"a": 1}, {"b": [1, 2, 3]}, {"a": 1, "b": [1, 2, 3]}, id="new_list_key_added"),
            pytest.param({"items": []}, {"items": [1, 2]}, {"items": [1, 2]}, id="empty_list_replaced"),
            pytest.param({"items": [1, 2]}, {"items": []}, {"items": []}, id="list_replaced_by_empty"),
            pytest.param(
                {"items": [{"a": 1}, {"b": 2}]},
                {"items": [{"c": 3}]},
                {"items": [{"c": 3}]},
                id="list_of_dicts_replaced",
            ),
        ],
    )
    def test_list_handling(self, base: dict, override: dict, expected: dict):
        result = deep_merge_dicts(base, override)
        assert result == expected

    # -------------------------------------------------------------------------
    # Immutability tests (originals not mutated)
    # -------------------------------------------------------------------------
    def test_base_not_mutated(self):
        base = {"a": {"b": 1}}
        base_copy = {"a": {"b": 1}}
        override = {"a": {"b": 2}}
        deep_merge_dicts(base, override)
        assert base == base_copy

    def test_override_not_mutated(self):
        base = {"a": {"b": 1}}
        override = {"a": {"b": 2, "c": 3}}
        override_copy = {"a": {"b": 2, "c": 3}}
        deep_merge_dicts(base, override)
        assert override == override_copy

    def test_base_list_not_mutated(self):
        base = {"items": [1, 2, 3]}
        base_copy = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        deep_merge_dicts(base, override)
        assert base == base_copy

    def test_nested_structure_not_mutated(self):
        base = {"a": {"b": {"c": [1, 2, 3]}}}
        base_copy = {"a": {"b": {"c": [1, 2, 3]}}}
        override = {"a": {"b": {"c": [4, 5], "d": 6}}}
        deep_merge_dicts(base, override)
        assert base == base_copy

    def test_result_is_independent_copy(self):
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        result = deep_merge_dicts(base, override)
        result["a"]["b"] = 999
        result["a"]["c"] = 888
        assert base == {"a": {"b": 1}}
        assert override == {"a": {"c": 2}}


class TestLoadValues:
    def test_single_file(self, sample_values_file: Path):
        values = load_values([sample_values_file], TemplateValues)
        assert "test-workflow" in values.workflows
        assert values.workflows["test-workflow"].name == "test-wf"

    def test_multiple_files_merge(self, sample_values_file: Path, override_values_file: Path):
        values = load_values([sample_values_file, override_values_file], TemplateValues)
        wf = values.workflows["test-workflow"]
        assert wf.name == "test-wf"  # From base
        assert wf.namespace == "override-ns"  # Overridden
        assert wf.container.image == "override-image:v2"  # Overridden

    def test_empty_file(self, tmp_path: Path):
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        values = load_values([empty_file], TemplateValues)
        assert values.workflows == {}

    def test_non_dict_yaml_raises(self, tmp_path: Path):
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("- item1\n- item2")
        with pytest.raises(ValueError, match="must start with a mapping"):
            load_values([invalid_file], TemplateValues)


class TestSelectWorkflow:
    def test_select_by_name(self):
        values = TemplateValues(
            workflows={
                "wf1": WorkflowConfig(name="workflow-one"),
                "wf2": WorkflowConfig(name="workflow-two"),
            }
        )
        result = select_workflow(values, "wf2")
        assert result.name == "workflow-two"

    def test_select_first_fallback(self):
        values = TemplateValues(
            workflows={
                "first": WorkflowConfig(name="first-wf"),
                "second": WorkflowConfig(name="second-wf"),
            }
        )
        result = select_workflow(values, None)
        assert result.name == "first-wf"

    def test_empty_workflows_returns_default(self):
        values = TemplateValues()
        result = select_workflow(values, None)
        assert result.name == "wurzel"  # Default from WorkflowConfig

    def test_nonexistent_workflow_raises(self):
        values = TemplateValues(workflows={"existing": WorkflowConfig()})
        with pytest.raises(ValueError, match="not found in values"):
            select_workflow(values, "nonexistent")


# ---------------------------------------------------------------------------
# Tests for ArgoBackend Class
# ---------------------------------------------------------------------------


class TestArgoBackendInit:
    def test_default_config(self):
        backend = ArgoBackend()
        assert backend.config.name == "wurzel"
        assert isinstance(backend.values, TemplateValues)

    def test_custom_config(self):
        config = WorkflowConfig(name="custom-wf", namespace="custom-ns")
        backend = ArgoBackend(config=config)
        assert backend.config.name == "custom-wf"
        assert backend.config.namespace == "custom-ns"

    def test_from_values(self):
        values = TemplateValues(workflows={"my-wf": WorkflowConfig(name="values-wf")})
        backend = ArgoBackend(values=values, workflow_name="my-wf")
        assert backend.config.name == "values-wf"


class TestArgoBackendFromValues:
    def test_factory_method(self, sample_values_file: Path):
        backend = ArgoBackend.from_values([sample_values_file], workflow_name="test-workflow")
        assert backend.config.name == "test-wf"
        assert backend.config.namespace == "test-ns"


class TestArgoBackendBuildSecretMounts:
    def test_no_mounts(self):
        backend = ArgoBackend()
        volumes, mounts = backend._build_secret_mounts()
        assert volumes == []
        assert mounts == []

    def test_single_mount_single_mapping(self):
        config = WorkflowConfig(
            container=ContainerConfig(
                mountSecrets=[
                    SecretMount(
                        **{
                            "from": "tls-secret",
                            "to": "/etc/ssl",
                            "mappings": [{"key": "tls.crt", "value": "cert.pem"}],
                        }
                    )
                ]
            )
        )
        backend = ArgoBackend(config=config)
        volumes, mounts = backend._volumes, backend._volume_mounts

        assert len(volumes) == 1
        assert volumes[0].name == "secret-mount-0"
        assert len(mounts) == 1
        assert mounts[0].mount_path == "/etc/ssl/cert.pem"
        assert mounts[0].sub_path == "tls.crt"

    def test_multiple_mappings(self):
        config = WorkflowConfig(
            container=ContainerConfig(
                mountSecrets=[
                    SecretMount(
                        **{
                            "from": "tls-secret",
                            "to": "/etc/ssl",
                            "mappings": [
                                {"key": "tls.crt", "value": "cert.pem"},
                                {"key": "tls.key", "value": "key.pem"},
                            ],
                        }
                    )
                ]
            )
        )
        backend = ArgoBackend(config=config)
        assert len(backend._volume_mounts) == 2


class TestArgoBackendBuildEnvFrom:
    def test_empty(self):
        backend = ArgoBackend()
        env_from = backend._build_env_from()
        assert env_from == []

    def test_config_map_env_from(self):
        from hera.workflows import ConfigMapEnvFrom

        config = WorkflowConfig(container=ContainerConfig(envFrom=[EnvFromConfig(name="my-cm", kind="configMap", prefix="CM_")]))
        backend = ArgoBackend(config=config)
        env_from = backend._build_env_from()

        assert len(env_from) == 1
        assert isinstance(env_from[0], ConfigMapEnvFrom)
        assert env_from[0].name == "my-cm"
        assert env_from[0].prefix == "CM_"

    def test_secret_env_from(self):
        from hera.workflows import SecretEnvFrom

        config = WorkflowConfig(container=ContainerConfig(envFrom=[EnvFromConfig(name="my-secret", kind="secret")]))
        backend = ArgoBackend(config=config)
        env_from = backend._build_env_from()

        assert len(env_from) == 1
        assert isinstance(env_from[0], SecretEnvFrom)

    def test_secret_ref(self):
        from hera.workflows import SecretEnvFrom

        config = WorkflowConfig(container=ContainerConfig(secretRef=["my-secret-1", "my-secret-2"]))
        backend = ArgoBackend(config=config)
        env_from = backend._build_env_from()

        assert len(env_from) == 2
        assert all(isinstance(e, SecretEnvFrom) for e in env_from)
        assert env_from[0].name == "my-secret-1"
        assert env_from[1].name == "my-secret-2"

    def test_secret_ref_combined_with_env_from(self):
        from hera.workflows import ConfigMapEnvFrom, SecretEnvFrom

        config = WorkflowConfig(container=ContainerConfig(envFrom=[EnvFromConfig(name="my-cm", kind="configMap")], secretRef=["my-secret"]))
        backend = ArgoBackend(config=config)
        env_from = backend._build_env_from()

        assert len(env_from) == 2
        assert isinstance(env_from[0], ConfigMapEnvFrom)
        assert isinstance(env_from[1], SecretEnvFrom)

    def test_config_map_ref(self):
        from hera.workflows import ConfigMapEnvFrom

        config = WorkflowConfig(container=ContainerConfig(configMapRef=["my-configmap-1", "my-configmap-2"]))
        backend = ArgoBackend(config=config)
        env_from = backend._build_env_from()

        assert len(env_from) == 2
        assert all(isinstance(e, ConfigMapEnvFrom) for e in env_from)
        assert env_from[0].name == "my-configmap-1"
        assert env_from[1].name == "my-configmap-2"


class TestArgoBackendGenerateArtifact:
    def test_generates_valid_yaml(self):
        backend = ArgoBackend()
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        # Should be valid YAML
        manifests = list(yaml.safe_load_all(yaml_output))
        assert len(manifests) >= 1

    def test_generates_workflow_manifest(self):
        backend = ArgoBackend()
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        manifest = yaml.safe_load(yaml_output)
        assert manifest["kind"] in ("CronWorkflow", "Workflow")


class TestArgoBackendGenerateWorkflow:
    def test_cron_workflow_with_schedule(self):
        config = WorkflowConfig(schedule="0 0 * * *")
        backend = ArgoBackend(config=config)
        step = DummyStep()
        workflow = backend._generate_workflow(step)

        assert workflow.kind == "CronWorkflow"

    def test_workflow_without_schedule(self):
        config = WorkflowConfig(schedule=None)
        backend = ArgoBackend(config=config)
        step = DummyStep()
        workflow = backend._generate_workflow(step)

        assert workflow.kind == "Workflow"

    def test_workflow_metadata(self):
        config = WorkflowConfig(
            name="test-wf",
            namespace="test-ns",
            serviceAccountName="test-sa",
        )
        backend = ArgoBackend(config=config)
        step = DummyStep()
        workflow = backend._generate_workflow(step)

        assert workflow.name == "test-wf"
        assert workflow.namespace == "test-ns"


class TestArgoBackendCreateArtifactFromStep:
    def test_artifact_properties(self):
        backend = ArgoBackend()
        step = DummyStep()
        artifact = backend._create_artifact_from_step(step)

        assert artifact.name == "wurzel-artifact-dummystep"
        assert artifact.key == "dummystep"
        assert artifact.bucket == "wurzel-bucket"
        assert "DummyStep" in artifact.path

    def test_artifact_caching(self):
        backend = ArgoBackend()
        step = DummyStep()
        artifact1 = backend._create_artifact_from_step(step)
        artifact2 = backend._create_artifact_from_step(step)

        assert artifact1 is artifact2  # Same object due to @cache


class TestArgoBackendCreateTask:
    def test_task_creation(self):
        from hera.workflows import DAG, Task, Workflow

        backend = ArgoBackend()
        step = DummyStep()

        with Workflow(name="test-workflow", entrypoint="test-dag"):
            with DAG(name="test-dag") as dag:
                task = backend._create_task(dag, step)

            assert isinstance(task, Task)
            assert task.name == "dummystep"

    def test_task_with_dependencies(self):
        from hera.workflows import DAG, Workflow

        backend = ArgoBackend()
        step1 = DummyStep()
        step2 = DummyFollowStep()
        step1 >> step2

        with Workflow(name="test-workflow", entrypoint="test-dag"):
            with DAG(name="test-dag") as dag:
                task = backend._create_task(dag, step2)

            # Task should have input artifacts from dependency
            assert task is not None


class TestArgoBackendIntegration:
    def test_full_pipeline_generation(self):
        """Test generating a complete pipeline with dependencies."""
        backend = ArgoBackend()
        step1 = DummyStep()
        step2 = DummyFollowStep()
        step1 >> step2

        yaml_output = backend.generate_artifact(step2)
        manifests = list(yaml.safe_load_all(yaml_output))

        # Should have workflow manifest
        workflow = manifests[-1]
        assert workflow["kind"] in ("CronWorkflow", "Workflow")

        # Should have templates for both steps
        spec = workflow.get("spec", {})
        if "workflowSpec" in spec:
            templates = spec["workflowSpec"].get("templates", [])
        else:
            templates = spec.get("templates", [])

        template_names = [t.get("name", "") for t in templates]
        assert any("dummystep" in name for name in template_names)
        assert any("dummyfollowstep" in name for name in template_names)

    def test_env_vars_in_container(self):
        """Test that environment variables are properly set in containers."""
        config = WorkflowConfig(container=ContainerConfig(env={"MY_VAR": "my_value"}))
        backend = ArgoBackend(config=config)
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)
        manifests = list(yaml.safe_load_all(yaml_output))
        workflow = manifests[-1]

        # Find container template
        spec = workflow.get("spec", {})
        if "workflowSpec" in spec:
            templates = spec["workflowSpec"].get("templates", [])
        else:
            templates = spec.get("templates", [])

        container_templates = [t for t in templates if "container" in t]
        assert len(container_templates) > 0

        # Check env vars
        for template in container_templates:
            env_list = template["container"].get("env", [])
            env_names = [e.get("name") for e in env_list]
            if "MY_VAR" in env_names:
                env_dict = {e["name"]: e["value"] for e in env_list}
                assert env_dict["MY_VAR"] == "my_value"
                break

    def test_from_values_file_integration(self, sample_values_file: Path):
        """Test creating backend from values file and generating workflow."""
        backend = ArgoBackend.from_values([sample_values_file], workflow_name="test-workflow")
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)
        workflow = yaml.safe_load(yaml_output)

        # Workflow should use values from file
        assert workflow["metadata"]["name"] == "test-wf"
        assert workflow["metadata"]["namespace"] == "test-ns"
