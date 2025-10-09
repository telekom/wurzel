# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
# pylint: disable=duplicate-code

"""Prometheus metrics middleware for step execution."""

import os
from logging import getLogger
from typing import Any, Optional

from prometheus_client import REGISTRY, Counter, Histogram, push_to_gateway

from wurzel.path import PathToFolderWithBaseModels
from wurzel.step.typed_step import TypedStep

from .base import BaseMiddleware, ExecuteStepCallable
from .prometheus.settings import PrometheusMiddlewareSettings

log = getLogger(__name__)


class PrometheusMiddleware(BaseMiddleware):  # pylint: disable=too-many-instance-attributes
    """Middleware that adds Prometheus metrics collection to step execution.

    This middleware collects metrics about step execution including:
    - Counter of steps started
    - Counter of steps failed
    - Counter of results produced
    - Counter of inputs processed
    - Histograms for load, execute, and save times
    """

    def __init__(self, settings: Optional[PrometheusMiddlewareSettings] = None):
        """Initialize the Prometheus middleware.

        Args:
            settings: Configuration for Prometheus metrics (gateway, job name, etc.)
        """
        super().__init__()
        self.settings = settings or PrometheusMiddlewareSettings()
        self._setup_metrics()

    def _setup_metrics(self):
        """Set up Prometheus metrics collectors."""
        if self.settings.PROMETHEUS_DISABLE_CREATED_METRIC:
            os.environ["PROMETHEUS_DISABLE_CREATED_SERIES"] = "True"

        self.counter_started = Counter("steps_started", "Total number of TypedSteps started", ("step_name",))
        self.counter_failed = Counter("steps_failed", "Total number of TypedSteps failed", ("step_name",))
        self.counter_results = Counter("step_results", "count of result, if its an array, otherwise -1", ("step_name",))
        self.counter_inputs = Counter("step_inputs", "count of inputs", ("step_name",))
        self.histogram_save = Histogram("step_hist_save", "Time to save results", ("step_name",))
        self.histogram_load = Histogram("step_hist_load", "Time to load inputs", ("step_name",))
        self.histogram_execute = Histogram("step_hist_execute", "Time to execute results", ("step_name",))

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
        lbl = step_cls.__name__
        self.counter_started.labels(lbl).inc()

        try:
            data = call_next(step_cls, inputs, output_dir)
        except Exception:
            self.counter_failed.labels(lbl).inc()
            raise

        # Aggregate metrics from all reports
        tt_s, tt_l, tt_e = (0, 0, 0)
        for _, report in data:
            self.counter_results.labels(lbl).inc(report.results)
            self.counter_inputs.labels(lbl).inc(report.inputs)
            tt_s += report.time_to_save
            tt_l += report.time_to_load
            tt_e += report.time_to_execute

        self.histogram_save.labels(lbl).observe(tt_s)
        self.histogram_load.labels(lbl).observe(tt_l)
        self.histogram_execute.labels(lbl).observe(tt_e)

        return data

    def __exit__(self, *exc_details):
        """Context manager exit - push metrics to gateway."""
        args = {"gateway": self.settings.PROMETHEUS_GATEWAY, "job": self.settings.PROMETHEUS_JOB}
        log.info("Pushing metrics", extra=args)
        try:
            push_to_gateway(**args, registry=REGISTRY)
        except Exception:  # pylint: disable=broad-exception-caught
            log.warning("Could not push prometheus metrics to gateway", exc_info=True)
