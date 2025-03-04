# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest
from wurzel.step_executor import PrometheusStepExecutor

def test_create_metrics():
    executor = PrometheusStepExecutor()
    assert executor.counter_failed
def test_context_manager():
    with PrometheusStepExecutor() as exc:
        assert exc.counter_failed
def test_context_manager_singelton():
    with PrometheusStepExecutor() as exc:
        with PrometheusStepExecutor() as exc2:
            assert exc == exc2