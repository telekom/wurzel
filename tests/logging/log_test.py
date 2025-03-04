# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest
import logging
from wurzel.utils.logging import JsonFormatter
import json
FOR_EACH_LOG_LEVEL = pytest.mark.parametrize("level",
    [pytest.param(v, id=k) for k,v in logging.getLevelNamesMapping().items() if k != "NOTSET"]
)
FOR_EACH_LOGGER=pytest.mark.parametrize('loggername',['root', 'new_one', ''])

@FOR_EACH_LOG_LEVEL
@FOR_EACH_LOGGER
def test_logging(capsys, level, loggername):
    handler = logging.StreamHandler()
    handler.setLevel("DEBUG")
    handler.setFormatter(JsonFormatter())

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[handler],
        force=True
    )
    logging.getLogger("root").log(level, "hi")
    out = capsys.readouterr().err.splitlines()[0]
    assert "hi" in out
    assert logging.getLevelName(level) in out
    assert json.loads(out)

@FOR_EACH_LOG_LEVEL
@FOR_EACH_LOGGER
def test_logging_extra_data(capsys, level, loggername):
    handler = logging.StreamHandler()
    handler.setLevel("DEBUG")
    handler.setFormatter(JsonFormatter())

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[handler],
        force=True
    )
    logging.getLogger("root").log(level, "hi", extra={'a': 1, 'b': logging})
    out = capsys.readouterr().err.splitlines()[0]
    assert "hi" in out
    assert logging.getLevelName(level) in out
    data = json.loads(out)
    assert 'extra' in data
    assert data['extra']['a'] == 1

@FOR_EACH_LOG_LEVEL
@FOR_EACH_LOGGER
def test_logging_cor_id(capsys, level, loggername):
    import asgi_correlation_id
    from uuid import uuid4
    uuid = uuid4()
    asgi_correlation_id.correlation_id.set(str(uuid))
    handler = logging.StreamHandler()
    handler.setLevel("DEBUG")
    handler.setFormatter(JsonFormatter())

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[handler],
        force=True
    )
    logging.getLogger("root").log(level, "hi")
    out = capsys.readouterr().err.splitlines()[0]
    assert "hi" in out
    assert logging.getLevelName(level) in out
    assert json.loads(out)
    assert str(uuid) in out