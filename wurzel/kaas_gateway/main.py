# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import uvicorn

from wurzel.kaas_gateway.settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "wurzel.kaas_gateway.app:app",
        host=settings.KAAS_GATEWAY_HOST,
        port=settings.KAAS_GATEWAY_PORT,
    )
