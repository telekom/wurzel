# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Prometheus metrics middleware for step execution."""

import os
from logging import getLogger
from typing import Any, Optional

from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram, push_to_gateway

from wurzel.core.typed_step import TypedStep
from wurzel.path import PathToFolderWithBaseModels

from ..base import BaseMiddleware, ExecuteStepCallable
from .settings import PrometheusMiddlewareSettings

log = getLogger(__name__)


class PrometheusMiddleware(BaseMiddleware):  # pylint: disable=too-many-instance-attributes
    """Middleware that adds Prometheus metrics collection to step execution.

    This middleware collects metrics about step execution including:
    - Counter of steps started
    - Counter of steps failed
    - Counter of results produced
    - Counter of inputs processed
    - Histograms for load, execute, and save times

    All metrics include two labels:
    - step_name: The name of the step being executed
    - run_id: Unique identifier for the pipeline run (from WURZEL_RUN_ID env var)

    The run_id label allows grouping and filtering metrics by pipeline execution,
    making it easy to track all steps from a single run together.
    """

    def __init__(
        self,
        settings: Optional[PrometheusMiddlewareSettings] = None,
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

    def __call__(
        self,
        call_next: ExecuteStepCallable,
        step_cls: type[TypedStep],
        inputs: Optional[set[PathToFolderWithBaseModels]],
        output_dir: Optional[PathToFolderWithBaseModels],
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

        self.counter_started.labels(step_name, run_id).inc()

        try:
            data = call_next(step_cls, inputs, output_dir)
        except Exception:
            self.counter_failed.labels(step_name, run_id).inc()
            raise

        # Aggregate metrics from all reports
        tt_s, tt_l, tt_e = (0, 0, 0)
        contract_metrics: dict[str, float] = {}
        for _, report in data:
            self.counter_results.labels(step_name, run_id).inc(report.results)
            self.counter_inputs.labels(step_name, run_id).inc(report.inputs)
            tt_s += report.time_to_save
            tt_l += report.time_to_load
            tt_e += report.time_to_execute
            report_metrics = getattr(report, "metrics", None)
            if report_metrics:
                for name, value in report_metrics.items():
                    contract_metrics[name] = contract_metrics.get(name, 0.0) + float(value)

        self.histogram_save.labels(step_name, run_id).observe(tt_s)
        self.histogram_load.labels(step_name, run_id).observe(tt_l)
        self.histogram_execute.labels(step_name, run_id).observe(tt_e)
        for name, value in contract_metrics.items():
            self.gauge_contract_metrics.labels(name, step_name, run_id).set(value)

        return data

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *exc_details):
        """Context manager exit - push metrics to gateway."""
        args = {"gateway": self.settings.GATEWAY, "job": self.settings.JOB}
        log.info("Pushing metrics", extra=args)
        try:
            push_to_gateway(**args, registry=self.registry or REGISTRY)
        except Exception:  # pylint: disable=broad-exception-caught
            log.warning("Could not push prometheus metrics to gateway", exc_info=True)
