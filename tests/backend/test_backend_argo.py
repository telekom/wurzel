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
    ResourcesConfig,
    S3ArtifactConfig,
    SecretMapping,
    SecretMount,
    SecurityContextConfig,
    TemplateValues,
    TokenizerCacheConfig,
    WorkflowConfig,
    select_workflow,
)
from wurzel.backend.values import ValuesFileError, deep_merge_dicts, load_values
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


class TestSecurityContextConfig:
    def test_defaults(self):
        config = SecurityContextConfig()
        assert config.runAsNonRoot is True
        assert config.runAsUser is None
        assert config.runAsGroup is None
        assert config.fsGroup is None
        assert config.allowPrivilegeEscalation is False
        assert config.readOnlyRootFilesystem is None
        assert config.dropCapabilities == ["ALL"]
        assert config.seccompProfileType == "RuntimeDefault"
        assert config.seccompLocalhostProfile is None

    def test_custom_values(self):
        config = SecurityContextConfig(
            runAsNonRoot=True,
            runAsUser=1000,
            runAsGroup=1000,
            fsGroup=2000,
            allowPrivilegeEscalation=False,
            readOnlyRootFilesystem=True,
            dropCapabilities=["ALL"],
            seccompProfileType="RuntimeDefault",
        )
        assert config.runAsUser == 1000
        assert config.runAsGroup == 1000
        assert config.fsGroup == 2000
        assert config.readOnlyRootFilesystem is True


class TestResourcesConfig:
    def test_defaults(self):
        config = ResourcesConfig()
        assert config.cpu_request == "100m"
        assert config.cpu_limit == "500m"
        assert config.memory_request == "128Mi"
        assert config.memory_limit == "512Mi"

    def test_custom_values(self):
        config = ResourcesConfig(
            cpu_request="200m",
            cpu_limit="1",
            memory_request="256Mi",
            memory_limit="1Gi",
        )
        assert config.cpu_request == "200m"
        assert config.cpu_limit == "1"
        assert config.memory_request == "256Mi"
        assert config.memory_limit == "1Gi"


class TestContainerConfig:
    def test_defaults(self):
        config = ContainerConfig()
        assert config.image == "ghcr.io/telekom/wurzel"
        assert config.env == {}
        assert config.envFrom == []
        assert config.mountSecrets == []
        assert config.annotations == {}
        assert isinstance(config.securityContext, SecurityContextConfig)
        assert config.securityContext.runAsNonRoot is True
        assert isinstance(config.resources, ResourcesConfig)

    def test_custom_values(self):
        config = ContainerConfig(
            image="custom:latest",
            env={"KEY": "value"},
            annotations={"custom": "annotation"},
        )
        assert config.image == "custom:latest"
        assert config.env == {"KEY": "value"}
        assert config.annotations == {"custom": "annotation"}

    def test_custom_security_context(self):
        config = ContainerConfig(
            securityContext=SecurityContextConfig(runAsUser=1000, runAsNonRoot=True),
        )
        assert config.securityContext.runAsUser == 1000
        assert config.securityContext.runAsNonRoot is True


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
        assert isinstance(config.podSecurityContext, SecurityContextConfig)
        assert config.podSecurityContext.runAsNonRoot is True

    def test_no_schedule(self):
        config = WorkflowConfig(schedule=None)
        assert config.schedule is None

    def test_custom_pod_security_context(self):
        config = WorkflowConfig(
            podSecurityContext=SecurityContextConfig(runAsUser=1000, fsGroup=2000),
        )
        assert config.podSecurityContext.runAsUser == 1000
        assert config.podSecurityContext.fsGroup == 2000


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
        with pytest.raises(ValuesFileError, match="must start with a mapping"):
            load_values([invalid_file], TemplateValues)

    def test_malformed_yaml_raises(self, tmp_path: Path):
        malformed_file = tmp_path / "malformed.yaml"
        malformed_file.write_text("key: value\n  bad_indent: oops")
        with pytest.raises(ValuesFileError, match="Failed to parse YAML"):
            load_values([malformed_file], TemplateValues)


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


