# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for DvcBackend with refactored structure."""

from wurzel.core import NoSettings, TypedStep
from wurzel.datacontract.common import MarkdownDataContract
from wurzel.executors.backend.backend_dvc import DvcBackend, DvcBackendSettings


class DummyStep(TypedStep[NoSettings, None, MarkdownDataContract]):
    """A simple step with no dependencies for testing."""

    def run(self, inpt: None) -> MarkdownDataContract:
        return MarkdownDataContract(content="test")


class DummyFollowStep(TypedStep[NoSettings, MarkdownDataContract, MarkdownDataContract]):
    """A step that depends on another step."""

    def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
        return inpt


class TestDvcBackend:
    def test_backend_initialization(self):
        """Test DvcBackend can be initialized."""
        backend = DvcBackend()
        assert backend is not None
        assert isinstance(backend.settings, DvcBackendSettings)

    def test_backend_with_custom_settings(self, tmp_path):
        """Test DvcBackend with custom settings."""
        settings = DvcBackendSettings(DATA_DIR=tmp_path / "custom")
        backend = DvcBackend(settings=settings)
        assert backend.settings.DATA_DIR == tmp_path / "custom"

    def test_generate_artifact_single_step(self):
        """Test generating DVC YAML for a single step."""
        backend = DvcBackend()
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)

        assert yaml_output is not None
        assert "stages:" in yaml_output
        assert "DummyStep:" in yaml_output
        assert "cmd:" in yaml_output
        assert "wurzel run" in yaml_output

    def test_generate_artifact_chained_steps(self):
        """Test generating DVC YAML for chained steps."""
        backend = DvcBackend()
        step1 = DummyStep()
        step2 = DummyFollowStep()
        step1 >> step2

        yaml_output = backend.generate_artifact(step2)

        assert "DummyStep:" in yaml_output
        assert "DummyFollowStep:" in yaml_output
        assert "deps:" in yaml_output
        assert "outs:" in yaml_output

    def test_backend_settings_from_env(self, monkeypatch):
        """Test DvcBackend settings can be loaded from environment."""
        monkeypatch.setenv("DVCBACKEND__DATA_DIR", "/custom/path")
        monkeypatch.setenv("DVCBACKEND__ENCAPSULATE_ENV", "false")

        settings = DvcBackendSettings()
        assert str(settings.DATA_DIR) == "/custom/path"
        assert settings.ENCAPSULATE_ENV is False

    def test_is_available(self):
        """Test DvcBackend.is_available() returns True."""
        assert DvcBackend.is_available() is True
