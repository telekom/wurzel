# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""OpenTelemetry middleware package."""

from .otel import OtelMiddleware
from .settings import OtelMiddlewareSettings

__all__ = ["OtelMiddleware", "OtelMiddlewareSettings"]
