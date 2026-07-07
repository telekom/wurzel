# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace
from typing import Any

import pytest

from wurzel.executors.middlewares.prometheus import PrometheusMiddleware


class DummyReport(SimpleNamespace):
    pass


class DummyStep:
    __name__ = "DummyStep"


def _set_wurzel_context(monkeypatch) -> None:
    monkeypatch.setenv("WURZEL_RUN_ID", "argo-run-uid")
    monkeypatch.setenv("WURZEL_WORKFLOW_NAME", "steps-austria-dev")


def _call_successfully(middleware: PrometheusMiddleware, reports: list[DummyReport]) -> list[tuple[Any, Any]]:
    def call_next(step_cls: type, inputs: set | None, output_dir: Any | None):
        return [(None, report) for report in reports]

    return middleware(call_next, DummyStep, set(), None)


def _metric_samples(collector, sample_name: str):
    return [sample for sample in list(collector.collect())[0].samples if sample.name == sample_name]


def _sample_by_labels(collector, sample_name: str, **labels: str):
    for sample in _metric_samples(collector, sample_name):
        if all(sample.labels.get(name) == value for name, value in labels.items()):
            return sample
    raise AssertionError(f"No sample {sample_name} found with labels {labels}")


def test_prometheus_middleware_happy_path() -> None:
    report = DummyReport(results=1, inputs=2, time_to_save=0.1, time_to_load=0.2, time_to_execute=0.3)

    m = PrometheusMiddleware()
    data = _call_successfully(m, [report])

    assert data[0][1] is report


def test_prometheus_middleware_exception_path() -> None:
    def call_next(step_cls: type, inputs: set | None, output_dir: Any | None):
        raise RuntimeError("boom")

    m = PrometheusMiddleware()
    with pytest.raises(RuntimeError):
        m(call_next, DummyStep, set(), None)


def test_prometheus_middleware_emits_observability_labels(monkeypatch) -> None:
    _set_wurzel_context(monkeypatch)
    report = DummyReport(results=1, inputs=2, time_to_save=0.1, time_to_load=0.2, time_to_execute=0.3)

    m = PrometheusMiddleware()
    _call_successfully(m, [report])

    sample = _sample_by_labels(m.gauge_step_info, "wurzel_step_info", step_name="DummyStep")
    assert sample.value == 1
    assert sample.labels["run_id"] == "argo-run-uid"
    assert sample.labels["workflow_name"] == "steps-austria-dev"
    assert set(sample.labels) == {"step_name", "run_id", "workflow_name"}


def test_prometheus_middleware_emits_input_and_result_gauges(monkeypatch) -> None:
    _set_wurzel_context(monkeypatch)
    reports = [
        DummyReport(results=3, inputs=4, time_to_save=0.1, time_to_load=0.2, time_to_execute=0.3),
        DummyReport(results=2, inputs=5, time_to_save=0.4, time_to_load=0.5, time_to_execute=0.6),
    ]

    m = PrometheusMiddleware()
    _call_successfully(m, reports)

    assert _sample_by_labels(m.gauge_step_input_items, "wurzel_step_input_items", step_name="DummyStep").value == 9
    assert _sample_by_labels(m.gauge_step_result_items, "wurzel_step_result_items", step_name="DummyStep").value == 5


def test_prometheus_middleware_emits_duration_gauges(monkeypatch) -> None:
    _set_wurzel_context(monkeypatch)
    reports = [
        DummyReport(results=1, inputs=1, time_to_save=0.1, time_to_load=0.2, time_to_execute=0.3),
        DummyReport(results=1, inputs=1, time_to_save=0.4, time_to_load=0.5, time_to_execute=0.6),
    ]

    m = PrometheusMiddleware()
    _call_successfully(m, reports)

    assert _sample_by_labels(m.gauge_step_duration_seconds, "wurzel_step_duration_seconds", phase="load").value == pytest.approx(0.7)
    assert _sample_by_labels(m.gauge_step_duration_seconds, "wurzel_step_duration_seconds", phase="execute").value == pytest.approx(0.9)
    assert _sample_by_labels(m.gauge_step_duration_seconds, "wurzel_step_duration_seconds", phase="save").value == pytest.approx(0.5)
    assert _sample_by_labels(m.gauge_step_duration_seconds, "wurzel_step_duration_seconds", phase="total").value == pytest.approx(2.1)


