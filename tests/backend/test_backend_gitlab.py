# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.backend.backend_gitlab module."""

from pathlib import Path

import pytest
import yaml

from wurzel.backend.backend_gitlab import (
    GitlabArtifactConfig,
    GitlabBackend,
    GitlabCacheConfig,
    GitlabConfig,
    GitlabImageConfig,
    GitlabJobConfig,
    GitlabTemplateValues,
    select_pipeline,
)
from wurzel.backend.values import load_values
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
def sample_gitlab_values_file(tmp_path: Path) -> Path:
    """Create a sample values.yaml file with GitLab config."""
    content = {
        "gitlab": {
            "test-pipeline": {
                "dataDir": "./custom-data",
                "encapsulateEnv": False,
                "image": {"name": "custom-image:latest"},
                "variables": {"ENV_VAR": "test-value"},
                "stages": ["build", "test", "deploy"],
            }
        },
    }
    file_path = tmp_path / "values.yaml"
    file_path.write_text(yaml.safe_dump(content))
    return file_path


@pytest.fixture
def override_gitlab_values_file(tmp_path: Path) -> Path:
    """Create an override values.yaml file."""
    content = {
        "gitlab": {
            "test-pipeline": {
                "dataDir": "./override-data",
                "image": {"name": "override-image:v2"},
            }
        }
    }
    file_path = tmp_path / "override.yaml"
    file_path.write_text(yaml.safe_dump(content))
    return file_path


# ---------------------------------------------------------------------------
# Tests for Pydantic Models
# ---------------------------------------------------------------------------


class TestGitlabImageConfig:
    def test_defaults(self):
        config = GitlabImageConfig()
        assert config.name == "ghcr.io/telekom/wurzel:latest"
        assert config.pull_policy is None

    def test_custom_values(self):
        config = GitlabImageConfig(name="custom:v1", pull_policy="always")
        assert config.name == "custom:v1"
        assert config.pull_policy == "always"


class TestGitlabArtifactConfig:
    def test_defaults(self):
        config = GitlabArtifactConfig()
        assert config.paths == ["data/"]
        assert config.expire_in == "1 week"
        assert config.when == "on_success"

    def test_custom_values(self):
        config = GitlabArtifactConfig(paths=["output/"], expire_in="2 weeks", when="always")
        assert config.paths == ["output/"]
        assert config.expire_in == "2 weeks"
        assert config.when == "always"


class TestGitlabCacheConfig:
    def test_defaults(self):
        config = GitlabCacheConfig()
        assert config.paths == []
        assert config.key == "${CI_COMMIT_REF_SLUG}"
        assert config.policy == "pull-push"

    def test_custom_values(self):
        config = GitlabCacheConfig(paths=[".cache/"], key="custom-key", policy="pull")
        assert config.paths == [".cache/"]
        assert config.key == "custom-key"
        assert config.policy == "pull"


class TestGitlabJobConfig:
    def test_defaults(self):
        config = GitlabJobConfig()
        assert config.stage == "process"
        assert config.tags == []
        assert config.timeout is None
        assert config.retry == 0
        assert config.allow_failure is False
        assert config.rules == []
        assert config.before_script == []
        assert config.after_script == []

    def test_custom_values(self):
        config = GitlabJobConfig(
            stage="build",
            tags=["docker"],
            timeout="1h",
            retry=2,
            allow_failure=True,
            rules=[{"if": "$CI_COMMIT_BRANCH"}],
            before_script=["echo 'before'"],
            after_script=["echo 'after'"],
        )
        assert config.stage == "build"
        assert config.tags == ["docker"]
        assert config.timeout == "1h"
        assert config.retry == 2
        assert config.allow_failure is True
        assert config.rules == [{"if": "$CI_COMMIT_BRANCH"}]
        assert config.before_script == ["echo 'before'"]
        assert config.after_script == ["echo 'after'"]


class TestGitlabConfig:
    def test_defaults(self):
        config = GitlabConfig()
        assert config.dataDir == Path("./data")
        assert config.encapsulateEnv is True
        assert config.image.name == "ghcr.io/telekom/wurzel:latest"
        assert config.variables == {}
        assert config.stages == ["process"]

    def test_custom_values(self):
        config = GitlabConfig(
            dataDir=Path("./custom"),
            encapsulateEnv=False,
            image=GitlabImageConfig(name="custom:latest"),
            variables={"KEY": "value"},
            stages=["stage1", "stage2"],
        )
        assert config.dataDir == Path("./custom")
        assert config.encapsulateEnv is False
        assert config.image.name == "custom:latest"
        assert config.variables == {"KEY": "value"}
        assert config.stages == ["stage1", "stage2"]


class TestGitlabTemplateValues:
    def test_empty(self):
        values = GitlabTemplateValues()
        assert values.gitlab == {}

    def test_with_pipelines(self):
        values = GitlabTemplateValues(gitlab={"pipeline1": GitlabConfig()})
        assert "pipeline1" in values.gitlab


# ---------------------------------------------------------------------------
# Tests for Utility Functions
# ---------------------------------------------------------------------------


