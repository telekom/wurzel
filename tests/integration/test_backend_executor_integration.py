# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for Backend and StepExecutor unified architecture.

These tests verify that backends properly inherit from BaseStepExecutor and can:
1. Execute steps directly
2. Generate artifacts with self-referencing CLI calls
3. Work with the CLI system
4. Support middleware and environment encapsulation
"""

import subprocess

import pytest
import yaml

from wurzel.backend import Backend, DvcBackend
from wurzel.cli import generate_cli_call
from wurzel.step_executor import BaseStepExecutor
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.utils import HAS_HERA
from wurzel.utils.meta_settings import WZ


def get_argo_backend():
    """Helper to get ArgoBackend class."""
    if HAS_HERA:
        from wurzel.backend import ArgoBackend

        return ArgoBackend
    return None


class TestBackendInheritance:
    """Test that backends properly inherit from BaseStepExecutor."""

    def test_backend_inherits_from_base_step_executor(self):
        """Verify Backend class inherits from BaseStepExecutor."""
        assert issubclass(Backend, BaseStepExecutor)

    @pytest.mark.parametrize(
        "backend_class",
        [
            pytest.param(DvcBackend, id="DvcBackend"),
            pytest.param(
                get_argo_backend(),
                marks=pytest.mark.skipif(not HAS_HERA, reason="Hera is not available"),
                id="ArgoBackend",
            ),
        ],
    )
    def test_backend_inherits_from_backend_and_executor(self, backend_class):
        """Verify backend classes inherit from Backend and BaseStepExecutor."""
        # Skip if backend_class is None (Hera not available)
        if backend_class is None:
            pytest.skip("Backend not available")

        assert issubclass(backend_class, Backend)
        assert issubclass(backend_class, BaseStepExecutor)


class TestBackendExecution:
    """Test that backends can execute steps like BaseStepExecutor."""

    @pytest.mark.parametrize(
        "backend_class",
        [
            pytest.param(DvcBackend, id="DvcBackend"),
            pytest.param(
                get_argo_backend(),
                marks=pytest.mark.skipif(not HAS_HERA, reason="Hera is not available"),
                id="ArgoBackend",
            ),
        ],
    )
    def test_backend_can_execute_step(self, backend_class, tmp_path, env):
        """Verify backends can execute a step."""
        # Skip if backend_class is None (Hera not available)
        if backend_class is None:
            pytest.skip("Backend not available")

        env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(tmp_path))
        output_path = tmp_path / "output"

        backend = backend_class()
        with backend as executor:
            results = executor.execute_step(ManualMarkdownStep, set(), output_path)

        assert len(results) == 1
        assert output_path.exists()

    def test_backend_supports_middlewares(self, tmp_path, env):
        """Verify backends support middleware system."""
        env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(tmp_path))
        output_path = tmp_path / "output"

        # Backend with middleware
        backend = DvcBackend(middlewares=["prometheus"])
        with backend as executor:
            results = executor.execute_step(ManualMarkdownStep, set(), output_path)

        assert len(results) == 1

    def test_backend_supports_dont_encapsulate_parameter(self, tmp_path, env):
        """Verify backends accept dont_encapsulate parameter."""
        env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(tmp_path))
        output_path = tmp_path / "output"

        # Test that backend can be initialized with dont_encapsulate parameter
        backend = DvcBackend(dont_encapsulate=True)
        assert isinstance(backend, DvcBackend)

        # Test with encapsulation (default behavior)
        backend2 = DvcBackend(dont_encapsulate=False)
        with backend2 as executor:
            results = executor.execute_step(ManualMarkdownStep, set(), output_path)

        assert len(results) == 1
        assert output_path.exists()


class TestBackendArtifactGeneration:
    """Test that backends generate artifacts with self-referencing CLI calls."""

    @pytest.mark.parametrize(
        "backend_class,backend_name,expected_patterns",
        [
            pytest.param(
                DvcBackend,
                "DvcBackend",
                ["-e DvcBackend", "wurzel run"],
                id="DvcBackend",
            ),
            pytest.param(
                get_argo_backend(),
                "ArgoBackend",
                ["ArgoBackend", "- wurzel", "- run"],
                marks=pytest.mark.skipif(not HAS_HERA, reason="Hera is not available"),
                id="ArgoBackend",
            ),
        ],
    )
    def test_backend_generates_self_referencing_cli(self, backend_class, backend_name, expected_patterns):
        """Verify backends generate CLI calls with self-reference."""
        # Skip if backend_class is None (Hera not available)
        if backend_class is None:
            pytest.skip("Backend not available")

        step = WZ(ManualMarkdownStep)
        backend = backend_class()
        yaml_output = backend.generate_artifact(step)

        for pattern in expected_patterns:
            assert pattern in yaml_output, f"Expected '{pattern}' in output for {backend_name}"

    def test_generate_cli_call_with_backend_parameter(self, tmp_path):
        """Verify generate_cli_call accepts backend parameter."""
        output_path = tmp_path / "output"

        # Test with backend parameter
        cli_call = generate_cli_call(
            ManualMarkdownStep,
            inputs=[],
            output=output_path,
            backend=DvcBackend,
        )

        assert "-e DvcBackend" in cli_call
        assert str(output_path) in cli_call

    def test_generate_cli_call_backward_compatibility(self, tmp_path):
        """Verify generate_cli_call maintains backward compatibility with executor parameter."""
        output_path = tmp_path / "output"

        # Test with old executor parameter
        cli_call = generate_cli_call(
            ManualMarkdownStep,
            inputs=[],
            output=output_path,
            executor=BaseStepExecutor,
        )

        assert "-e BaseStepExecutor" in cli_call


class TestCLIIntegration:
    """Test CLI integration with backends."""

    @pytest.mark.parametrize(
        "backend_name,backend_class",
        [
            pytest.param("DvcBackend", DvcBackend, id="DvcBackend-full"),
            pytest.param("Dvc", DvcBackend, id="DvcBackend-partial"),
            pytest.param(
                "ArgoBackend",
                get_argo_backend(),
                marks=pytest.mark.skipif(not HAS_HERA, reason="Hera is not available"),
                id="ArgoBackend-full",
            ),
            pytest.param(
                "Argo",
                get_argo_backend(),
                marks=pytest.mark.skipif(not HAS_HERA, reason="Hera is not available"),
                id="ArgoBackend-partial",
            ),
        ],
    )
    def test_cli_recognizes_backend(self, backend_name, backend_class):
        """Verify CLI can parse backend names (full and partial)."""
        from wurzel.cli._main import executer_callback

        class FakeCtx:
            pass

        class FakeParam:
            pass

        # Skip if backend_class is None (Hera not available)
        if backend_class is None:
            pytest.skip("Backend not available")

        result = executer_callback(FakeCtx(), FakeParam(), backend_name)
        assert result == backend_class

    def test_cli_run_with_backend(self, tmp_path, env):
        """Verify CLI run command works with backend as executor."""
        env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(tmp_path))
        output_path = tmp_path / "output"

        cmd = [
            "wurzel",
            "run",
            "wurzel.steps.manual_markdown:ManualMarkdownStep",
            "-o",
            str(output_path),
            "-e",
            "DvcBackend",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert output_path.exists()


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    @pytest.mark.parametrize(
        "backend_class,backend_name,yaml_checks",
        [
            pytest.param(
                DvcBackend,
                "DvcBackend",
                {
                    "stages_key": "stages",
                    "step_key": "ManualMarkdownStep",
                    "cmd_patterns": ["-e DvcBackend", "wurzel run"],
                },
                id="DvcBackend",
            ),
            pytest.param(
                get_argo_backend(),
                "ArgoBackend",
                {
                    "spec_key": "spec",
                    "workflow_key": "workflowSpec",
                    "backend_pattern": "ArgoBackend",
                },
                marks=pytest.mark.skipif(not HAS_HERA, reason="Hera is not available"),
                id="ArgoBackend",
            ),
        ],
    )
    def test_generate_and_verify_pipeline(self, backend_class, backend_name, yaml_checks, tmp_path, env):
        """Test generating a pipeline and verifying it uses the backend."""
        # Skip if backend_class is None (Hera not available)
        if backend_class is None:
            pytest.skip("Backend not available")

        env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(tmp_path))

        # Generate pipeline
        step = WZ(ManualMarkdownStep)
        backend = backend_class()
        yaml_output = backend.generate_artifact(step)

        # Parse the YAML
        parsed = yaml.safe_load(yaml_output)

        # Verify structure based on backend type
        if "stages_key" in yaml_checks:
            # DVC-style checks
            assert yaml_checks["stages_key"] in parsed
            assert yaml_checks["step_key"] in parsed[yaml_checks["stages_key"]]
            cmd = parsed[yaml_checks["stages_key"]][yaml_checks["step_key"]]["cmd"]
            for pattern in yaml_checks["cmd_patterns"]:
                assert pattern in cmd
        elif "spec_key" in yaml_checks:
            # Argo-style checks
            assert yaml_checks["spec_key"] in parsed
            assert yaml_checks["workflow_key"] in parsed[yaml_checks["spec_key"]]
            assert yaml_checks["backend_pattern"] in str(yaml_output)

    @pytest.mark.parametrize(
        "backend_class",
        [
            pytest.param(DvcBackend, id="DvcBackend"),
            pytest.param(
                get_argo_backend(),
                marks=pytest.mark.skipif(not HAS_HERA, reason="Hera is not available"),
                id="ArgoBackend",
            ),
        ],
    )
    def test_backend_can_execute_and_generate(self, backend_class, tmp_path, env):
        """Verify a backend can both execute steps and generate artifacts."""
        # Skip if backend_class is None (Hera not available)
        if backend_class is None:
            pytest.skip("Backend not available")

        env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(tmp_path))
        output_path = tmp_path / "output"

        backend = backend_class()

        # 1. Execute a step
        with backend as executor:
            results = executor.execute_step(ManualMarkdownStep, set(), output_path)
        assert len(results) == 1
        assert output_path.exists()

        # 2. Generate artifact
        step = WZ(ManualMarkdownStep)
        yaml_output = backend.generate_artifact(step)
        assert backend_class.__name__ in yaml_output

        # Verify both operations used the same backend instance
        assert isinstance(backend, backend_class)
        assert isinstance(backend, BaseStepExecutor)
        assert isinstance(backend, Backend)


class TestBackendSettings:
    """Test backend-specific settings work correctly."""

    @pytest.mark.parametrize(
        "backend_class,settings_class,settings_kwargs,expected_values",
        [
            pytest.param(
                DvcBackend,
                lambda: __import__("wurzel.backend.backend_dvc", fromlist=["DvcBackendSettings"]).DvcBackendSettings,
                lambda tmp_path: {"DATA_DIR": tmp_path, "ENCAPSULATE_ENV": False},
                lambda tmp_path, backend: {
                    "DATA_DIR": (backend.settings.DATA_DIR, tmp_path),
                    "ENCAPSULATE_ENV": (backend.settings.ENCAPSULATE_ENV, False),
                },
                id="DvcBackend",
            ),
            pytest.param(
                get_argo_backend(),
                lambda: __import__("wurzel.backend.backend_argo", fromlist=["ArgoBackendSettings"]).ArgoBackendSettings,
                lambda tmp_path: {"IMAGE": "custom/image:latest", "NAMESPACE": "test-ns"},
                lambda tmp_path, backend: {
                    "IMAGE": (backend.settings.IMAGE, "custom/image:latest"),
                    "NAMESPACE": (backend.settings.NAMESPACE, "test-ns"),
                },
                marks=pytest.mark.skipif(not HAS_HERA, reason="Hera is not available"),
                id="ArgoBackend",
            ),
        ],
    )
    def test_backend_settings(self, backend_class, settings_class, settings_kwargs, expected_values, tmp_path):
        """Verify backends respect their settings."""
        # Skip if backend_class is None (Hera not available)
        if backend_class is None:
            pytest.skip("Backend not available")

        # Handle lazy imports
        if callable(settings_class):
            settings_class = settings_class()

        # Create settings with kwargs
        kwargs = settings_kwargs(tmp_path)
        settings = settings_class(**kwargs)
        backend = backend_class(settings=settings)

        # Verify expected values
        expected = expected_values(tmp_path, backend)
        for key, (actual, expected_val) in expected.items():
            assert actual == expected_val, f"Expected {key}={expected_val}, got {actual}"


class TestBackendContextManager:
    """Test backend context manager functionality."""

    @pytest.mark.parametrize(
        "backend_class,middlewares",
        [
            pytest.param(DvcBackend, None, id="DvcBackend-no-middleware"),
            pytest.param(DvcBackend, ["prometheus"], id="DvcBackend-with-middleware"),
            pytest.param(
                get_argo_backend(),
                None,
                marks=pytest.mark.skipif(not HAS_HERA, reason="Hera is not available"),
                id="ArgoBackend-no-middleware",
            ),
            pytest.param(
                get_argo_backend(),
                ["prometheus"],
                marks=pytest.mark.skipif(not HAS_HERA, reason="Hera is not available"),
                id="ArgoBackend-with-middleware",
            ),
        ],
    )
    def test_backend_context_manager(self, backend_class, middlewares, tmp_path, env):
        """Verify backends work as context managers with and without middlewares."""
        # Skip if backend_class is None (Hera not available)
        if backend_class is None:
            pytest.skip("Backend not available")

        env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(tmp_path))
        output_path = tmp_path / "output"

        # Use backend as context manager
        backend_kwargs = {"middlewares": middlewares} if middlewares else {}
        with backend_class(**backend_kwargs) as backend:
            assert isinstance(backend, backend_class)
            results = backend.execute_step(ManualMarkdownStep, set(), output_path)
            assert len(results) == 1
