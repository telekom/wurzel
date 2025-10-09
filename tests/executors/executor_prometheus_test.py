# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for deprecated PrometheusStepExecutor.

Note: PrometheusStepExecutor is deprecated. These tests verify backward compatibility.
For new tests, see middleware_test.py
"""

import pytest

from wurzel.core.typed_step import TypedStep
from wurzel.datacontract.common import MarkdownDataContract
from wurzel.executors import PrometheusStepExecutor


class DummyStep(TypedStep[None, None, MarkdownDataContract]):
    def run(self, inpt: None) -> MarkdownDataContract:
        return MarkdownDataContract(md="md", keywords="", url="")


def test_create_metrics():
    """Test that PrometheusStepExecutor can be created (deprecated)."""
    with pytest.warns(DeprecationWarning):
        executor = PrometheusStepExecutor()
        # Just verify it's created, don't check internal attributes
        assert executor is not None


def test_context_manager():
    """Test that PrometheusStepExecutor works as context manager (deprecated)."""
    with pytest.warns(DeprecationWarning):
        with PrometheusStepExecutor() as exc:
            # Just verify context manager works
            assert exc is not None


def test_context_manager_singelton():
    """Test that PrometheusStepExecutor maintains singleton pattern (deprecated)."""
    with pytest.warns(DeprecationWarning):
        with PrometheusStepExecutor() as exc:
            with pytest.warns(DeprecationWarning):
                with PrometheusStepExecutor() as exc2:
                    # Singleton pattern should return same instance
                    assert exc == exc2


def test_execution_works():
    """Test that PrometheusStepExecutor can execute steps (deprecated)."""
    with pytest.warns(DeprecationWarning):
        with PrometheusStepExecutor() as exc:
            # Just verify execution works, don't check metrics
            result = exc(DummyStep, None, None)
            assert result is not None
            assert len(result) > 0