class TestArgoBackendBuildVolumes:
    def test_no_mounts(self):
        backend = ArgoBackend()
        volumes, mounts = backend._build_volumes()
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

    def test_tokenizer_cache_disabled_by_default(self):
        backend = ArgoBackend()
        volumes, mounts = backend._build_volumes()
        # No tokenizer cache volume when disabled
        assert not any(getattr(v, "claim_name", None) == "tokenizer-cache-pvc" for v in volumes)

    def test_tokenizer_cache_enabled(self):
        config = WorkflowConfig(
            container=ContainerConfig(
                tokenizerCache=TokenizerCacheConfig(
                    enabled=True,
                    claimName="my-tokenizer-pvc",
                    mountPath="/cache/hf",
                    readOnly=True,
                )
            )
        )
        backend = ArgoBackend(config=config)
        volumes, mounts = backend._build_volumes()

        # Should have one volume for tokenizer cache
        assert len(volumes) == 1
        assert volumes[0].claim_name == "my-tokenizer-pvc"
        assert volumes[0].name == "tokenizer-cache"

        # Should have one mount
        assert len(mounts) == 1
        assert mounts[0].mount_path == "/cache/hf"
        assert mounts[0].read_only is True

    def test_tokenizer_cache_with_secret_mounts(self):
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
                ],
                tokenizerCache=TokenizerCacheConfig(enabled=True),
            )
        )
        backend = ArgoBackend(config=config)
        volumes, mounts = backend._build_volumes()

        # Should have 2 volumes: secret + tokenizer cache
        assert len(volumes) == 2
        # Should have 2 mounts: secret mapping + tokenizer cache
        assert len(mounts) == 2


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
    """Tests for _generate_workflow method covering both CronWorkflow and normal Workflow creation."""

    @pytest.mark.parametrize(
        "schedule,expected_kind,test_id",
        [
            pytest.param("0 0 * * *", "CronWorkflow", "daily_midnight_cron"),
            pytest.param("0 4 * * *", "CronWorkflow", "daily_4am_cron"),
            pytest.param("*/15 * * * *", "CronWorkflow", "every_15min_cron"),
            pytest.param("0 0 1 * *", "CronWorkflow", "monthly_cron"),
            pytest.param(None, "Workflow", "no_schedule_normal_workflow"),
        ],
    )
    def test_workflow_kind_based_on_schedule(self, schedule, expected_kind, test_id):
        """Test that correct workflow type is created based on schedule configuration.

        When schedule is set, creates a CronWorkflow.
        When schedule is None, creates a normal Workflow.
        """
        config = WorkflowConfig(schedule=schedule)
        backend = ArgoBackend(config=config)
        step = DummyStep()
        workflow = backend._generate_workflow(step)

        assert workflow.kind == expected_kind, f"Failed for test case: {test_id}"

    @pytest.mark.parametrize(
        "workflow_name,namespace,service_account",
        [
            pytest.param("test-wf", "test-ns", "test-sa", id="basic_metadata"),
            pytest.param("my-pipeline", "production", "prod-sa", id="production_metadata"),
            pytest.param("dev-workflow", "development", "dev-service-account", id="dev_metadata"),
        ],
    )
    def test_workflow_metadata(self, workflow_name, namespace, service_account):
        """Test that workflow metadata is correctly applied from configuration."""
        config = WorkflowConfig(
            name=workflow_name,
            namespace=namespace,
            serviceAccountName=service_account,
        )
        backend = ArgoBackend(config=config)
        step = DummyStep()
        workflow = backend._generate_workflow(step)

        assert workflow.name == workflow_name
        assert workflow.namespace == namespace

    def test_workflow_without_schedule_is_not_cron(self):
        """Explicit test that schedule=None creates a normal Workflow, not CronWorkflow.

        This is important for manual workflows or workflows triggered by other workflows.
        """
        config = WorkflowConfig(schedule=None)
        backend = ArgoBackend(config=config)
        step = DummyStep()
        workflow = backend._generate_workflow(step)

        assert workflow.kind == "Workflow"
        assert workflow.kind != "CronWorkflow"

    def test_workflow_with_schedule_is_cron(self):
        """Explicit test that schedule parameter creates a CronWorkflow."""
        config = WorkflowConfig(schedule="0 0 * * *")
        backend = ArgoBackend(config=config)
        step = DummyStep()
        workflow = backend._generate_workflow(step)

        assert workflow.kind == "CronWorkflow"
        assert workflow.kind != "Workflow"

    def test_workflow_contains_dag(self):
        """Test that generated workflow contains the expected DAG."""
        backend = ArgoBackend()
        step = DummyStep()
        workflow = backend._generate_workflow(step)

        # Workflow should be properly initialized
        assert workflow is not None
        assert hasattr(workflow, "entrypoint")

    @pytest.mark.parametrize(
        "schedule",
        [
            pytest.param(None, id="normal_workflow"),
            pytest.param("0 0 * * *", id="cron_workflow"),
        ],
    )
    def test_workflow_yaml_generation(self, schedule):
        """Test that both workflow types can be converted to valid YAML."""
        config = WorkflowConfig(schedule=schedule)
        backend = ArgoBackend(config=config)
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)
        workflow_dict = yaml.safe_load(yaml_output)

        assert "kind" in workflow_dict
        assert "metadata" in workflow_dict
        assert "spec" in workflow_dict

        if schedule:
            assert workflow_dict["kind"] == "CronWorkflow"
            assert "schedule" in workflow_dict["spec"]
        else:
            assert workflow_dict["kind"] == "Workflow"
            assert "schedule" not in workflow_dict["spec"]


