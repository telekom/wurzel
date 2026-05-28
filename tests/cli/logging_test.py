# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json

import pytest
from loguru import logger

from wurzel.cli.logger import setup_cli_logging
from wurzel.core.logging import setup_logging


@pytest.fixture(autouse=True)
def reset_loguru():
    logger.remove()
    yield
    logger.remove()


def test_setup_cli_logging_does_not_raise():
    """setup_cli_logging should configure loguru without errors."""
    setup_cli_logging("INFO")
    setup_cli_logging("DEBUG")


def test_setup_logging_output_is_json(capsys):
    setup_logging("INFO")
    logger.info("cli logging test")
    err = capsys.readouterr().err.strip()
    assert err
    data = json.loads(err.splitlines()[-1])
    assert data["message"] == "cli logging test"
    assert data["level"] == "INFO"