def test_prometheus_middleware_emits_success_status_and_timestamps(monkeypatch) -> None:
    _set_wurzel_context(monkeypatch)
    report = DummyReport(results=1, inputs=1, time_to_save=0.1, time_to_load=0.2, time_to_execute=0.3)

    m = PrometheusMiddleware()
    _call_successfully(m, [report])

    assert _sample_by_labels(m.gauge_step_status, "wurzel_step_status", status="started").value == 0
    assert _sample_by_labels(m.gauge_step_status, "wurzel_step_status", status="succeeded").value == 1
    assert _sample_by_labels(m.gauge_step_status, "wurzel_step_status", status="failed").value == 0
    started = _sample_by_labels(m.gauge_step_timestamp_seconds, "wurzel_step_timestamp_seconds", event="started").value
    completed = _sample_by_labels(m.gauge_step_timestamp_seconds, "wurzel_step_timestamp_seconds", event="completed").value
    assert started > 0
    assert completed >= started


def test_prometheus_middleware_emits_failed_status_and_timestamp(monkeypatch) -> None:
    _set_wurzel_context(monkeypatch)

    def call_next(step_cls: type, inputs: set | None, output_dir: Any | None):
        raise RuntimeError("intentional failure")

    m = PrometheusMiddleware()
    with pytest.raises(RuntimeError):
        m(call_next, DummyStep, set(), None)

    assert _sample_by_labels(m.gauge_step_status, "wurzel_step_status", status="started").value == 0
    assert _sample_by_labels(m.gauge_step_status, "wurzel_step_status", status="succeeded").value == 0
    assert _sample_by_labels(m.gauge_step_status, "wurzel_step_status", status="failed").value == 1
    started = _sample_by_labels(m.gauge_step_timestamp_seconds, "wurzel_step_timestamp_seconds", event="started").value
    failed = _sample_by_labels(m.gauge_step_timestamp_seconds, "wurzel_step_timestamp_seconds", event="failed").value
    assert started > 0
    assert failed >= started


def test_prometheus_middleware_emits_datacontract_metrics(monkeypatch) -> None:
    _set_wurzel_context(monkeypatch)
    report = DummyReport(
        results=1,
        inputs=1,
        time_to_save=0.1,
        time_to_load=0.2,
        time_to_execute=0.3,
        metrics={"md_char_len": 5.0},
    )

    m = PrometheusMiddleware()
    _call_successfully(m, [report])

    sample = _sample_by_labels(
        m.gauge_step_datacontract_metric,
        "wurzel_step_datacontract_metric",
        step_name="DummyStep",
        metric_name="md_char_len",
    )
    assert sample.value == 5.0
    assert sample.labels["run_id"] == "argo-run-uid"
    assert sample.labels["workflow_name"] == "steps-austria-dev"
    assert set(sample.labels) == {"step_name", "run_id", "workflow_name", "metric_name"}


def test_prometheus_middleware_context_defaults_to_unknown(monkeypatch) -> None:
    monkeypatch.delenv("WURZEL_RUN_ID", raising=False)
    monkeypatch.delenv("WURZEL_WORKFLOW_NAME", raising=False)
    report = DummyReport(results=1, inputs=1, time_to_save=0.1, time_to_load=0.2, time_to_execute=0.3)

    m = PrometheusMiddleware()
    _call_successfully(m, [report])

    sample = _sample_by_labels(m.gauge_step_info, "wurzel_step_info", step_name="DummyStep")
    assert sample.labels["run_id"] == "unknown"
    assert sample.labels["workflow_name"] == "unknown"
    assert set(sample.labels) == {"step_name", "run_id", "workflow_name"}