class TestArgoBackendCreateArtifactFromStep:
    def test_artifact_properties(self):
        backend = ArgoBackend()
        step = DummyStep()
        artifact = backend._create_artifact_from_step(step)

        assert artifact.name == "wurzel-artifact-dummystep"
        # Key includes workflow.name template for unique paths per run
        assert artifact.key == "argo-workflows/{{workflow.name}}/dummystep"
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


class TestArgoBackendTokenizerCache:
    def test_hf_home_env_var_set_when_enabled(self):
        """Test that HF_HOME env var is set when tokenizer cache is enabled."""
        config = WorkflowConfig(
            container=ContainerConfig(
                tokenizerCache=TokenizerCacheConfig(
                    enabled=True,
                    mountPath="/cache/huggingface",
                )
            )
        )
        backend = ArgoBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)
        workflow = yaml.safe_load(yaml_output)

        spec = workflow.get("spec", {})
        if "workflowSpec" in spec:
            templates = spec["workflowSpec"].get("templates", [])
        else:
            templates = spec.get("templates", [])

        container_templates = [t for t in templates if "container" in t]
        assert len(container_templates) > 0

        for template in container_templates:
            env_vars = template["container"].get("env", [])
            hf_home_vars = [e for e in env_vars if e.get("name") == "HF_HOME"]
            assert len(hf_home_vars) == 1
            assert hf_home_vars[0]["value"] == "/cache/huggingface"

    def test_hf_home_env_var_not_set_when_disabled(self):
        """Test that HF_HOME env var is not set when tokenizer cache is disabled."""
        backend = ArgoBackend()
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)
        workflow = yaml.safe_load(yaml_output)

        spec = workflow.get("spec", {})
        if "workflowSpec" in spec:
            templates = spec["workflowSpec"].get("templates", [])
        else:
            templates = spec.get("templates", [])

        container_templates = [t for t in templates if "container" in t]
        for template in container_templates:
            env_vars = template["container"].get("env", [])
            hf_home_vars = [e for e in env_vars if e.get("name") == "HF_HOME"]
            assert len(hf_home_vars) == 0

    def test_tokenizer_cache_volume_in_workflow(self):
        """Test that tokenizer cache volume is included in workflow manifest."""
        config = WorkflowConfig(
            container=ContainerConfig(
                tokenizerCache=TokenizerCacheConfig(
                    enabled=True,
                    claimName="my-tokenizer-pvc",
                    mountPath="/cache/hf",
                )
            )
        )
        backend = ArgoBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)
        workflow = yaml.safe_load(yaml_output)

        spec = workflow.get("spec", {})
        if "workflowSpec" in spec:
            volumes = spec["workflowSpec"].get("volumes", [])
        else:
            volumes = spec.get("volumes", [])

        # Should have tokenizer cache volume
        tokenizer_volumes = [v for v in volumes if v.get("name") == "tokenizer-cache"]
        assert len(tokenizer_volumes) == 1
        assert tokenizer_volumes[0]["persistentVolumeClaim"]["claimName"] == "my-tokenizer-pvc"

    def test_create_pvc_uses_volume_claim_templates(self):
        """Test that createPvc uses volumeClaimTemplates in workflow spec."""
        config = WorkflowConfig(
            container=ContainerConfig(
                tokenizerCache=TokenizerCacheConfig(
                    enabled=True,
                    createPvc=True,
                    storageSize="20Gi",
                    storageClassName="fast-storage",
                    accessModes=["ReadWriteMany"],
                )
            ),
        )
        backend = ArgoBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)
        workflow = yaml.safe_load(yaml_output)

        # Should have volumeClaimTemplates in workflow spec
        spec = workflow.get("spec", {})
        if "workflowSpec" in spec:
            volume_claim_templates = spec["workflowSpec"].get("volumeClaimTemplates", [])
        else:
            volume_claim_templates = spec.get("volumeClaimTemplates", [])

        assert len(volume_claim_templates) == 1
        vct = volume_claim_templates[0]
        assert vct["metadata"]["name"] == "tokenizer-cache"
        assert vct["spec"]["accessModes"] == ["ReadWriteMany"]
        assert vct["spec"]["resources"]["requests"]["storage"] == "20Gi"
        assert vct["spec"]["storageClassName"] == "fast-storage"

    def test_create_pvc_without_storage_class(self):
        """Test that createPvc works without storageClassName."""
        config = WorkflowConfig(
            container=ContainerConfig(
                tokenizerCache=TokenizerCacheConfig(
                    enabled=True,
                    createPvc=True,
                )
            ),
        )
        backend = ArgoBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)
        workflow = yaml.safe_load(yaml_output)

        spec = workflow.get("spec", {})
        if "workflowSpec" in spec:
            volume_claim_templates = spec["workflowSpec"].get("volumeClaimTemplates", [])
        else:
            volume_claim_templates = spec.get("volumeClaimTemplates", [])

        assert len(volume_claim_templates) == 1
        vct = volume_claim_templates[0]
        assert "storageClassName" not in vct["spec"] or vct["spec"]["storageClassName"] is None
        assert vct["spec"]["resources"]["requests"]["storage"] == "10Gi"  # default

    def test_no_volume_claim_templates_when_create_pvc_disabled(self):
        """Test that no volumeClaimTemplates when createPvc is False (uses existing PVC)."""
        config = WorkflowConfig(
            container=ContainerConfig(
                tokenizerCache=TokenizerCacheConfig(
                    enabled=True,
                    createPvc=False,
                    claimName="existing-pvc",
                )
            ),
        )
        backend = ArgoBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)
        workflow = yaml.safe_load(yaml_output)

        spec = workflow.get("spec", {})
        if "workflowSpec" in spec:
            volume_claim_templates = spec["workflowSpec"].get("volumeClaimTemplates", [])
            volumes = spec["workflowSpec"].get("volumes", [])
        else:
            volume_claim_templates = spec.get("volumeClaimTemplates", [])
            volumes = spec.get("volumes", [])

        # Should have no volumeClaimTemplates
        assert len(volume_claim_templates) == 0

        # Should have existing volume reference
        tokenizer_volumes = [v for v in volumes if v.get("name") == "tokenizer-cache"]
        assert len(tokenizer_volumes) == 1
        assert tokenizer_volumes[0]["persistentVolumeClaim"]["claimName"] == "existing-pvc"


