# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace
from typing import Any, Optional

from wurzel.executors.middlewares.prometheus import PrometheusMiddleware


class DummyReport(SimpleNamespace):
    pass


class DummyStep:
    __name__ = "DummyStep"


def test_prometheus_middleware_happy_path() -> None:
    # call_next returns list of (result, report)
    report = DummyReport(results=1, inputs=2, time_to_save=0.1, time_to_load=0.2, time_to_execute=0.3)

    def call_next(step_cls: type, inputs: Optional[set], output_dir: Optional[Any]):
        return [(None, report)]

    m = PrometheusMiddleware()
    data = m(call_next, DummyStep, set(), None)
    assert data[0][1] is report


def test_prometheus_middleware_exception_path() -> None:
    def call_next(step_cls: type, inputs: Optional[set], output_dir: Optional[Any]):
        raise RuntimeError("boom")

    m = PrometheusMiddleware()
    try:
        m(call_next, DummyStep, set(), None)
        assert False, "should have raised"
    except RuntimeError:
        # expected
        pass