class TestSelectPipeline:
    def test_select_by_name(self):
        values = GitlabTemplateValues(
            gitlab={
                "p1": GitlabConfig(dataDir=Path("./data1")),
                "p2": GitlabConfig(dataDir=Path("./data2")),
            }
        )
        result = select_pipeline(values, "p2")
        assert result.dataDir == Path("./data2")

    def test_select_first_when_no_name(self):
        values = GitlabTemplateValues(gitlab={"first": GitlabConfig(dataDir=Path("./first-data"))})
        result = select_pipeline(values, None)
        assert result.dataDir == Path("./first-data")

    def test_returns_default_when_empty(self):
        values = GitlabTemplateValues()
        result = select_pipeline(values, None)
        assert result.dataDir == Path("./data")

    def test_nonexistent_pipeline_raises(self):
        values = GitlabTemplateValues(gitlab={"existing": GitlabConfig()})
        with pytest.raises(ValueError, match="not found in values"):
            select_pipeline(values, "nonexistent")


class TestLoadGitlabValues:
    def test_single_file(self, sample_gitlab_values_file: Path):
        values = load_values([sample_gitlab_values_file], GitlabTemplateValues)
        assert "test-pipeline" in values.gitlab
        assert values.gitlab["test-pipeline"].dataDir == Path("./custom-data")
        assert values.gitlab["test-pipeline"].encapsulateEnv is False
        assert values.gitlab["test-pipeline"].image.name == "custom-image:latest"

    def test_multiple_files_merge(self, sample_gitlab_values_file: Path, override_gitlab_values_file: Path):
        values = load_values([sample_gitlab_values_file, override_gitlab_values_file], GitlabTemplateValues)
        pipeline = values.gitlab["test-pipeline"]
        assert pipeline.dataDir == Path("./override-data")
        assert pipeline.encapsulateEnv is False  # From base, not overridden
        assert pipeline.image.name == "override-image:v2"

    def test_empty_file(self, tmp_path: Path):
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        values = load_values([empty_file], GitlabTemplateValues)
        assert values.gitlab == {}


# ---------------------------------------------------------------------------
# Tests for GitlabBackend Class
# ---------------------------------------------------------------------------


class TestGitlabBackendInit:
    def test_default_config(self):
        backend = GitlabBackend()
        assert backend.config.dataDir == Path("./data")
        assert backend.config.encapsulateEnv is True

    def test_custom_config(self):
        config = GitlabConfig(dataDir=Path("./custom"), encapsulateEnv=False)
        backend = GitlabBackend(config=config)
        assert backend.config.dataDir == Path("./custom")
        assert backend.config.encapsulateEnv is False


class TestGitlabBackendFromValues:
    def test_factory_method(self, sample_gitlab_values_file: Path):
        backend = GitlabBackend.from_values([sample_gitlab_values_file], workflow_name="test-pipeline")
        assert backend.config.dataDir == Path("./custom-data")
        assert backend.config.encapsulateEnv is False

    def test_factory_selects_first_pipeline(self, sample_gitlab_values_file: Path):
        backend = GitlabBackend.from_values([sample_gitlab_values_file])
        assert backend.config.dataDir == Path("./custom-data")

    def test_factory_with_multiple_files(self, sample_gitlab_values_file: Path, override_gitlab_values_file: Path):
        backend = GitlabBackend.from_values([sample_gitlab_values_file, override_gitlab_values_file], workflow_name="test-pipeline")
        assert backend.config.dataDir == Path("./override-data")