class TestArgoBackendSecurityContext:
    def test_default_security_context_in_workflow(self):
        """Test that default security context is applied to workflow."""
        backend = ArgoBackend()
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)
        workflow = yaml.safe_load(yaml_output)

        # Check pod-level security context
        spec = workflow.get("spec", {})
        if "workflowSpec" in spec:
            security_context = spec["workflowSpec"].get("securityContext", {})
        else:
            security_context = spec.get("securityContext", {})

        assert security_context.get("runAsNonRoot") is True
        assert security_context.get("seccompProfile", {}).get("type") == "RuntimeDefault"

    def test_custom_security_context_in_workflow(self):
        """Test that custom security context is applied to workflow."""
        config = WorkflowConfig(
            podSecurityContext=SecurityContextConfig(
                runAsNonRoot=True,
                runAsUser=1000,
                runAsGroup=1000,
                fsGroup=2000,
            ),
        )
        backend = ArgoBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)
        workflow = yaml.safe_load(yaml_output)

        spec = workflow.get("spec", {})
        if "workflowSpec" in spec:
            security_context = spec["workflowSpec"].get("securityContext", {})
        else:
            security_context = spec.get("securityContext", {})

        assert security_context.get("runAsNonRoot") is True
        assert security_context.get("runAsUser") == 1000
        assert security_context.get("runAsGroup") == 1000
        assert security_context.get("fsGroup") == 2000

    def test_container_security_context(self):
        """Test that container-level security context is applied."""
        config = WorkflowConfig(
            container=ContainerConfig(
                securityContext=SecurityContextConfig(
                    runAsNonRoot=True,
                    runAsUser=1000,
                    allowPrivilegeEscalation=False,
                ),
            ),
        )
        backend = ArgoBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)
        workflow = yaml.safe_load(yaml_output)

        spec = workflow.get("spec", {})
        if "workflowSpec" in spec:
            templates = spec["workflowSpec"].get("templates", [])
        else:
            templates = spec.get("templates", [])

        container_templates = [t for t in templates if "container" in t]
        assert len(container_templates) > 0

        for template in container_templates:
            sec_ctx = template["container"].get("securityContext", {})
            assert sec_ctx.get("runAsNonRoot") is True
            assert sec_ctx.get("runAsUser") == 1000
            assert sec_ctx.get("allowPrivilegeEscalation") is False
            assert sec_ctx.get("capabilities", {}).get("drop") == ["ALL"]
            assert sec_ctx.get("seccompProfile", {}).get("type") == "RuntimeDefault"

            resources = template["container"].get("resources", {})
            assert resources.get("requests", {}).get("cpu")
            assert resources.get("requests", {}).get("memory")
            assert resources.get("limits", {}).get("cpu")
            assert resources.get("limits", {}).get("memory")

    def test_security_context_from_values_file(self, tmp_path: Path):
        """Test that security context can be configured via values file."""
        content = {
            "workflows": {
                "secure-workflow": {
                    "name": "secure-wf",
                    "podSecurityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 1000,
                        "fsGroup": 2000,
                    },
                    "container": {
                        "securityContext": {
                            "runAsNonRoot": True,
                            "runAsUser": 1000,
                            "allowPrivilegeEscalation": False,
                        },
                    },
                }
            },
        }
        file_path = tmp_path / "security-values.yaml"
        file_path.write_text(yaml.safe_dump(content))

        backend = ArgoBackend.from_values([file_path], workflow_name="secure-workflow")
        assert backend.config.podSecurityContext.runAsUser == 1000
        assert backend.config.podSecurityContext.fsGroup == 2000
        assert backend.config.container.securityContext.allowPrivilegeEscalation is False


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


