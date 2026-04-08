# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi import APIRouter

from wurzel.kaas_gateway.models import IsAliveResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/isAlive", response_model=IsAliveResponse)
def is_alive() -> IsAliveResponse:
    return IsAliveResponse(status="ok")
