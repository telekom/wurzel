# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace
from typing import Any, Optional

import pytest

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


def test_prometheus_middleware_uses_run_id_from_environment(monkeypatch) -> None:
    """Test that Prometheus middleware uses WURZEL_RUN_ID as a metric label."""
    test_run_id = "test-run-12345"
    monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

    report = DummyReport(results=1, inputs=2, time_to_save=0.1, time_to_load=0.2, time_to_execute=0.3)

    def call_next(step_cls: type, inputs: Optional[set], output_dir: Optional[Any]):
        return [(None, report)]

    m = PrometheusMiddleware()
    m(call_next, DummyStep, set(), None)

    # Verify that metrics have the run_id label
    # Check counter_started metric
    metric_samples = list(m.counter_started.collect())[0].samples
    assert any(sample.labels.get("run_id") == test_run_id for sample in metric_samples)


def test_prometheus_middleware_run_id_defaults_to_unknown(monkeypatch) -> None:
    """Test that run_id defaults to 'unknown' when WURZEL_RUN_ID is not set."""
    monkeypatch.delenv("WURZEL_RUN_ID", raising=False)

    report = DummyReport(results=1, inputs=2, time_to_save=0.1, time_to_load=0.2, time_to_execute=0.3)

    def call_next(step_cls: type, inputs: Optional[set], output_dir: Optional[Any]):
        return [(None, report)]

    m = PrometheusMiddleware()
    m(call_next, DummyStep, set(), None)

    # Verify that metrics have run_id='unknown'
    metric_samples = list(m.counter_started.collect())[0].samples
    assert any(sample.labels.get("run_id") == "unknown" for sample in metric_samples)


def test_prometheus_middleware_run_id_in_all_metrics(monkeypatch) -> None:
    """Test that run_id label is present in all metric types."""
    test_run_id = "comprehensive-test-67890"
    monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

    report = DummyReport(results=5, inputs=3, time_to_save=0.5, time_to_load=0.3, time_to_execute=0.7)

    def call_next(step_cls: type, inputs: Optional[set], output_dir: Optional[Any]):
        return [(None, report)]

    m = PrometheusMiddleware()
    m(call_next, DummyStep, set(), None)

    # Check all counters
    for counter in [m.counter_started, m.counter_results, m.counter_inputs]:
        samples = list(counter.collect())[0].samples
        assert any(sample.labels.get("run_id") == test_run_id for sample in samples), f"run_id not found in {counter._name}"

    # Check all histograms
    for histogram in [m.histogram_save, m.histogram_load, m.histogram_execute]:
        samples = list(histogram.collect())[0].samples
        assert any(sample.labels.get("run_id") == test_run_id for sample in samples), f"run_id not found in {histogram._name}"


def test_prometheus_middleware_run_id_on_failure(monkeypatch) -> None:
    """Test that run_id is recorded even when step execution fails."""
    test_run_id = "failure-test-999"
    monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

    def call_next(step_cls: type, inputs: Optional[set], output_dir: Optional[Any]):
        raise RuntimeError("intentional failure")

    m = PrometheusMiddleware()

    with pytest.raises(RuntimeError):
        m(call_next, DummyStep, set(), None)

    # Verify that counter_failed has the run_id label
    metric_samples = list(m.counter_failed.collect())[0].samples
    assert any(sample.labels.get("run_id") == test_run_id for sample in metric_samples)


def test_prometheus_middleware_different_run_ids_create_separate_metrics(monkeypatch) -> None:
    """Test that different run_ids create separate metric series."""
    report = DummyReport(results=1, inputs=1, time_to_save=0.1, time_to_load=0.1, time_to_execute=0.1)

    def call_next(step_cls: type, inputs: Optional[set], output_dir: Optional[Any]):
        return [(None, report)]

    m = PrometheusMiddleware()

    # Execute with first run_id
    monkeypatch.setenv("WURZEL_RUN_ID", "run-1")
    m(call_next, DummyStep, set(), None)

    # Execute with second run_id
    monkeypatch.setenv("WURZEL_RUN_ID", "run-2")
    m(call_next, DummyStep, set(), None)

    # Verify both run_ids are present in metrics
    metric_samples = list(m.counter_started.collect())[0].samples
    run_ids = {sample.labels.get("run_id") for sample in metric_samples}
    assert "run-1" in run_ids
    assert "run-2" in run_ids


def test_prometheus_middleware_run_id_with_step_name_label(monkeypatch) -> None:
    """Test that run_id and step_name labels work together."""
    test_run_id = "label-combo-test"
    monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

    report = DummyReport(results=1, inputs=1, time_to_save=0.1, time_to_load=0.1, time_to_execute=0.1)

    def call_next(step_cls: type, inputs: Optional[set], output_dir: Optional[Any]):
        return [(None, report)]

    m = PrometheusMiddleware()
    m(call_next, DummyStep, set(), None)

    # Verify both labels are present
    metric_samples = list(m.counter_started.collect())[0].samples
    matching_samples = [
        sample for sample in metric_samples if sample.labels.get("run_id") == test_run_id and sample.labels.get("step_name") == "DummyStep"
    ]
    assert len(matching_samples) > 0, "Expected to find metrics with both run_id and step_name labels"


def test_prometheus_middleware_datacontract_metrics(monkeypatch) -> None:
    test_run_id = "metrics-test-123"
    monkeypatch.setenv("WURZEL_RUN_ID", test_run_id)

    report = DummyReport(
        results=1,
        inputs=1,
        time_to_save=0.1,
        time_to_load=0.1,
        time_to_execute=0.1,
        metrics={"md_char_len": 5.0},
    )

    def call_next(step_cls: type, inputs: Optional[set], output_dir: Optional[Any]):
        return [(None, report)]

    m = PrometheusMiddleware()
    m(call_next, DummyStep, set(), None)

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
