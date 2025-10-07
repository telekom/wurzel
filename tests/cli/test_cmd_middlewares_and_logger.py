# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import logging

from typer.testing import CliRunner

from wurzel.cli import cmd_middlewares
from wurzel.cli.logger import WithExtraFormatter

runner = CliRunner()


def test_list_middlewares_empty(monkeypatch):
    class DummyRegistry:
        def list_available(self):
            return []

        def get(self, name):
            return None

    monkeypatch.setattr("wurzel.step_executor.middlewares.get_registry", lambda: DummyRegistry())
    result = runner.invoke(cmd_middlewares.app, ["list"])
    assert result.exit_code == 0
    assert "No middlewares available" in result.output


def test_inspect_middleware_not_found(monkeypatch):
    class DummyRegistry:
        def list_available(self):
            return ["a"]

        def get(self, name):
            return None

    monkeypatch.setattr("wurzel.step_executor.middlewares.get_registry", lambda: DummyRegistry())
    result = runner.invoke(cmd_middlewares.app, ["inspect", "missing"])
    assert result.exit_code == 1
    assert "Error: Middleware 'missing' not found." in result.output


def test_with_extra_formatter():
    fmt = WithExtraFormatter(reduced=["INFO"])
    rec = logging.LogRecord(
        name="testx", level=logging.INFO, pathname="/x.py", lineno=1, msg="hello", args=(), exc_info=None, func="test_func"
    )
    out = fmt.format(rec)
    assert "'hello'" in out
