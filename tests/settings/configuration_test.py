# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest
from loguru import logger

from wurzel.core.logging import setup_logging


@pytest.fixture(autouse=True)
def reset_loguru():
    logger.remove()
    yield
    logger.remove()


def test_setup_logging():
    setup_logging("INFO")


def test_setup_logging_json_string():
    setup_logging("INFO", json_string=True)


def test_warning_override():
    from wurzel.core.logging import warnings_to_logger

    warnings_to_logger("Test", "None", __file__, lineno="123")
    # Dummy test
