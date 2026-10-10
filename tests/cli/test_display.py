# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.cli.environment.display — _print_requirements and _print_missing."""

from unittest.mock import patch

from wurzel.cli.environment.display import (
    _build_missing_table,
    _build_requirements_table,
    _print_missing,
    _print_requirements,
)
from wurzel.cli.environment.requirements import EnvValidationIssue, EnvVarRequirement


def make_requirement(env_var="MY_VAR", required=True, step_name="MyStep", default="", description="A var"):
    return EnvVarRequirement(
        env_var=env_var,
        required=required,
        step_name=step_name,
        field_name="MY_VAR",
        default=default,
        description=description,
        step_index=0,
        field_index=0,
    )


def make_issue(env_var="MISSING_VAR", message="is required"):
    return EnvValidationIssue(env_var=env_var, message=message)


class TestBuildRequirementsTable:
    def test_returns_table_with_rows(self):
        from rich.table import Table

        req = make_requirement()
        table = _build_requirements_table([req])
        assert isinstance(table, Table)
        assert table.row_count == 1

    def test_empty_requirements(self):
        from rich.table import Table

        table = _build_requirements_table([])
        assert isinstance(table, Table)
        assert table.row_count == 0

    def test_optional_requirement(self):
        from rich.table import Table

        req = make_requirement(required=False, default="default_val")
        table = _build_requirements_table([req])
        assert isinstance(table, Table)
        assert table.row_count == 1


class TestBuildMissingTable:
    def test_returns_table_with_rows(self):
        from rich.table import Table

        issue = make_issue()
        table = _build_missing_table([issue])
        assert isinstance(table, Table)
        assert table.row_count == 1

    def test_empty_issues(self):
        from rich.table import Table

        table = _build_missing_table([])
        assert isinstance(table, Table)
        assert table.row_count == 0


class TestPrintRequirements:
    def test_prints_table_when_terminal(self, capsys):
        req = make_requirement(env_var="FOO_VAR", default="mydefault")
        with patch("wurzel.cli.environment.display.console") as mock_console:
            mock_console.is_terminal = True
            _print_requirements([req])
            mock_console.print.assert_called_once()

    def test_prints_text_when_not_terminal(self, capsys):
        req = make_requirement(env_var="FOO_VAR", required=False, default="mydefault")
        with patch("wurzel.cli.environment.display.console") as mock_console:
            mock_console.is_terminal = False
            with patch("wurzel.cli.environment.display.typer.echo") as mock_echo:
                _print_requirements([req])
                mock_echo.assert_called_once()
                output = mock_echo.call_args[0][0]
                assert "FOO_VAR" in output
                assert "optional" in output

    def test_prints_required_text_when_not_terminal(self, capsys):
        req = make_requirement(env_var="REQUIRED_VAR", required=True, description=None)
        with patch("wurzel.cli.environment.display.console") as mock_console:
            mock_console.is_terminal = False
            with patch("wurzel.cli.environment.display.typer.echo") as mock_echo:
                _print_requirements([req])
                output = mock_echo.call_args[0][0]
                assert "required" in output


class TestPrintMissing:
    def test_prints_table_when_terminal(self):
        issue = make_issue()
        with patch("wurzel.cli.environment.display.console") as mock_console:
            mock_console.is_terminal = True
            _print_missing([issue])
            mock_console.print.assert_called_once()

    def test_prints_text_when_not_terminal(self):
        issue = make_issue(env_var="MISSING_KEY", message="This variable is required")
        with patch("wurzel.cli.environment.display.console") as mock_console:
            mock_console.is_terminal = False
            with patch("wurzel.cli.environment.display.typer.echo") as mock_echo:
                _print_missing([issue])
                mock_echo.assert_called_once()
                output = mock_echo.call_args[0][0]
                assert "MISSING_KEY" in output
                assert "This variable is required" in output
