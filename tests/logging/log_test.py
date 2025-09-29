# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import sys

import pytest

from wurzel.utils.logging import JsonFormatter, JsonStringFormatter, log_uncaught_exception, setup_uncaught_exception_logging

FOR_EACH_LOG_LEVEL = pytest.mark.parametrize(
    "level",
    [pytest.param(v, id=k) for k, v in logging.getLevelNamesMapping().items() if k != "NOTSET"],
)
FOR_EACH_LOGGER = pytest.mark.parametrize("loggername", ["root", "new_one", ""])
FOR_EACH_FORMATTER = pytest.mark.parametrize("formatter", [JsonFormatter(), JsonStringFormatter()])


@FOR_EACH_LOG_LEVEL
@FOR_EACH_LOGGER
@FOR_EACH_FORMATTER
def test_logging(capsys, level, loggername, formatter):
    handler = logging.StreamHandler()
    handler.setLevel("DEBUG")
    handler.setFormatter(formatter)

    logging.basicConfig(level=logging.DEBUG, handlers=[handler], force=True)
    logging.getLogger("root").log(level, "hi")
    out = capsys.readouterr().err.splitlines()[0]
    assert "hi" in out
    assert logging.getLevelName(level) in out
    assert json.loads(out)


@FOR_EACH_LOG_LEVEL
@FOR_EACH_LOGGER
@FOR_EACH_FORMATTER
def test_logging_extra_data(capsys, level, loggername, formatter):
    handler = logging.StreamHandler()
    handler.setLevel("DEBUG")
    handler.setFormatter(formatter)
    logging.basicConfig(level=logging.DEBUG, handlers=[handler], force=True)
    logging.getLogger(loggername).log(level, "hi", extra={"a": 1, "b": logging})
    out = capsys.readouterr().err.splitlines()[0]
    assert "hi" in out
    assert logging.getLevelName(level) in out
    data = json.loads(out)
    data_extra = {}
    assert "extra" in data
    if isinstance(formatter, JsonStringFormatter):
        # Since JsonStringFormatter changes all extra field to json string
        assert isinstance(data["extra"], str)
        data_extra = json.loads(data["extra"])
    elif isinstance(formatter, JsonFormatter):
        data_extra = data["extra"]
    assert data_extra["a"] == 1


@FOR_EACH_LOG_LEVEL
@FOR_EACH_LOGGER
def test_logging_cor_id(capsys, level, loggername):
    from uuid import uuid4

    import asgi_correlation_id

    uuid = uuid4()
    asgi_correlation_id.correlation_id.set(str(uuid))
    handler = logging.StreamHandler()
    handler.setLevel("DEBUG")
    handler.setFormatter(JsonFormatter())

    logging.basicConfig(level=logging.DEBUG, handlers=[handler], force=True)
    logging.getLogger("root").log(level, "hi")
    out = capsys.readouterr().err.splitlines()[0]
    assert "hi" in out
    assert logging.getLevelName(level) in out
    assert json.loads(out)
    assert str(uuid) in out


def test_setup_uncaught_exception_logging(caplog):
    """Test that setup_uncaught_exception_logging sets sys.excepthook."""
    # Save original excepthook
    original_hook = sys.excepthook

    try:
        setup_uncaught_exception_logging()
        assert sys.excepthook == log_uncaught_exception
    finally:
        # Restore original hook
        sys.excepthook = original_hook


def test_log_uncaught_exception(caplog):
    """Test that log_uncaught_exception logs the exception."""
    # Create a mock exception
    exc_type = None
    exc_value = None
    exc_traceback = None
    try:
        raise ValueError("Test exception")
    except ValueError:
        exc_type, exc_value, exc_traceback = sys.exc_info()

    # Ensure they are not None
    assert exc_type is not None
    assert exc_value is not None
    assert exc_traceback is not None

    # Call the function
    with caplog.at_level(logging.ERROR):
        log_uncaught_exception(exc_type, exc_value, exc_traceback)

    # Check that it was logged
    assert "Uncaught exception" in caplog.text
    assert "Test exception" in caplog.text