class TestArgoBackendPodSpecPatch:
    """Tests for podSpecPatch generation."""

    def test_no_pod_spec_patch_by_default(self):
        """Test that no podSpecPatch is generated by default.

        We don't generate podSpecPatch anymore to avoid conflicts with Argo's
        built-in init containers (init, wait). The pod-level security context
        is sufficient for most use cases.
        """
        config = WorkflowConfig(
            container=ContainerConfig(
                securityContext=SecurityContextConfig(
                    runAsNonRoot=True,
                    runAsUser=1000,
                ),
            ),
        )
        backend = ArgoBackend(config=config)
        pod_spec_patch = backend._build_pod_spec_patch()

        assert pod_spec_patch is None

    def test_custom_pod_spec_patch_is_used(self):
        """Test that custom podSpecPatch in config is used when provided."""
        custom_patch = """
initContainers:
  - name: custom-init
    securityContext:
      runAsUser: 1234
"""
        config = WorkflowConfig(podSpecPatch=custom_patch)
        backend = ArgoBackend(config=config)
        pod_spec_patch = backend._build_pod_spec_patch()

        assert pod_spec_patch == custom_patch


class TestArgoBackendS3Artifact:
    """Tests for S3Artifact configuration."""

    def test_artifact_has_no_mode_by_default(self):
        """Test that S3Artifact does not set mode parameter by default."""
        backend = ArgoBackend()
        step = DummyStep()
        artifact = backend._create_artifact_from_step(step)

        # The artifact should not have a mode set by default
        assert artifact.mode is None

    def test_artifact_uses_default_mode_from_config(self):
        """Test that S3Artifact uses defaultMode from config when provided."""
        config = WorkflowConfig(
            artifacts=S3ArtifactConfig(
                bucket="test-bucket",
                endpoint="s3.amazonaws.com",
                defaultMode=509,  # 0o775 in decimal
            ),
        )
        backend = ArgoBackend(config=config)
        step = DummyStep()
        artifact = backend._create_artifact_from_step(step)

        assert artifact.mode == 509

    def test_artifact_has_recurse_mode(self):
        """Test that S3Artifact has recurse_mode enabled for directory artifacts."""
        backend = ArgoBackend()
        step = DummyStep()
        artifact = backend._create_artifact_from_step(step)

        assert artifact.recurse_mode is True

    def test_artifact_uses_config_bucket_and_endpoint(self):
        """Test that S3Artifact uses bucket and endpoint from config."""
        config = WorkflowConfig(
            artifacts=S3ArtifactConfig(
                bucket="custom-bucket",
                endpoint="minio.local:9000",
            ),
        )
        backend = ArgoBackend(config=config)
        step = DummyStep()
        artifact = backend._create_artifact_from_step(step)

        assert artifact.bucket == "custom-bucket"
        assert artifact.endpoint == "minio.local:9000"

    def test_artifact_path_uses_data_dir(self):
        """Test that S3Artifact path is based on dataDir config."""
        config = WorkflowConfig(dataDir=Path("/custom/data"))
        backend = ArgoBackend(config=config)
        step = DummyStep()
        artifact = backend._create_artifact_from_step(step)

        # Check path components (Windows adds drive letter, uses backslashes)
        assert "custom" in artifact.path
        assert "data" in artifact.path
        assert "DummyStep" in artifact.path


