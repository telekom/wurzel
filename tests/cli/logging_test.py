import logging

import pytest

from wurzel.cli.logger import WithExtraFormatter

# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


class DummyRecord(logging.LogRecord):
    def __init__(self, **kwargs):
        super().__init__(
            name=kwargs.get("name", "wurzel"),
            level=kwargs.get("level", logging.INFO),
            pathname=kwargs.get("pathname", "test.py"),
            lineno=kwargs.get("lineno", 1),
            msg=kwargs.get("msg", "test message"),
            args=kwargs.get("args", ()),
            exc_info=kwargs.get("exc_info", None),
            func=kwargs.get("func", "test_func"),
            sinfo=kwargs.get("sinfo", None),
        )
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def formatter():
    return WithExtraFormatter()


def test_with_extra_formatter_basic(formatter):
    record = DummyRecord(msg="hello", level=logging.INFO)
    # Patch _get_output_dict to simulate JsonFormatter output
    formatter._get_output_dict = lambda rec: {
        "message": rec.getMessage(),
        "foo": "bar",
        "level": "INFO",
        "@timestamp": "2024-01-01T00:00:00Z",
        "file": "test.py",
        "exc_text": "",
    }
    result = formatter.format(record)
    assert result.startswith("'hello'")
    assert "foo" in result
    assert "level" not in result
    assert "@timestamp" not in result
    assert "file" not in result
