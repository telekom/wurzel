# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for backend implementations with executors and middlewares."""

from pathlib import Path

import pytest

from wurzel.core import NoSettings, TypedStep
from wurzel.datacontract.common import MarkdownDataContract
from wurzel.executors.backend.backend_dvc import DvcBackend, DvcBackendSettings
from wurzel.utils import HAS_HERA

from .helpers import DummyFollowStep, DummyStep

if HAS_HERA:
    from wurzel.executors.backend.backend_argo import ArgoBackend


class TestBackendWithMiddlewares:
    def test_dvc_backend_with_prometheus_middleware(self):
        """Test DvcBackend with Prometheus middleware enabled."""
        backend = DvcBackend(middlewares=["prometheus"])
        yaml_output = backend.generate_artifact(DummyStep())

        assert yaml_output is not None
        assert "wurzel run" in yaml_output

    def test_dvc_backend_with_multiple_middlewares(self):
        """Test DvcBackend with multiple middlewares."""
        assert DvcBackend(middlewares=["prometheus"]) is not None

    def test_dvc_backend_load_middlewares_from_env(self, monkeypatch):
        """Test DvcBackend loading middlewares from environment."""
        monkeypatch.setenv("MIDDLEWARES", "prometheus")
        backend = DvcBackend(load_middlewares_from_env=True)
        assert backend.generate_artifact(DummyStep()) is not None


class TestBackendWithComplexPipelines:
    def test_dvc_backend_with_linear_pipeline(self):
        """Test DvcBackend with a linear pipeline of steps."""
        backend = DvcBackend()

        step1 = DummyStep()
        step2 = DummyFollowStep()
        step3 = DummyFollowStep()
        step1 >> step2 >> step3

        yaml_output = backend.generate_artifact(step3)

        assert "DummyStep" in yaml_output
        assert "DummyFollowStep" in yaml_output
        assert "deps:" in yaml_output

    def test_dvc_backend_with_branching_pipeline(self):
        """Test DvcBackend with a branching pipeline."""
        backend = DvcBackend()

        source = DummyStep()
        branch1 = DummyFollowStep()
        branch2 = DummyFollowStep()
        source >> branch1
        source >> branch2

        yaml_output1 = backend.generate_artifact(branch1)
        yaml_output2 = backend.generate_artifact(branch2)

        assert "DummyStep" in yaml_output1
        assert "DummyStep" in yaml_output2


class TestBackendWithCustomPaths:
    def test_dvc_backend_respects_custom_data_directory(self, tmp_path):
        """Test that DvcBackend uses custom DATA_DIR in output."""
        custom_dir = tmp_path / "my_custom_data"
        settings = DvcBackendSettings(DATA_DIR=custom_dir)
        yaml_output = DvcBackend(settings=settings).generate_artifact(DummyStep())
        assert str(custom_dir) in yaml_output

    def test_dvc_backend_with_absolute_path(self, tmp_path):
        """Test DvcBackend with absolute path."""
        absolute_path = tmp_path.resolve() / "absolute"
        settings = DvcBackendSettings(DATA_DIR=absolute_path)
        yaml_output = DvcBackend(settings=settings).generate_artifact(DummyStep())
        assert str(absolute_path) in yaml_output

    def test_dvc_backend_with_relative_path(self):
        """Test DvcBackend with relative path."""
        settings = DvcBackendSettings(DATA_DIR=Path("./data/relative"))
        yaml_output = DvcBackend(settings=settings).generate_artifact(DummyStep())
        assert "relative" in yaml_output


class TestBackendEncapsulation:
    @pytest.mark.parametrize(
        "encapsulate,expect_flag",
        [
            pytest.param(True, True, id="encapsulation_enabled"),
            pytest.param(False, False, id="encapsulation_disabled"),
        ],
    )
    def test_dvc_backend_encapsulation_flag_in_output(self, encapsulate, expect_flag):
        """Test DvcBackend encapsulation flag presence in generated YAML."""
        settings = DvcBackendSettings(ENCAPSULATE_ENV=encapsulate)
        yaml_output = DvcBackend(settings=settings).generate_artifact(DummyStep())
        assert "wurzel run" in yaml_output
        assert ("--encapsulate-env" in yaml_output) is expect_flag

    def test_dvc_backend_dont_encapsulate_parameter(self):
        """Test DvcBackend with dont_encapsulate constructor parameter."""
        yaml_output = DvcBackend(dont_encapsulate=True).generate_artifact(DummyStep())
        assert yaml_output is not None


class TestBackendConsistency:
    def test_dvc_backend_generates_consistent_output(self):
        """Test that DvcBackend generates consistent output for same input."""
        backend = DvcBackend()
        step = DummyStep()
        assert backend.generate_artifact(step) == backend.generate_artifact(step)

    def test_dvc_backend_different_steps_produce_different_output(self):
        """Test that different steps produce different output."""
        backend = DvcBackend()

        class StepA(TypedStep[NoSettings, None, MarkdownDataContract]):
            def run(self, inpt: None) -> MarkdownDataContract:
                return MarkdownDataContract(content="a")

        class StepB(TypedStep[NoSettings, None, MarkdownDataContract]):
            def run(self, inpt: None) -> MarkdownDataContract:
                return MarkdownDataContract(content="b")

        yaml_a = backend.generate_artifact(StepA())
        yaml_b = backend.generate_artifact(StepB())

        assert yaml_a != yaml_b
        assert "StepA" in yaml_a
        assert "StepB" in yaml_b

    @pytest.mark.skipif(not HAS_HERA, reason="Hera not available")
    def test_argo_backend_generates_consistent_output(self):
        """Test that ArgoBackend generates consistent output for same input."""
        backend = ArgoBackend()
        step = DummyStep()
        assert backend.generate_artifact(step) == backend.generate_artifact(step)


class TestBackendErrorHandling:
    def test_dvc_backend_with_none_step_raises_error(self):
        """Test that DvcBackend raises error with None step."""
        with pytest.raises(AttributeError):
            DvcBackend().generate_artifact(None)  # type: ignore

    @pytest.mark.skipif(not HAS_HERA, reason="Hera not available")
    def test_argo_backend_with_none_step_raises_error(self):
        """Test that ArgoBackend raises error with None step."""
        with pytest.raises(AttributeError):
            ArgoBackend().generate_artifact(None)  # type: ignore
