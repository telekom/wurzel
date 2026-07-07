# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Prometheus metrics middleware for step execution."""

import os
import time
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from typing import Any

from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram, push_to_gateway

from wurzel.core.typed_step import TypedStep
from wurzel.path import PathToFolderWithBaseModels

from ..base import BaseMiddleware, ExecuteStepCallable
from .settings import PrometheusMiddlewareSettings

log = getLogger(__name__)

CONTEXT_LABELS = ("step_name", "run_id", "workflow_name", "workflow_namespace", "step_pod")
ARGO_TEMPLATE_SEPARATOR = "-wurzel-run-template-"
KUBERNETES_NAMESPACE_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")


@dataclass
class StepMetricTotals:
    """Aggregated metrics from one Wurzel step invocation."""

    results: float
    inputs: float
    time_to_save: float
    time_to_load: float
    time_to_execute: float
    contract_metrics: dict[str, float]


class PrometheusMiddleware(BaseMiddleware):  # pylint: disable=too-many-instance-attributes
    """Middleware that adds Prometheus metrics collection to step execution.

    This middleware collects metrics about step execution including:
    - Counter of steps started
    - Counter of steps failed
    - Counter of results produced
    - Counter of inputs processed
    - Histograms for load, execute, and save times
    - Gauges for stable per-step input, output, status, timestamp, and duration values

    All metrics include two labels:
    - step_name: The name of the step being executed
    - run_id: Unique identifier for the pipeline run (from WURZEL_RUN_ID env var)

    The run_id label allows grouping and filtering metrics by pipeline execution,
    making it easy to track all steps from a single run together.
    """

    def __init__(
        self,
        settings: PrometheusMiddlewareSettings | None = None,
        *,
        registry: CollectorRegistry | None = None,
    ):
        """Initialize the Prometheus middleware.

        Args:
            settings: Configuration for Prometheus metrics (gateway, job name, etc.)
        """
        super().__init__()
        self.settings = settings or PrometheusMiddlewareSettings()
        self.registry = registry or CollectorRegistry(auto_describe=True)
        self._setup_metrics()

    def _setup_metrics(self):
        """Set up Prometheus metrics collectors."""
        if self.settings.DISABLE_CREATED_METRIC:
            os.environ["PROMETHEUS_DISABLE_CREATED_SERIES"] = "True"

        # Add run_id as a label to all metrics for identifying pipeline runs
        self.counter_started = Counter(
            "steps_started", "Total number of TypedSteps started", ("step_name", "run_id"), registry=self.registry
        )
        self.counter_failed = Counter("steps_failed", "Total number of TypedSteps failed", ("step_name", "run_id"), registry=self.registry)
        self.counter_results = Counter(
            "step_results",
            "count of result, if its an array, otherwise -1",
            ("step_name", "run_id"),
            registry=self.registry,
        )
        self.counter_inputs = Counter("step_inputs", "count of inputs", ("step_name", "run_id"), registry=self.registry)
        self.histogram_save = Histogram("step_hist_save", "Time to save results", ("step_name", "run_id"), registry=self.registry)
        self.histogram_load = Histogram("step_hist_load", "Time to load inputs", ("step_name", "run_id"), registry=self.registry)
        self.histogram_execute = Histogram("step_hist_execute", "Time to execute results", ("step_name", "run_id"), registry=self.registry)
        self.gauge_contract_metrics = Gauge(
            "step_datacontract_metric",
            "Metrics reported by data contracts",
            ("metric_name", "step_name", "run_id"),
            registry=self.registry,
        )
        self.gauge_step_input_items = Gauge(
            "wurzel_step_input_items",
            "Number of input items processed by a Wurzel step",
            CONTEXT_LABELS,
            registry=self.registry,
        )
        self.gauge_step_result_items = Gauge(
            "wurzel_step_result_items",
            "Number of result items produced by a Wurzel step",
            CONTEXT_LABELS,
            registry=self.registry,
        )
        self.gauge_step_duration_seconds = Gauge(
            "wurzel_step_duration_seconds",
            "Duration of a Wurzel step phase in seconds",
            (*CONTEXT_LABELS, "phase"),
            registry=self.registry,
        )
        self.gauge_step_status = Gauge(
            "wurzel_step_status",
            "Status marker for a Wurzel step execution",
            (*CONTEXT_LABELS, "status"),
            registry=self.registry,
        )
        self.gauge_step_timestamp_seconds = Gauge(
            "wurzel_step_timestamp_seconds",
            "Unix timestamp for Wurzel step lifecycle events",
            (*CONTEXT_LABELS, "event"),
            registry=self.registry,
        )
        self.gauge_step_info = Gauge(
            "wurzel_step_info",
            "Static Wurzel step execution information",
            CONTEXT_LABELS,
            registry=self.registry,
        )

    @staticmethod
    def _read_workflow_namespace() -> str:
        try:
            namespace = KUBERNETES_NAMESPACE_PATH.read_text(encoding="utf-8").strip()
        except OSError:
            return "unknown"
        return namespace or "unknown"

    @staticmethod
    def _derive_workflow_name(step_pod: str) -> str:
        if ARGO_TEMPLATE_SEPARATOR not in step_pod:
            return "unknown"
        workflow_name = step_pod.split(ARGO_TEMPLATE_SEPARATOR, maxsplit=1)[0]
        return workflow_name or "unknown"

    def _context_labels(self, step_name: str) -> dict[str, str]:
        step_pod = os.environ.get("HOSTNAME") or "unknown"
        return {
            "step_name": step_name,
            "run_id": os.environ.get("WURZEL_RUN_ID", "unknown"),
            "workflow_name": self._derive_workflow_name(step_pod),
            "workflow_namespace": self._read_workflow_namespace(),
            "step_pod": step_pod,
        }

    def _set_step_status(self, context_labels: dict[str, str], status: str) -> None:
        for known_status in ("started", "succeeded", "failed"):
            self.gauge_step_status.labels(**context_labels, status=known_status).set(1 if known_status == status else 0)

    def _collect_report_metrics(self, data: list[tuple[Any, Any]], step_name: str, run_id: str) -> StepMetricTotals:
        total_results = 0.0
        total_inputs = 0.0
        tt_s, tt_l, tt_e = (0.0, 0.0, 0.0)
        contract_metrics: dict[str, float] = {}

        for _, report in data:
            self.counter_results.labels(step_name, run_id).inc(report.results)
            self.counter_inputs.labels(step_name, run_id).inc(report.inputs)
            total_results += report.results
            total_inputs += report.inputs
            tt_s += report.time_to_save
            tt_l += report.time_to_load
            tt_e += report.time_to_execute
            report_metrics = getattr(report, "metrics", None)
            if report_metrics:
                for name, value in report_metrics.items():
                    contract_metrics[name] = contract_metrics.get(name, 0.0) + float(value)

        return StepMetricTotals(
            results=total_results,
            inputs=total_inputs,
            time_to_save=tt_s,
            time_to_load=tt_l,
            time_to_execute=tt_e,
            contract_metrics=contract_metrics,
        )

    def _record_success_metrics(self, data: list[tuple[Any, Any]], step_name: str, run_id: str, context_labels: dict[str, str]) -> None:
        totals = self._collect_report_metrics(data, step_name, run_id)

        self.histogram_save.labels(step_name, run_id).observe(totals.time_to_save)
        self.histogram_load.labels(step_name, run_id).observe(totals.time_to_load)
        self.histogram_execute.labels(step_name, run_id).observe(totals.time_to_execute)
        for name, value in totals.contract_metrics.items():
            self.gauge_contract_metrics.labels(name, step_name, run_id).set(value)

        self.gauge_step_input_items.labels(**context_labels).set(totals.inputs)
        self.gauge_step_result_items.labels(**context_labels).set(totals.results)
        self.gauge_step_duration_seconds.labels(**context_labels, phase="load").set(totals.time_to_load)
        self.gauge_step_duration_seconds.labels(**context_labels, phase="execute").set(totals.time_to_execute)
        self.gauge_step_duration_seconds.labels(**context_labels, phase="save").set(totals.time_to_save)
        self.gauge_step_duration_seconds.labels(**context_labels, phase="total").set(
            totals.time_to_load + totals.time_to_execute + totals.time_to_save
        )
        self._set_step_status(context_labels, "succeeded")
        self.gauge_step_timestamp_seconds.labels(**context_labels, event="completed").set(time.time())

    def __call__(
        self,
        call_next: ExecuteStepCallable,
        step_cls: type[TypedStep],
        inputs: set[PathToFolderWithBaseModels] | None,
        output_dir: PathToFolderWithBaseModels | None,
    ) -> list[tuple[Any, Any]]:
        """Execute step with Prometheus metrics collection.

        Args:
            call_next: The next function in the chain
            step_cls: The step class to execute
            inputs: Input paths or objects
            output_dir: Output directory

        Returns:
            List of tuples containing step results and reports
        """
        step_name = step_cls.__name__
        run_id = os.environ.get("WURZEL_RUN_ID", "unknown")
        context_labels = self._context_labels(step_name)
        started_at = time.time()

        self.counter_started.labels(step_name, run_id).inc()
        self.gauge_step_info.labels(**context_labels).set(1)
        self._set_step_status(context_labels, "started")
        self.gauge_step_timestamp_seconds.labels(**context_labels, event="started").set(started_at)

        try:
            data = call_next(step_cls, inputs, output_dir)
        except Exception:
            self.counter_failed.labels(step_name, run_id).inc()
            self._set_step_status(context_labels, "failed")
            self.gauge_step_timestamp_seconds.labels(**context_labels, event="failed").set(time.time())
            raise

        self._record_success_metrics(data, step_name, run_id, context_labels)
        return data

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *exc_details):
        """Context manager exit - push metrics to gateway."""
        log.info("Pushing metrics", extra={"gateway": self.settings.GATEWAY, "job": self.settings.JOB})
        try:
            push_to_gateway(self.settings.GATEWAY, job=self.settings.JOB, registry=self.registry or REGISTRY)
        except Exception:  # pylint: disable=broad-exception-caught
            log.warning("Could not push prometheus metrics to gateway", exc_info=True)