class TestArgoBackendWorkflowCreationCornerCases:
    """Comprehensive tests for workflow creation covering edge cases and corner cases."""

    @pytest.mark.parametrize(
        "config_kwargs,expected_workflow_kind,test_description",
        [
            pytest.param(
                {"schedule": "0 0 * * *", "name": "cron-wf"},
                "CronWorkflow",
                "cron_with_custom_name",
                id="cron_custom_name",
            ),
            pytest.param(
                {"schedule": None, "name": "manual-wf"},
                "Workflow",
                "normal_with_custom_name",
                id="normal_custom_name",
            ),
            pytest.param(
                {"schedule": "*/5 * * * *"},
                "CronWorkflow",
                "cron_every_5_minutes",
                id="cron_5min",
            ),
            pytest.param(
                {"schedule": None, "namespace": "custom-namespace"},
                "Workflow",
                "normal_custom_namespace",
                id="normal_custom_ns",
            ),
        ],
    )
    def test_workflow_creation_with_various_configs(self, config_kwargs, expected_workflow_kind, test_description):
        """Test workflow creation with various configuration combinations."""
        config = WorkflowConfig(**config_kwargs)
        backend = ArgoBackend(config=config)
        step = DummyStep()

        workflow = backend._generate_workflow(step)

        assert workflow.kind == expected_workflow_kind, f"Failed for: {test_description}"

    def test_normal_workflow_yaml_structure(self):
        """Test that normal Workflow (schedule=None) has correct YAML structure."""
        config = WorkflowConfig(
            name="test-normal-workflow",
            namespace="test-ns",
            schedule=None,  # Explicitly no schedule
        )
        backend = ArgoBackend(config=config)
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)
        workflow_dict = yaml.safe_load(yaml_output)

        # Verify it's a normal Workflow
        assert workflow_dict["kind"] == "Workflow"
        assert workflow_dict["metadata"]["name"] == "test-normal-workflow"
        assert workflow_dict["metadata"]["namespace"] == "test-ns"

        # Normal Workflow should NOT have schedule in spec
        spec = workflow_dict.get("spec", {})
        assert "schedule" not in spec

        # Should have required workflow fields
        assert "entrypoint" in spec
        assert "templates" in spec

    def test_cron_workflow_yaml_structure(self):
        """Test that CronWorkflow has correct YAML structure with schedule."""
        config = WorkflowConfig(
            name="test-cron-workflow",
            namespace="test-ns",
            schedule="0 4 * * *",
        )
        backend = ArgoBackend(config=config)
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)
        workflow_dict = yaml.safe_load(yaml_output)

        # Verify it's a CronWorkflow
        assert workflow_dict["kind"] == "CronWorkflow"
        assert workflow_dict["metadata"]["name"] == "test-cron-workflow"

        # CronWorkflow should have schedule in spec
        spec = workflow_dict.get("spec", {})
        assert "schedule" in spec
        assert spec["schedule"] == "0 4 * * *"

        # Should have workflowSpec nested inside
        assert "workflowSpec" in spec

    @pytest.mark.parametrize(
        "schedule,expected_in_yaml",
        [
            pytest.param("0 0 * * *", True, id="schedule_present"),
            pytest.param(None, False, id="schedule_absent"),
        ],
    )
    def test_schedule_presence_in_yaml(self, schedule, expected_in_yaml):
        """Test that schedule is correctly present/absent in generated YAML."""
        config = WorkflowConfig(schedule=schedule)
        backend = ArgoBackend(config=config)
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)

        if expected_in_yaml:
            assert "schedule:" in yaml_output
        else:
            # Normal Workflow shouldn't have schedule field
            workflow_dict = yaml.safe_load(yaml_output)
            spec = workflow_dict.get("spec", {})
            assert "schedule" not in spec

    def test_workflow_with_complex_dag(self):
        """Test workflow creation with multi-step DAG (normal Workflow)."""
        config = WorkflowConfig(schedule=None)  # Normal Workflow
        backend = ArgoBackend(config=config)

        step1 = DummyStep()
        step2 = DummyFollowStep()
        step1 >> step2

        workflow = backend._generate_workflow(step2)

        assert workflow.kind == "Workflow"

        yaml_output = backend.generate_artifact(step2)
        workflow_dict = yaml.safe_load(yaml_output)

        # Should have templates for both steps
        templates = workflow_dict["spec"]["templates"]
        template_names = [t.get("name", "") for t in templates]

        # Check that both step types are present
        assert any("dummystep" in name for name in template_names)
        assert any("dummyfollowstep" in name for name in template_names)

    def test_workflow_entrypoint_configuration(self):
        """Test that entrypoint is correctly set for both workflow types."""
        for schedule in [None, "0 0 * * *"]:
            config = WorkflowConfig(
                schedule=schedule,
                entrypoint="custom-entrypoint",
            )
            backend = ArgoBackend(config=config)
            step = DummyStep()

            yaml_output = backend.generate_artifact(step)
            workflow_dict = yaml.safe_load(yaml_output)

            if schedule:
                # CronWorkflow has nested workflowSpec
                assert workflow_dict["spec"]["workflowSpec"]["entrypoint"] == "custom-entrypoint"
            else:
                # Normal Workflow has direct spec
                assert workflow_dict["spec"]["entrypoint"] == "custom-entrypoint"

    def test_workflow_service_account_configuration(self):
        """Test that service account is correctly set for both workflow types."""
        for schedule in [None, "0 0 * * *"]:
            config = WorkflowConfig(
                schedule=schedule,
                serviceAccountName="custom-sa",
            )
            backend = ArgoBackend(config=config)
            step = DummyStep()

            yaml_output = backend.generate_artifact(step)
            workflow_dict = yaml.safe_load(yaml_output)

            if schedule:
                # CronWorkflow
                service_account = workflow_dict["spec"]["workflowSpec"]["serviceAccountName"]
            else:
                # Normal Workflow
                service_account = workflow_dict["spec"]["serviceAccountName"]

            assert service_account == "custom-sa"

    def test_normal_workflow_from_values_file(self, tmp_path):
        """Test creating normal Workflow from values file with schedule=null."""
        values_content = {
            "workflows": {
                "no-schedule-workflow": {
                    "name": "no-schedule-wf",
                    "namespace": "test-ns",
                    "schedule": None,  # Explicitly null/None
                    "container": {
                        "image": "test-image:latest",
                    },
                }
            }
        }
        values_file = tmp_path / "values.yaml"
        values_file.write_text(yaml.safe_dump(values_content))

        backend = ArgoBackend.from_values([values_file], workflow_name="no-schedule-workflow")
        step = DummyStep()

        workflow = backend._generate_workflow(step)
        assert workflow.kind == "Workflow"

        yaml_output = backend.generate_artifact(step)
        workflow_dict = yaml.safe_load(yaml_output)
        assert workflow_dict["kind"] == "Workflow"
        assert "schedule" not in workflow_dict["spec"]

    def test_workflow_annotations(self):
        """Test that annotations are correctly applied to both workflow types."""
        annotations = {"annotation-key": "annotation-value"}

        for schedule in [None, "0 0 * * *"]:
            config = WorkflowConfig(
                schedule=schedule,
                annotations=annotations,
            )
            backend = ArgoBackend(config=config)
            step = DummyStep()

            yaml_output = backend.generate_artifact(step)
            workflow_dict = yaml.safe_load(yaml_output)

            # Annotations should be in metadata
            assert workflow_dict["metadata"]["annotations"]["annotation-key"] == "annotation-value"
