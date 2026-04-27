# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for DvcBackend with refactored structure."""

import shlex
from pathlib import Path

import pytest

from wurzel.executors.backend.backend_dvc import DvcBackend, DvcBackendSettings

from .helpers import DummyFollowStep, DummyStep


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
        assert settings.DATA_DIR == Path("/custom/path")
        assert settings.ENCAPSULATE_ENV is False

    def test_is_available(self):
        """Test DvcBackend.is_available() returns True."""
        assert DvcBackend.is_available() is True

    @pytest.mark.parametrize(
        "kwargs",
        [
            pytest.param({"middlewares": ["prometheus"]}, id="with_middlewares"),
            pytest.param({"dont_encapsulate": True}, id="dont_encapsulate"),
            pytest.param({"middlewares": [], "dont_encapsulate": True}, id="both_options"),
            pytest.param({"middlewares": []}, id="empty_middlewares"),
        ],
    )
    def test_backend_initialization_with_options(self, kwargs):
        """Test DvcBackend can be initialized with various option combinations."""
        assert DvcBackend(**kwargs) is not None

    def test_backend_load_middlewares_from_env(self, monkeypatch):
        """Test DvcBackend can load middlewares from environment."""
        monkeypatch.setenv("MIDDLEWARES", "prometheus")
        backend = DvcBackend(load_middlewares_from_env=True)
        assert backend is not None

    def test_generate_artifact_with_custom_data_dir(self, tmp_path):
        """Test DvcBackend respects custom DATA_DIR setting."""
        custom_dir = tmp_path / "custom_data"
        settings = DvcBackendSettings(DATA_DIR=custom_dir)
        backend = DvcBackend(settings=settings)
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)

        assert str(custom_dir) in yaml_output

    def test_generate_artifact_without_encapsulation(self):
        """Test DvcBackend with ENCAPSULATE_ENV disabled."""
        settings = DvcBackendSettings(ENCAPSULATE_ENV=False)
        backend = DvcBackend(settings=settings)
        step = DummyStep()

        yaml_output = backend.generate_artifact(step)

        assert "wurzel run" in yaml_output


class TestWriteEnvFile:
    def test_valid_keys_written(self, tmp_path):
        settings = DvcBackendSettings(DATA_DIR=tmp_path)
        backend = DvcBackend(settings=settings)
        env_file = backend._write_env_file({"FOO": "bar", "MY_VAR": "hello"})
        content = env_file.read_text()
        assert "export FOO='bar'" in content
        assert "export MY_VAR='hello'" in content

    @pytest.mark.parametrize(
        "bad_key",
        [
            "FOO; rm -rf /",
            "1INVALID",
            "foo",
            "MY VAR",
            "KEY\nINJECT",
            "",
        ],
    )
    def test_invalid_key_raises_value_error(self, tmp_path, bad_key):
        settings = DvcBackendSettings(DATA_DIR=tmp_path)
        backend = DvcBackend(settings=settings)
        with pytest.raises(ValueError, match="environment variable"):
            backend._write_env_file({bad_key: "value"})

    def test_env_file_path_is_quoted_in_command(self, tmp_path):
        """Env file path with spaces must be quoted in the shell command."""
        import yaml  # noqa: PLC0415

        data_dir = tmp_path / "my data dir"
        settings = DvcBackendSettings(DATA_DIR=data_dir)
        backend = DvcBackend(settings=settings)
        step = DummyStep()
        yaml_output = backend.generate_artifact(step, env_vars={"MY_VAR": "value"})
        parsed = yaml.safe_load(yaml_output)
        cmd = parsed["stages"]["DummyStep"]["cmd"]
        env_file = data_dir / ".wurzel_env"
        assert shlex.quote(str(env_file)) in cmd
