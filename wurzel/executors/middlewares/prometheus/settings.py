# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for Prometheus middleware."""

from pydantic import Field

from wurzel.step.settings import Settings


class PrometheusMiddlewareSettings(Settings):
    """Configuration for Prometheus middleware."""

    PROMETHEUS_GATEWAY: str = Field("localhost:9091", description="host:port of pushgateway")
    PROMETHEUS_JOB: str = Field("default-job-name", description="jobname for the prometheus counter")
    PROMETHEUS_DISABLE_CREATED_METRIC: bool = Field(True, description="disable *_created metrics")
