# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for Prometheus middleware."""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from wurzel.core.settings import Settings


class PrometheusMiddlewareSettings(Settings):
    """Configuration for Prometheus middleware."""

    model_config = SettingsConfigDict(env_prefix="PROMETHEUS__")

    GATEWAY: str = Field("localhost:9091", description="host:port of pushgateway")
    JOB: str = Field("default-job-name", description="jobname for the prometheus counter")
    DISABLE_CREATED_METRIC: bool = Field(True, description="disable *_created metrics")
