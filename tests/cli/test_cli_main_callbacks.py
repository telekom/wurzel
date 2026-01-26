# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import typer

from wurzel.cli import _main as cli_main


def test_executer_callback_base():
    # Base
    res = cli_main.executer_callback(None, None, "Base")
    from wurzel.executors import BaseStepExecutor

    assert res is BaseStepExecutor


def test_executer_callback_bad():
    import pytest

    with pytest.raises(typer.BadParameter):
        cli_main.executer_callback(None, None, "unknown")


def test_backend_callback_invalid(monkeypatch):
    import pytest

    # Mock HAS_HERA to avoid UnboundLocalError
    monkeypatch.setattr("wurzel.utils.HAS_HERA", False)

    # Pass an unsupported backend name
    with pytest.raises(typer.BadParameter):
        cli_main.backend_callback(None, None, "NonExistingBackend")


def test_update_log_level_runs():
    # Should not raise
    cli_main.update_log_level("INFO")


def test_build_module_path(tmp_path):
    # Create a fake project structure
    search = tmp_path / "pkg"
    search.mkdir()
    (search / "sub").mkdir()
    f = search / "sub" / "mymodule.py"
    f.write_text("class X: pass")

    # Relative to search path
    res = cli_main._build_module_path(f, search, "base")
    assert res.startswith("base.")

    # No base_module
    res2 = cli_main._build_module_path(f, search, "")
    assert res2.count(".") >= 1


def test_complete_step_import_minimal(tmp_path, monkeypatch):
    # Run autocomplete with a prefix that likely exists (wurzel) and ensure it doesn't crash
    results = cli_main.complete_step_import("")
    assert isinstance(results, list)

    # Call with a non-matching prefix
    results2 = cli_main.complete_step_import("no_such_prefix_hopefully")
    assert isinstance(results2, list)
