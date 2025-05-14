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
        self.counter_started = Counter("steps_started", "Total number of TypedSteps started", ("step_name",))
        self.counter_failed = Counter("steps_failed", "Total number of TypedSteps failed", ("step_name",))
        self.counter_results = Counter(
            "step_results",
            "count of result, if its an array, otherwise -1",
            ("step_name",),
        )
        self.counter_inputs = Counter("step_inputs", "count of inputs", ("step_name",))
        self.histogram_save = Histogram("step_hist_save", "Time to save results", ("step_name",))
        self.histogram_load = Histogram("step_hist_load", "Time to load inputs", ("step_name",))
        self.histogram_execute = Histogram("step_hist_execute", "Time to execute results", ("step_name",))

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
        lbl = step_cls.__name__
        self.counter_started.labels(lbl).inc()
        try:
            data = super().execute_step(step_cls, inputs, output_dir)
        except:
            self.counter_failed.labels(lbl)
            raise
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
