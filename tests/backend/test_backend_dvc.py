# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.backend.backend_dvc module."""

from pathlib import Path

import pytest
import yaml

from wurzel.backend.backend_dvc import (
    DvcBackend,
    DvcBackendSettings,
    DvcConfig,
    DvcTemplateValues,
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
def sample_dvc_values_file(tmp_path: Path) -> Path:
    """Create a sample values.yaml file with DVC config."""
    content = {
        "dvc": {
            "test-pipeline": {
                "dataDir": "./custom-data",
                "encapsulateEnv": False,
            }
        },
    }
    file_path = tmp_path / "values.yaml"
    file_path.write_text(yaml.safe_dump(content))
    return file_path


@pytest.fixture
def override_dvc_values_file(tmp_path: Path) -> Path:
    """Create an override values.yaml file."""
    content = {
        "dvc": {
            "test-pipeline": {
                "dataDir": "./override-data",
            }
        }
    }
    file_path = tmp_path / "override.yaml"
    file_path.write_text(yaml.safe_dump(content))
    return file_path


# ---------------------------------------------------------------------------
# Tests for Pydantic Models
# ---------------------------------------------------------------------------


class TestDvcConfig:
    def test_defaults(self):
        config = DvcConfig()
        assert config.dataDir == Path("./data")
        assert config.encapsulateEnv is True

    def test_custom_values(self):
        config = DvcConfig(dataDir=Path("./custom"), encapsulateEnv=False)
        assert config.dataDir == Path("./custom")
        assert config.encapsulateEnv is False


class TestDvcBackendSettings:
    def test_defaults(self):
        settings = DvcBackendSettings()
        assert settings.DATA_DIR == Path("./data")
        assert settings.ENCAPSULATE_ENV is True

    def test_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("DVCBACKEND__DATA_DIR", "./env-data")
        monkeypatch.setenv("DVCBACKEND__ENCAPSULATE_ENV", "false")

        settings = DvcBackendSettings()
        assert settings.DATA_DIR == Path("./env-data")
        assert settings.ENCAPSULATE_ENV is False


class TestDvcTemplateValues:
    def test_empty(self):
        values = DvcTemplateValues()
        assert values.dvc == {}

    def test_with_pipelines(self):
        values = DvcTemplateValues(dvc={"pipeline1": DvcConfig()})
        assert "pipeline1" in values.dvc


# ---------------------------------------------------------------------------
# Tests for Utility Functions
# ---------------------------------------------------------------------------


class TestSelectPipeline:
    def test_select_by_name(self):
        values = DvcTemplateValues(
            dvc={
                "p1": DvcConfig(dataDir=Path("./data1")),
                "p2": DvcConfig(dataDir=Path("./data2")),
            }
        )
        result = select_pipeline(values, "p2")
        assert result.dataDir == Path("./data2")

    def test_select_first_when_no_name(self):
        values = DvcTemplateValues(dvc={"first": DvcConfig(dataDir=Path("./first-data"))})
        result = select_pipeline(values, None)
        assert result.dataDir == Path("./first-data")

    def test_returns_default_when_empty(self):
        values = DvcTemplateValues()
        result = select_pipeline(values, None)
        assert result.dataDir == Path("./data")

    def test_nonexistent_pipeline_raises(self):
        values = DvcTemplateValues(dvc={"existing": DvcConfig()})
        with pytest.raises(ValueError, match="not found in values"):
            select_pipeline(values, "nonexistent")


class TestLoadDvcValues:
    def test_single_file(self, sample_dvc_values_file: Path):
        values = load_values([sample_dvc_values_file], DvcTemplateValues)
        assert "test-pipeline" in values.dvc
        assert values.dvc["test-pipeline"].dataDir == Path("./custom-data")
        assert values.dvc["test-pipeline"].encapsulateEnv is False

    def test_multiple_files_merge(self, sample_dvc_values_file: Path, override_dvc_values_file: Path):
        values = load_values([sample_dvc_values_file, override_dvc_values_file], DvcTemplateValues)
        pipeline = values.dvc["test-pipeline"]
        assert pipeline.dataDir == Path("./override-data")
        assert pipeline.encapsulateEnv is False  # From base, not overridden

    def test_empty_file(self, tmp_path: Path):
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        values = load_values([empty_file], DvcTemplateValues)
        assert values.dvc == {}


# ---------------------------------------------------------------------------
# Tests for DvcBackend Class
# ---------------------------------------------------------------------------


class TestDvcBackendInit:
    def test_default_config(self):
        backend = DvcBackend()
        assert backend.config.dataDir == Path("./data")
        assert backend.config.encapsulateEnv is True

    def test_custom_config(self):
        config = DvcConfig(dataDir=Path("./custom"), encapsulateEnv=False)
        backend = DvcBackend(config=config)
        assert backend.config.dataDir == Path("./custom")
        assert backend.config.encapsulateEnv is False

    def test_config_from_settings(self):
        settings = DvcBackendSettings(DATA_DIR=Path("./settings-data"), ENCAPSULATE_ENV=False)
        backend = DvcBackend(settings=settings)
        assert backend.config.dataDir == Path("./settings-data")
        assert backend.config.encapsulateEnv is False

    def test_config_overrides_settings(self):
        settings = DvcBackendSettings(DATA_DIR=Path("./settings-data"))
        config = DvcConfig(dataDir=Path("./config-data"))
        backend = DvcBackend(config=config, settings=settings)
        assert backend.config.dataDir == Path("./config-data")


class TestDvcBackendFromEnvVars:
    def test_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("DVCBACKEND__DATA_DIR", "./env-data")
        monkeypatch.setenv("DVCBACKEND__ENCAPSULATE_ENV", "false")

        backend = DvcBackend()
        assert backend.config.dataDir == Path("./env-data")
        assert backend.config.encapsulateEnv is False

    def test_env_vars_with_explicit_settings(self, monkeypatch):
        monkeypatch.setenv("DVCBACKEND__DATA_DIR", "./env-data")

        settings = DvcBackendSettings()
        backend = DvcBackend(settings=settings)
        assert backend.config.dataDir == Path("./env-data")


class TestDvcBackendFromValues:
    def test_factory_method(self, sample_dvc_values_file: Path):
        backend = DvcBackend.from_values([sample_dvc_values_file], workflow_name="test-pipeline")
        assert backend.config.dataDir == Path("./custom-data")
        assert backend.config.encapsulateEnv is False

    def test_factory_selects_first_pipeline(self, sample_dvc_values_file: Path):
        backend = DvcBackend.from_values([sample_dvc_values_file])
        assert backend.config.dataDir == Path("./custom-data")

    def test_factory_with_multiple_files(self, sample_dvc_values_file: Path, override_dvc_values_file: Path):
        backend = DvcBackend.from_values([sample_dvc_values_file, override_dvc_values_file], workflow_name="test-pipeline")
        assert backend.config.dataDir == Path("./override-data")


class TestDvcBackendGenerateArtifact:
    def test_generates_valid_yaml(self):
        backend = DvcBackend()
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        assert "stages" in data
        assert "DummyStep" in data["stages"]

    def test_uses_config_data_dir(self):
        config = DvcConfig(dataDir=Path("./custom-output"))
        backend = DvcBackend(config=config)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step)

        data = yaml.safe_load(yaml_output)
        expected_path = str(Path("custom-output/DummyStep"))
        assert expected_path in data["stages"]["DummyStep"]["outs"][0]

    def test_pipeline_with_dependencies(self):
        backend = DvcBackend()
        step1 = DummyStep()
        step2 = DummyFollowStep()
        step1 >> step2

        yaml_output = backend.generate_artifact(step2)
        data = yaml.safe_load(yaml_output)

        assert "DummyStep" in data["stages"]
        assert "DummyFollowStep" in data["stages"]


class TestDvcBackendIntegration:
    def test_full_workflow_from_yaml(self, sample_dvc_values_file: Path):
        """Test complete workflow: load from YAML and generate artifact."""
        backend = DvcBackend.from_values([sample_dvc_values_file], workflow_name="test-pipeline")
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)
        data = yaml.safe_load(yaml_output)

        assert "stages" in data
        expected_path = str(Path("custom-data/DummyStep"))
        assert expected_path in data["stages"]["DummyStep"]["outs"][0]

    def test_full_workflow_from_env(self, monkeypatch):
        """Test complete workflow: load from env vars and generate artifact."""
        monkeypatch.setenv("DVCBACKEND__DATA_DIR", "./env-output")

        backend = DvcBackend()
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)
        data = yaml.safe_load(yaml_output)

        assert "stages" in data
        expected_path = str(Path("env-output/DummyStep"))
        assert expected_path in data["stages"]["DummyStep"]["outs"][0]
