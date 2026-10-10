# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for the OpenTelemetry middleware."""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from wurzel.core.settings import Settings


class OtelMiddlewareSettings(Settings):
    """Configuration for the OpenTelemetry middleware.

    All fields are loaded from environment variables with the ``OTEL__`` prefix,
    e.g. ``OTEL__ENDPOINT=http://collector:4317``.

    Routing attributes
    ------------------
    ``PROJECT_NAME`` is written to the OTel ``Resource`` as ``project.name`` so
    Arize Phoenix automatically routes each trace into the correct project.

    ``TENANT`` is written to the ``Resource`` as ``tenant`` and also attached as
    a span attribute.  The OTel Collector can use it with the ``routing``
    connector to fan-out traces to tenant-specific exporters.
    """

    model_config = SettingsConfigDict(env_prefix="OTEL__")

    ENDPOINT: str = Field("localhost:4317", description="OTLP gRPC collector endpoint (host:port)")
    SERVICE_NAME: str = Field("wurzel", description="OTel resource service.name attribute")
    INSECURE: bool = Field(True, description="Use an insecure (plain-text) gRPC channel")
    ENABLED: bool = Field(True, description="Master switch — set False to disable all OTel instrumentation")
    PROJECT_NAME: str = Field(
        "",
        description=(
            "Project name (OTEL__PROJECT_NAME). "
            "Written as the 'project.name' resource attribute so Phoenix routes "
            "the trace into the named project. Empty string uses Phoenix's default project."
        ),
    )
    TENANT: str = Field(
        "",
        description=(
            "Tenant identifier (OTEL__TENANT). "
            "Written as the 'tenant' resource attribute and as a span attribute. "
            "The OTel Collector routing connector can fan-out by this value."
        ),
    )
