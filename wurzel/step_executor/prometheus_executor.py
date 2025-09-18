# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import os
from logging import getLogger
from typing import Any, Optional, Self

from prometheus_client import REGISTRY, Counter, Histogram, push_to_gateway

from .base_executor import (
    BaseStepExecutor,
    PathToFolderWithBaseModels,
    StepReport,
    TypedStep,
)
from .settings import PrometheusSettings as Settings

log = getLogger(__name__)


class PrometheusStepExecutor(BaseStepExecutor):
    """Executer for KP steps.
    Adds PrometheusCounter; is a singelton.

    For more info see `BaseStepExecutor`.
    """

    # pylint: disable=too-many-instance-attributes
    counter_started: Counter
    counter_failed: Counter
    counter_results: Counter
    counter_inputs: Counter
    counter_log_warning_counts: Counter
    counter_log_error_counts: Counter
    histogram_load: Histogram
    histogram_save: Histogram
    histogram_execute: Histogram
    # step_info: Info
    # Singelton Instance
    _instance = None
    s = Settings

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.__init__(*args, **kwargs)
            # pylint: disable=protected-access
            cls._instance.s = Settings()
            cls._instance.__setup_metrics()
        return cls._instance

    # pylint: disable=unused-private-member
    def __setup_metrics(self):
        if self.s.PROMETHEUS_DISABLE_CREATED_METRIC:
            os.environ["PROMETHEUS_DISABLE_CREATED_SERIES"] = "True"

        base_labels = [
            "step_name",
            "history_first_step",
            "history_last_step",
        ]
        self.counter_started = Counter("steps_started", "Total number of TypedSteps started", base_labels)
        self.counter_failed = Counter("steps_failed", "Total number of TypedSteps failed", base_labels)
        self.counter_results = Counter(
            "step_results",
            "count of result, if its an array, otherwise -1",
            base_labels,
        )
        self.counter_log_warning_counts = Counter(
            "step_log_warning_counts",
            "count of log warning messages",
            base_labels,
        )
        self.counter_log_error_counts = Counter(
            "step_log_error_counts",
            "count of log error messages",
            base_labels,
        )
        self.counter_inputs = Counter("step_inputs", "count of inputs", base_labels)
        self.histogram_save = Histogram("step_hist_save", "Time to save results", base_labels)
        self.histogram_load = Histogram("step_hist_load", "Time to load inputs", base_labels)
        self.histogram_execute = Histogram("step_hist_execute", "Time to execute results", base_labels)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_details):
        args = {"gateway": self.s.PROMETHEUS_GATEWAY, "job": self.s.PROMETHEUS_JOB}
        log.info("Pushing metrics", extra=args)
        try:
            push_to_gateway(**args, registry=REGISTRY)
        except Exception:  # pylint: disable=broad-exception-caught
            log.warning("Could not push prometheus metrics to gateway", exc_info=True)

    def execute_step(
        self,
        step_cls: TypedStep,
        inputs: Optional[set[PathToFolderWithBaseModels]],
        output_dir: Optional[PathToFolderWithBaseModels],
    ) -> list[tuple[Any, StepReport]]:
        """Run a given Step.

        Args:
            step_cls (Type[TypedDVCStep]): Step to run
            inputs (set[PathToBaseModel]): Step inputs
            output (PathToBaseModel): Step output

        """
        step_name = step_cls.__name__

        report_labels = {
            "step_name": step_name,
            "history_first_step": None,
            "history_last_step": None,
        }

        self.counter_started.labels(**report_labels).inc()
        try:
            data = super().execute_step(step_cls, inputs, output_dir)
        except:
            self.counter_failed.labels(**report_labels)
            raise
        time_to_save, time_to_load, time_to_execute = (0, 0, 0)
        for _, report in data:
            # Increase counter variables with step report data
            report_labels.update(
                {
                    # Keep track of pipeline history
                    "history_first_step": report.history[0].split("-")[0],  # There is probably a cleaner way for doing this
                    "history_last_step": report.history[-1],
                }
            )

            self.counter_results.labels(**report_labels).inc(report.results)
            self.counter_inputs.labels(**report_labels).inc(report.inputs)

            self.counter_log_error_counts.labels(**report_labels).inc(report.log_error_counts)
            self.counter_log_warning_counts.labels(**report_labels).inc(report.log_warning_counts)

            time_to_save += report.time_to_save
            time_to_load += report.time_to_load
            time_to_execute += report.time_to_execute

        self.histogram_save.labels(**report_labels).observe(time_to_save)
        self.histogram_load.labels(**report_labels).observe(time_to_load)
        self.histogram_execute.labels(**report_labels).observe(time_to_execute)
        return data
