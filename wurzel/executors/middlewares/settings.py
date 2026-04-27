# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Settings for step executor middlewares."""

from pydantic import Field

from wurzel.core.settings import Settings


class MiddlewareSettings(Settings):
    """Global settings for middleware configuration."""

    MIDDLEWARES: str = Field("", description="Comma-separated list of middlewares to enable (e.g., 'prometheus,otel')")
