# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for CLI tab completion functionality (TDD approach)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from wurzel.cli.shared.autocompletion import complete_step_import


class TestCompleteStepImport:
    """Test step import autocompletion function."""

    def test_returns_list(self):
        """Autocompletion should always return a list."""
        result = complete_step_import("")
        assert isinstance(result, list)

    def test_empty_prefix_returns_steps(self):
        """Autocompletion with empty prefix should return available steps."""
        result = complete_step_import("")
        assert len(result) > 0, "Should find at least some steps"

    def test_prefix_filters_results(self):
        """Results should match the provided prefix."""
        result = complete_step_import("wurzel.steps.")
        assert all(r.startswith("wurzel.steps.") for r in result), "All results should match prefix"

    def test_nonexistent_prefix_returns_empty(self):
        """Nonexistent prefix should return empty list."""
        result = complete_step_import("nonexistent.module.that.does.not.exist.")
        assert result == [], "Should return empty list for nonexistent prefix"

    def test_includes_wurzel_steps(self):
        """Should include wurzel built-in steps."""
        result = complete_step_import("")
        assert any("wurzel.steps." in r for r in result), "Should include wurzel.steps"

    def test_case_sensitive_matching(self):
        """Prefix matching should be case-sensitive."""
        result_lower = complete_step_import("wurzel.steps.")
        result_upper = complete_step_import("WURZEL.STEPS.")
        assert len(result_lower) > 0
        assert len(result_upper) == 0, "Case mismatch should return empty"

    def test_partial_module_path(self):
        """Should support partial module paths."""
        result = complete_step_import("wurzel")
        assert all(r.startswith("wurzel") for r in result)

    def test_handles_cwd_error_gracefully(self):
        """Should handle errors when getting current working directory."""
        with patch("wurzel.cli.shared.autocompletion.Path.cwd") as mock_cwd:
            mock_cwd.side_effect = Exception("Permission denied")
            result = complete_step_import("")
            # Should still return results from wurzel package even if cwd fails
            assert isinstance(result, list)

    def test_handles_import_errors_gracefully(self):
        """Should handle import errors when scanning packages."""
        with patch("importlib.metadata.distributions") as mock_dist:
            mock_dist.side_effect = Exception("Import error")
            result = complete_step_import("")
            # Should still return results from other sources
            assert isinstance(result, list)

    def test_performance_empty_prefix(self):
        """Should complete reasonably fast for empty prefix."""
        import time

        start = time.perf_counter()
        result = complete_step_import("")
        duration = time.perf_counter() - start
        assert duration < 2.0, f"Autocompletion too slow: {duration:.2f}s (expected < 2.0s)"
        assert len(result) > 0

    def test_performance_with_prefix(self):
        """Should complete very fast with prefix filter."""
        import time

        start = time.perf_counter()
        _ = complete_step_import("wurzel.steps.m")
        duration = time.perf_counter() - start
        assert duration < 0.5, f"Prefix autocompletion too slow: {duration:.2f}s (expected < 0.5s)"

    def test_no_duplicates_in_results(self):
        """Results should not contain duplicates."""
        result = complete_step_import("")
        assert len(result) == len(set(result)), "Results should not have duplicates"

    def test_results_are_sorted(self):
        """Results should be in a consistent order (ideally sorted)."""
        result = complete_step_import("")
        # Check that results are the same order on repeated calls
        result2 = complete_step_import("")
        assert result == result2, "Results should be consistent across calls"


class TestStepImportInSharedInit:
    """Test that complete_step_import is properly exported from shared module."""

    def test_can_import_from_shared(self):
        """complete_step_import should be importable from wurzel.cli.shared."""
        from wurzel.cli.shared import complete_step_import  # noqa: F401
        # If we got here without ImportError, the test passes

    def test_can_import_from_shared_autocompletion(self):
        """complete_step_import should be importable from autocompletion module."""
        from wurzel.cli.shared.autocompletion import complete_step_import  # noqa: F401
        # If we got here without ImportError, the test passes


