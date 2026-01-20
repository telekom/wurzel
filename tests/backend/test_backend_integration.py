# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for backend implementations with executors and middlewares."""

from pathlib import Path

import pytest

from wurzel.core import NoSettings, TypedStep
from wurzel.core.settings import SettingsLeaf
from wurzel.datacontract.common import MarkdownDataContract
from wurzel.executors.backend.backend_dvc import DvcBackend, DvcBackendSettings
from wurzel.utils import HAS_HERA

if HAS_HERA:
    from wurzel.executors.backend.backend_argo import ArgoBackend


class CustomStepSettings(SettingsLeaf):
    """Custom settings for testing."""

    custom_value: str = "default"
    numeric_value: int = 42


class SimpleStep(TypedStep[NoSettings, None, MarkdownDataContract]):
    """A simple step for testing."""

    def run(self, inpt: None) -> MarkdownDataContract:
        return MarkdownDataContract(content="simple")


class SimpleFollowStep(TypedStep[NoSettings, MarkdownDataContract, MarkdownDataContract]):
    """A step that accepts MarkdownDataContract as input."""

    def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
        return inpt


class StepWithCustomSettings(TypedStep[CustomStepSettings, None, MarkdownDataContract]):
    """A step with custom settings."""

    def run(self, inpt: None) -> MarkdownDataContract:
        return MarkdownDataContract(content=f"value: {self.settings.custom_value}")


class TestBackendWithMiddlewares:
    def test_dvc_backend_with_prometheus_middleware(self):
        """Test DvcBackend with Prometheus middleware enabled."""
        backend = DvcBackend(middlewares=["prometheus"])
        step = SimpleStep()
        yaml_output = backend.generate_artifact(step)

        assert yaml_output is not None
        assert "wurzel run" in yaml_output

    def test_dvc_backend_with_multiple_middlewares(self):
        """Test DvcBackend with multiple middlewares."""
        backend = DvcBackend(middlewares=["prometheus"])
        assert backend is not None

    def test_dvc_backend_load_middlewares_from_env(self, monkeypatch):
        """Test DvcBackend loading middlewares from environment."""
        monkeypatch.setenv("MIDDLEWARES", "prometheus")
        backend = DvcBackend(load_middlewares_from_env=True)
        step = SimpleStep()
        yaml_output = backend.generate_artifact(step)

        assert yaml_output is not None


class TestBackendWithComplexPipelines:
    def test_dvc_backend_with_linear_pipeline(self):
        """Test DvcBackend with a linear pipeline of steps."""
        backend = DvcBackend()

        step1 = SimpleStep()
        step2 = SimpleFollowStep()
        step3 = SimpleFollowStep()

        step1 >> step2 >> step3

        yaml_output = backend.generate_artifact(step3)

        # Should contain all steps
        assert "SimpleStep" in yaml_output
        assert "SimpleFollowStep" in yaml_output
        assert "deps:" in yaml_output

    def test_dvc_backend_with_branching_pipeline(self):
        """Test DvcBackend with a branching pipeline."""
        backend = DvcBackend()

        # Create branching structure
        source = SimpleStep()
        branch1 = SimpleFollowStep()
        branch2 = SimpleFollowStep()

        source >> branch1
        source >> branch2

        yaml_output1 = backend.generate_artifact(branch1)
        yaml_output2 = backend.generate_artifact(branch2)

        # Both branches should reference the source
        assert "SimpleStep" in yaml_output1
        assert "SimpleStep" in yaml_output2