class TestGitlabBackendGenerateArtifact:
    def test_generates_valid_yaml(self):
        backend = GitlabBackend()
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        assert "DummyStep" in data
        assert "image" in data
        assert "stages" in data

    def test_uses_config_data_dir(self):
        config = GitlabConfig(dataDir=Path("./custom-output"))
        backend = GitlabBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        expected_path = str(Path("custom-output/DummyStep"))
        assert expected_path in data["DummyStep"]["artifacts"]["paths"][0]

    def test_pipeline_with_dependencies(self):
        backend = GitlabBackend()
        step1 = DummyStep()
        step2 = DummyFollowStep()
        step1 >> step2

        yaml_output = backend.generate_artifact(step2)
        data = yaml.safe_load(yaml_output)

        assert "DummyStep" in data
        assert "DummyFollowStep" in data
        assert "needs" in data["DummyFollowStep"]
        assert "DummyStep" in data["DummyFollowStep"]["needs"]

    def test_job_has_script(self):
        backend = GitlabBackend()
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        assert "script" in data["DummyStep"]
        assert isinstance(data["DummyStep"]["script"], list)
        assert len(data["DummyStep"]["script"]) > 0

    def test_job_has_artifacts(self):
        backend = GitlabBackend()
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        assert "artifacts" in data["DummyStep"]
        assert "paths" in data["DummyStep"]["artifacts"]
        assert "expire_in" in data["DummyStep"]["artifacts"]
        assert "when" in data["DummyStep"]["artifacts"]

    def test_custom_image_configuration(self):
        config = GitlabConfig(image=GitlabImageConfig(name="custom-wurzel:v2.0", pull_policy="always"))
        backend = GitlabBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        assert "image" in data
        assert isinstance(data["image"], dict)
        assert data["image"]["name"] == "custom-wurzel:v2.0"
        assert data["image"]["pull_policy"] == "always"

    def test_variables_in_output(self):
        config = GitlabConfig(variables={"CI_VAR": "value", "ANOTHER_VAR": "another"})
        backend = GitlabBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        assert "variables" in data
        assert data["variables"]["CI_VAR"] == "value"
        assert data["variables"]["ANOTHER_VAR"] == "another"

    def test_cache_configuration(self):
        config = GitlabConfig(cache=GitlabCacheConfig(paths=[".cache/pip"], key="pip-cache", policy="pull"))
        backend = GitlabBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        assert "cache" in data
        assert data["cache"]["paths"] == [".cache/pip"]
        assert data["cache"]["key"] == "pip-cache"
        assert data["cache"]["policy"] == "pull"

    def test_job_tags(self):
        config = GitlabConfig(defaultJob=GitlabJobConfig(tags=["docker", "linux"]))
        backend = GitlabBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        assert "tags" in data["DummyStep"]
        assert data["DummyStep"]["tags"] == ["docker", "linux"]

    def test_job_timeout(self):
        config = GitlabConfig(defaultJob=GitlabJobConfig(timeout="2h"))
        backend = GitlabBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        assert "timeout" in data["DummyStep"]
        assert data["DummyStep"]["timeout"] == "2h"

    def test_job_retry(self):
        config = GitlabConfig(defaultJob=GitlabJobConfig(retry=2))
        backend = GitlabBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        assert "retry" in data["DummyStep"]
        assert data["DummyStep"]["retry"] == 2

    def test_job_allow_failure(self):
        config = GitlabConfig(defaultJob=GitlabJobConfig(allow_failure=True))
        backend = GitlabBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        assert "allow_failure" in data["DummyStep"]
        assert data["DummyStep"]["allow_failure"] is True

    def test_job_rules(self):
        config = GitlabConfig(defaultJob=GitlabJobConfig(rules=[{"if": "$CI_COMMIT_BRANCH == 'main'"}]))
        backend = GitlabBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        assert "rules" in data["DummyStep"]
        assert data["DummyStep"]["rules"] == [{"if": "$CI_COMMIT_BRANCH == 'main'"}]

    def test_job_before_script(self):
        config = GitlabConfig(defaultJob=GitlabJobConfig(before_script=["pip install -U pip", "pip install -e ."]))
        backend = GitlabBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        assert "before_script" in data["DummyStep"]
        assert data["DummyStep"]["before_script"] == ["pip install -U pip", "pip install -e ."]

    def test_job_after_script(self):
        config = GitlabConfig(defaultJob=GitlabJobConfig(after_script=["cleanup.sh"]))
        backend = GitlabBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        assert "after_script" in data["DummyStep"]
        assert data["DummyStep"]["after_script"] == ["cleanup.sh"]


class TestGitlabBackendIntegration:
    def test_full_workflow_from_yaml(self, sample_gitlab_values_file: Path):
        """Test complete workflow: load from YAML and generate artifact."""
        backend = GitlabBackend.from_values([sample_gitlab_values_file], workflow_name="test-pipeline")
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)
        data = yaml.safe_load(yaml_output)

        assert "DummyStep" in data
        expected_path = str(Path("custom-data/DummyStep"))
        assert expected_path in data["DummyStep"]["artifacts"]["paths"][0]
        assert data["image"] == "custom-image:latest"
        assert data["variables"]["ENV_VAR"] == "test-value"
        assert data["stages"] == ["build", "test", "deploy"]

    def test_complex_pipeline(self):
        """Test a more complex pipeline with multiple dependencies."""
        backend = GitlabBackend()

        # Create a chain: step1 -> step2 -> step3
        class Step1(TypedStep[NoSettings, None, MarkdownDataContract]):
            def run(self, inpt: None) -> MarkdownDataContract:
                return MarkdownDataContract(content="step1")

        class Step2(TypedStep[NoSettings, MarkdownDataContract, MarkdownDataContract]):
            def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
                return inpt

        class Step3(TypedStep[NoSettings, MarkdownDataContract, MarkdownDataContract]):
            def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
                return inpt

        step1 = Step1()
        step2 = Step2()
        step3 = Step3()

        step1 >> step2 >> step3

        yaml_output = backend.generate_artifact(step3)
        data = yaml.safe_load(yaml_output)

        # Verify all steps are present
        assert "Step1" in data
        assert "Step2" in data
        assert "Step3" in data

        # Verify dependencies
        assert "needs" not in data["Step1"]  # First step has no dependencies
        assert data["Step2"]["needs"] == ["Step1"]
        assert data["Step3"]["needs"] == ["Step2"]

    def test_is_available(self):
        """Test that GitlabBackend is always available."""
        assert GitlabBackend.is_available() is True
