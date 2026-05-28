# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import asgi_correlation_id
import pytest
from fastapi import FastAPI

from wurzel.core.logging import setup_logging


@pytest.fixture(scope="function")
def FastApiLog():
    def configure_logging():
        setup_logging("DEBUG")

    configure_logging()
    app = FastAPI(on_startup=[configure_logging])
    app.add_middleware(asgi_correlation_id.CorrelationIdMiddleware)
