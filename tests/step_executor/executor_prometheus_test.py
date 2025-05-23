# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


from wurzel.datacontract.common import MarkdownDataContract
from wurzel.step.typed_step import TypedStep
from wurzel.step_executor import PrometheusStepExecutor

class DummyStep(TypedStep[None, None, MarkdownDataContract]):
    def run(self, inpt: None) -> MarkdownDataContract:
        return MarkdownDataContract(md="md", keywords="", url="")

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
def test_setting_of_counters():
    with PrometheusStepExecutor() as exc:
        exc(DummyStep, None, None)
        assert exc.counter_results.collect()[0].samples[0].value == 1.0
        exc(DummyStep, None, None)
        assert exc.counter_results.collect()[0].samples[0].value == 2.0