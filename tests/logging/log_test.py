# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json
import logging

import pytest

from wurzel.utils.logging import JsonFormatter, JsonStringFormatter

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
