# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import pytest

from wurzel.executors.middlewares.prometheus import PrometheusMiddleware

from .conftest import DummyStep


def test_prometheus_middleware_happy_path(dummy_report, make_call_next) -> None:
    m = PrometheusMiddleware()
    data = m(make_call_next(dummy_report), DummyStep, set(), None)
    assert data[0][1] is dummy_report


def test_prometheus_middleware_exception_path() -> None:
    def call_next(step_cls: type, inputs: set | None, output_dir: Any | None):
        raise RuntimeError("boom")

    m = PrometheusMiddleware()
    with pytest.raises(RuntimeError, match="boom"):
        m(call_next, DummyStep, set(), None)


@pytest.mark.parametrize(
    "run_id,expected_label",
    [
        pytest.param("test-run-12345", "test-run-12345", id="explicit_run_id"),
        pytest.param(None, "unknown", id="defaults_to_unknown"),
    ],
)
def test_prometheus_middleware_run_id_in_counter_started(monkeypatch, dummy_report, make_call_next, run_id, expected_label) -> None:
    """Test that counter_started uses WURZEL_RUN_ID (or 'unknown' when absent)."""
    if run_id is None:
        monkeypatch.delenv("WURZEL_RUN_ID", raising=False)
    else:
        monkeypatch.setenv("WURZEL_RUN_ID", run_id)

    m = PrometheusMiddleware()
    m(make_call_next(dummy_report), DummyStep, set(), None)

    metric_samples = list(m.counter_started.collect())[0].samples
    assert any(sample.labels.get("run_id") == expected_label for sample in metric_samples)


def test_prometheus_middleware_run_id_in_all_metrics(monkeypatch, dummy_report, make_call_next) -> None:
    """Test that run_id label is present in all counter and histogram metric types."""
    test_run_id = "comprehensive-test-67890"
    monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

    m = PrometheusMiddleware()
    m(make_call_next(dummy_report), DummyStep, set(), None)

    for counter in [m.counter_started, m.counter_results, m.counter_inputs]:
        samples = list(counter.collect())[0].samples
        assert any(sample.labels.get("run_id") == test_run_id for sample in samples), f"run_id not found in {counter._name}"

    for histogram in [m.histogram_save, m.histogram_load, m.histogram_execute]:
        samples = list(histogram.collect())[0].samples
        assert any(sample.labels.get("run_id") == test_run_id for sample in samples), f"run_id not found in {histogram._name}"


def test_prometheus_middleware_run_id_on_failure(monkeypatch) -> None:
    """Test that run_id is recorded even when step execution fails."""
    test_run_id = "failure-test-999"
    monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

    def call_next(step_cls: type, inputs: set | None, output_dir: Any | None):
        raise RuntimeError("intentional failure")

    m = PrometheusMiddleware()
    with pytest.raises(RuntimeError):
        m(call_next, DummyStep, set(), None)

    metric_samples = list(m.counter_failed.collect())[0].samples
    assert any(sample.labels.get("run_id") == test_run_id for sample in metric_samples)


def test_prometheus_middleware_different_run_ids_create_separate_metrics(monkeypatch, dummy_report, make_call_next) -> None:
    """Test that different run_ids create separate metric series."""
    m = PrometheusMiddleware()

    monkeypatch.setenv("WURZEL_RUN_ID", "run-1")
    m(make_call_next(dummy_report), DummyStep, set(), None)

    monkeypatch.setenv("WURZEL_RUN_ID", "run-2")
    m(make_call_next(dummy_report), DummyStep, set(), None)

    metric_samples = list(m.counter_started.collect())[0].samples
    run_ids = {sample.labels.get("run_id") for sample in metric_samples}
    assert "run-1" in run_ids
    assert "run-2" in run_ids


def test_prometheus_middleware_run_id_with_step_name_label(monkeypatch, dummy_report, make_call_next) -> None:
    """Test that run_id and step_name labels are both present together."""
    test_run_id = "label-combo-test"
    monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

    m = PrometheusMiddleware()
    m(make_call_next(dummy_report), DummyStep, set(), None)

    metric_samples = list(m.counter_started.collect())[0].samples
    matching_samples = [
        sample for sample in metric_samples if sample.labels.get("run_id") == test_run_id and sample.labels.get("step_name") == "DummyStep"
    ]
    assert len(matching_samples) > 0, "Expected to find metrics with both run_id and step_name labels"


def test_prometheus_middleware_datacontract_metrics(monkeypatch, make_call_next) -> None:
    from types import SimpleNamespace  # noqa: PLC0415

    test_run_id = "metrics-test-123"
    monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

    report_with_metrics = SimpleNamespace(
        results=1,
        inputs=1,
        time_to_save=0.1,
        time_to_load=0.1,
        time_to_execute=0.1,
        metrics={"md_char_len": 5.0},
    )

    m = PrometheusMiddleware()
    m(make_call_next(report_with_metrics), DummyStep, set(), None)

    metric_samples = list(m.gauge_contract_metrics.collect())[0].samples
    matches = [
        sample
        for sample in metric_samples
        if sample.name == "step_datacontract_metric"
        and sample.labels.get("metric_name") == "md_char_len"
        and sample.labels.get("step_name") == "DummyStep"
        and sample.labels.get("run_id") == test_run_id
    ]
    assert len(matches) == 1
    assert matches[0].value == 5.0
