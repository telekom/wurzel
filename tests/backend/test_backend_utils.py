# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend utility functions and backend discovery."""

import pytest

from wurzel.executors.backend import (
    Backend,
    DvcBackend,
    get_all_backends,
    get_available_backends,
    get_backend_by_name,
)
from wurzel.utils import HAS_HERA


class TestGetAllBackends:
    def test_returns_dict_with_dvc_backend(self):
        """Test that get_all_backends always includes DvcBackend."""
        backends = get_all_backends()
        assert isinstance(backends, dict)
        assert "DvcBackend" in backends
        assert backends["DvcBackend"] == DvcBackend

    def test_includes_argo_backend_when_hera_available(self):
        """Test that ArgoBackend is included when Hera is available."""
        backends = get_all_backends()
        if HAS_HERA:
            from wurzel.executors.backend import ArgoBackend

            assert "ArgoBackend" in backends
            assert backends["ArgoBackend"] == ArgoBackend
        else:
            assert "ArgoBackend" not in backends

    def test_returns_new_dict_each_call(self):
        """Test that get_all_backends returns a new dict each time."""
        backends1 = get_all_backends()
        backends2 = get_all_backends()
        assert backends1 is not backends2
        assert backends1 == backends2


class TestGetAvailableBackends:
    def test_returns_only_available_backends(self):
        """Test that get_available_backends filters by availability."""
        available = get_available_backends()
        assert isinstance(available, dict)
        # All returned backends should be available
        for name, backend_cls in available.items():
            assert backend_cls.is_available() is True

    def test_dvc_backend_always_available(self):
        """Test that DvcBackend is always in available backends."""
        available = get_available_backends()
        assert "DvcBackend" in available
        assert available["DvcBackend"] == DvcBackend

    def test_subset_of_all_backends(self):
        """Test that available backends is a subset of all backends."""
        all_backends = get_all_backends()
        available = get_available_backends()
        assert set(available.keys()).issubset(set(all_backends.keys()))


class TestGetBackendByName:
    def test_get_dvc_backend_by_exact_name(self):
        """Test getting DvcBackend by exact name."""
        backend = get_backend_by_name("DvcBackend")
        assert backend == DvcBackend

    def test_get_backend_case_insensitive(self):
        """Test that backend lookup is case-insensitive."""
        backend_lower = get_backend_by_name("dvcbackend")
        backend_upper = get_backend_by_name("DVCBACKEND")
        backend_mixed = get_backend_by_name("DvCbAcKeNd")

        assert backend_lower == DvcBackend
        assert backend_upper == DvcBackend
        assert backend_mixed == DvcBackend

    def test_get_nonexistent_backend_returns_none(self):
        """Test that requesting a non-existent backend returns None."""
        backend = get_backend_by_name("NonExistentBackend")
        assert backend is None

    def test_get_backend_with_empty_string(self):
        """Test that empty string returns None."""
        backend = get_backend_by_name("")
        assert backend is None

    def test_get_backend_with_whitespace(self):
        """Test that whitespace-only string returns None."""
        backend = get_backend_by_name("   ")
        assert backend is None

    @pytest.mark.skipif(not HAS_HERA, reason="Hera not available")
    def test_get_argo_backend_by_name(self):
        """Test getting ArgoBackend by name when Hera is available."""
        from wurzel.executors.backend import ArgoBackend

        backend = get_backend_by_name("ArgoBackend")
        assert backend == ArgoBackend

        backend_lower = get_backend_by_name("argobackend")
        assert backend_lower == ArgoBackend


class TestBackendBaseClass:
    def test_backend_is_abstract_base(self):
        """Test that Backend is an abstract base class."""
        assert issubclass(DvcBackend, Backend)

    def test_backend_has_is_available_method(self):
        """Test that Backend has is_available class method."""
        assert hasattr(Backend, "is_available")
        assert callable(Backend.is_available)

    def test_backend_has_generate_artifact_method(self):
        """Test that Backend has generate_artifact method."""
        assert hasattr(Backend, "generate_artifact")

    def test_backend_is_available_returns_true_by_default(self):
        """Test that Backend.is_available returns True by default."""
        assert Backend.is_available() is True

    def test_backend_generate_artifact_raises_not_implemented(self):
        """Test that Backend.generate_artifact raises NotImplementedError."""
        from wurzel.core import NoSettings, TypedStep
        from wurzel.datacontract.common import MarkdownDataContract

        class DummyStep(TypedStep[NoSettings, None, MarkdownDataContract]):
            def run(self, inpt: None) -> MarkdownDataContract:
                return MarkdownDataContract(content="test")

        backend = Backend()
        step = DummyStep()

        with pytest.raises(NotImplementedError):
            backend.generate_artifact(step)


class TestBackendInitialization:
    def test_backend_accepts_dont_encapsulate_parameter(self):
        """Test that Backend accepts dont_encapsulate parameter."""
        backend = Backend(dont_encapsulate=True)
        assert backend is not None

    def test_backend_accepts_middlewares_parameter(self):
        """Test that Backend accepts middlewares parameter."""
        backend = Backend(middlewares=["prometheus"])
        assert backend is not None

    def test_backend_accepts_load_middlewares_from_env_parameter(self):
        """Test that Backend accepts load_middlewares_from_env parameter."""
        backend = Backend(load_middlewares_from_env=True)
        assert backend is not None

    def test_backend_accepts_executor_parameter(self):
        """Test that Backend accepts executor parameter."""
        from wurzel.executors.base_executor import BaseStepExecutor

        backend = Backend(executer=BaseStepExecutor)
        assert backend.executor == BaseStepExecutor

    def test_backend_executor_defaults_to_none(self):
        """Test that Backend.executor defaults to None."""
        backend = Backend()
        assert backend.executor is None
