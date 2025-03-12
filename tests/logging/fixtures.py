# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest
import logging
from fastapi import FastAPI
import asgi_correlation_id
from wurzel.utils.logging import JsonFormatter
log = logging.getLogger(__name__)
@pytest.fixture(scope="function")
def FastApiLog():
    def configure_logging():
        info_handler = logging.StreamHandler()
        info_handler.setLevel("INFO")
        info_handler.addFilter(asgi_correlation_id.CorrelationIdFilter())
        info_handler.setFormatter(JsonFormatter())
        logging.root.setLevel("DEBUG")
        logging.root.addHandler(info_handler)
        logging.root.propagate = True
        logging.basicConfig(
            handlers=[info_handler],
            level="DEBUG")
    configure_logging()
    app = FastAPI(on_startup=[configure_logging])
    app.add_middleware(asgi_correlation_id.CorrelationIdMiddleware)

    @app.get("/{level}")
    async def test_get_level(level: int):
        log.log(level, "Test Log")
    yield app
