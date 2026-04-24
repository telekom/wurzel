# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Health-check response models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ComponentStatus(str, Enum):
    """Status of a single infrastructure component."""

    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


class ComponentHealth(BaseModel):
    """Health of a single named component."""

    name: str
    status: ComponentStatus
    detail: str | None = None


class HealthResponse(BaseModel):
    """Aggregated health response returned by ``GET /v1/health``."""

    status: ComponentStatus
    components: list[ComponentHealth] = []