class TestCommandAutocompletion:
    """Test that CLI commands have autocompletion configured."""

    def test_run_command_exists(self):
        """Run command should exist in the CLI."""
        from wurzel.cli.run.command import app as run_app

        assert run_app is not None
        assert hasattr(run_app, "command") or hasattr(run_app, "registered_commands")

    def test_inspect_command_exists(self):
        """Inspect command should exist in the CLI."""
        from wurzel.cli.inspect.command import app as inspect_app

        assert inspect_app is not None

    def test_generate_command_exists(self):
        """Generate command should exist in the CLI."""
        from wurzel.cli.generate.command import app as generate_app

        assert generate_app is not None

    def test_env_command_exists(self):
        """Env command should exist in the CLI."""
        from wurzel.cli.environment.command import app as env_app

        assert env_app is not None

    def test_main_app_integrates_commands(self):
        """Main app should have all command groups registered."""
        from wurzel.cli._main import app

        assert app is not None
        # The app should be callable/instantiable
        assert hasattr(app, "command") or hasattr(app, "registered_commands")


class TestAutocompletionEdgeCases:
    """Test edge cases in autocompletion."""

    def test_empty_string_prefix(self):
        """Empty string should be handled properly."""
        result = complete_step_import("")
        assert isinstance(result, list)
        assert len(result) >= 0

    def test_none_like_prefix(self):
        """Should handle string that looks like None."""
        result = complete_step_import("None")
        assert isinstance(result, list)

    def test_special_characters_in_prefix(self):
        """Should handle special characters gracefully."""
        result = complete_step_import("wurzel.steps.@#$")
        assert isinstance(result, list)

    def test_very_long_prefix(self):
        """Should handle very long prefix gracefully."""
        long_prefix = "a" * 1000
        result = complete_step_import(long_prefix)
        assert isinstance(result, list)
        assert len(result) == 0, "Very long nonsense prefix should return empty"

    def test_dot_separated_modules(self):
        """Should handle fully qualified module paths."""
        result = complete_step_import("wurzel.steps.")
        # All results should be fully qualified
        assert all("." in r for r in result if result)

    def test_single_step_match(self):
        """Should return single match when prefix is very specific."""
        result = complete_step_import("wurzel.steps.manual_markdown.ManualMarkdown")
        assert isinstance(result, list)
        # May be 0 or 1 results depending on exact class name
        assert len(result) <= 1


class TestAutocompletionWithCustomSteps:
    """Test autocompletion finds custom user steps."""

    def test_finds_custom_steps_in_cwd(self):
        """Should find custom TypedStep classes in current directory."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a custom step file
            step_file = Path(tmpdir) / "custom_steps.py"
            step_file.write_text(
                """
from wurzel.step import TypedStep

class MyCustomStep(TypedStep):
    pass
"""
            )

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = complete_step_import("")
                # Should find our custom step
                assert any("MyCustomStep" in r for r in result), f"Should find MyCustomStep, got {result}"
            finally:
                os.chdir(original_cwd)

    def test_finds_nested_custom_steps(self):
        """Should find custom steps in nested directories."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested step structure
            steps_dir = Path(tmpdir) / "mysteps"
            steps_dir.mkdir()
            step_file = steps_dir / "my_step.py"
            step_file.write_text(
                """
from wurzel.step import TypedStep

class NestedStep(TypedStep):
    pass
"""
            )

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = complete_step_import("")
                assert any("NestedStep" in r for r in result), f"Should find NestedStep, got {result}"
            finally:
                os.chdir(original_cwd)


class TestAutocompletionIntegration:
    """Integration tests for autocompletion with actual CLI."""

    def test_cli_can_be_imported_without_errors(self):
        """Main CLI module should import without errors."""
        try:
            from wurzel.cli._main import app  # noqa: F401
        except ImportError as e:
            pytest.fail(f"Failed to import CLI app: {e}")

    def test_autocompletion_exported_from_main_module(self):
        """Autocompletion function should be accessible for CLI commands."""
        # Commands reference complete_step_import, so it must be accessible
        from wurzel.cli.shared import complete_step_import as func  # noqa: F401

        assert callable(func)

    def test_can_call_autocompletion_multiple_times(self):
        """Autocompletion should be callable multiple times without side effects."""
        result1 = complete_step_import("wurzel")
        result2 = complete_step_import("wurzel")
        result3 = complete_step_import("wurzel")
        assert result1 == result2 == result3, "Repeated calls should return same results"