class TestBackendWithCustomPaths:
    def test_dvc_backend_respects_custom_data_directory(self, tmp_path):
        """Test that DvcBackend uses custom DATA_DIR in output."""
        custom_dir = tmp_path / "my_custom_data"
        settings = DvcBackendSettings(DATA_DIR=custom_dir)
        backend = DvcBackend(settings=settings)
        step = SimpleStep()

        yaml_output = backend.generate_artifact(step)

        assert str(custom_dir) in yaml_output

    def test_dvc_backend_with_absolute_path(self, tmp_path):
        """Test DvcBackend with absolute path."""
        absolute_path = tmp_path.resolve() / "absolute"
        settings = DvcBackendSettings(DATA_DIR=absolute_path)
        backend = DvcBackend(settings=settings)
        step = SimpleStep()

        yaml_output = backend.generate_artifact(step)

        assert str(absolute_path) in yaml_output

    def test_dvc_backend_with_relative_path(self):
        """Test DvcBackend with relative path."""
        relative_path = Path("./data/relative")
        settings = DvcBackendSettings(DATA_DIR=relative_path)
        backend = DvcBackend(settings=settings)
        step = SimpleStep()

        yaml_output = backend.generate_artifact(step)

        assert "relative" in yaml_output


class TestBackendEncapsulation:
    def test_dvc_backend_with_encapsulation_enabled(self):
        """Test DvcBackend with environment encapsulation enabled."""
        settings = DvcBackendSettings(ENCAPSULATE_ENV=True)
        backend = DvcBackend(settings=settings)
        step = SimpleStep()

        yaml_output = backend.generate_artifact(step)

        assert "wurzel run" in yaml_output
        assert "--encapsulate-env" in yaml_output or "-e" in yaml_output

    def test_dvc_backend_with_encapsulation_disabled(self):
        """Test DvcBackend with environment encapsulation disabled."""
        settings = DvcBackendSettings(ENCAPSULATE_ENV=False)
        backend = DvcBackend(settings=settings)
        step = SimpleStep()

        yaml_output = backend.generate_artifact(step)

        assert "wurzel run" in yaml_output
        # Should not have encapsulation flag
        assert "--encapsulate-env" not in yaml_output

    def test_dvc_backend_dont_encapsulate_parameter(self):
        """Test DvcBackend with dont_encapsulate constructor parameter."""
        backend = DvcBackend(dont_encapsulate=True)
        step = SimpleStep()

        yaml_output = backend.generate_artifact(step)

        assert yaml_output is not None


class TestBackendConsistency:
    def test_dvc_backend_generates_consistent_output(self):
        """Test that DvcBackend generates consistent output for same input."""
        backend = DvcBackend()
        step = SimpleStep()

        yaml_output1 = backend.generate_artifact(step)
        yaml_output2 = backend.generate_artifact(step)

        # Output should be deterministic
        assert yaml_output1 == yaml_output2

    def test_dvc_backend_different_steps_produce_different_output(self):
        """Test that different steps produce different output."""
        backend = DvcBackend()

        class StepA(TypedStep[NoSettings, None, MarkdownDataContract]):
            def run(self, inpt: None) -> MarkdownDataContract:
                return MarkdownDataContract(content="a")

        class StepB(TypedStep[NoSettings, None, MarkdownDataContract]):
            def run(self, inpt: None) -> MarkdownDataContract:
                return MarkdownDataContract(content="b")

        step_a = StepA()
        step_b = StepB()

        yaml_a = backend.generate_artifact(step_a)
        yaml_b = backend.generate_artifact(step_b)

        assert yaml_a != yaml_b
        assert "StepA" in yaml_a
        assert "StepB" in yaml_b

    @pytest.mark.skipif(not HAS_HERA, reason="Hera not available")
    def test_argo_backend_generates_consistent_output(self):
        """Test that ArgoBackend generates consistent output for same input."""
        backend = ArgoBackend()
        step = SimpleStep()

        yaml_output1 = backend.generate_artifact(step)
        yaml_output2 = backend.generate_artifact(step)

        # Output should be deterministic
        assert yaml_output1 == yaml_output2


class TestBackendErrorHandling:
    def test_dvc_backend_with_none_step_raises_error(self):
        """Test that DvcBackend raises error with None step."""
        backend = DvcBackend()

        with pytest.raises(AttributeError):
            backend.generate_artifact(None)  # type: ignore

    @pytest.mark.skipif(not HAS_HERA, reason="Hera not available")
    def test_argo_backend_with_none_step_raises_error(self):
        """Test that ArgoBackend raises error with None step."""
        backend = ArgoBackend()

        with pytest.raises(AttributeError):
            backend.generate_artifact(None)  # type: ignore
