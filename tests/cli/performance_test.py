# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Performance tests for CLI autocompletion to ensure it stays fast."""

import tempfile
import time
from pathlib import Path

import pytest

from wurzel.cli._main import complete_step_import


class TestAutocompletionPerformance:
    """Test CLI autocompletion performance to prevent regressions."""

    def test_autocompletion_performance_wurzel_project(self):
        """Test that autocompletion is fast in wurzel project directory."""
        # Test multiple runs to ensure consistency
        times = []
        for _ in range(5):
            start = time.perf_counter()
            results = complete_step_import("")
            end = time.perf_counter()
            duration = end - start
            times.append(duration)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        # Assert that autocompletion is fast (under 1s average, 2s max for real scanning)
        assert avg_time < 1.0, f"Autocompletion too slow: {avg_time:.3f}s average (expected < 1.0s)"
        assert max_time < 2.0, f"Autocompletion max time too slow: {max_time:.3f}s (expected < 2.0s)"

        # Verify it actually returns results
        assert len(results) > 0, "Autocompletion should return at least some results"

        # Verify wurzel built-in steps are included
        assert any("wurzel.steps." in r for r in results), "Should include wurzel built-in steps"

    def test_autocompletion_performance_user_project(self):
        """Test that autocompletion is fast in a user project directory with custom steps."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a user project structure with custom steps
            steps_dir = temp_path / "mysteps"
            steps_dir.mkdir()

            # Create a custom TypedStep file
            custom_step_file = steps_dir / "custom_step.py"
            custom_step_file.write_text("""
from wurzel.step import TypedStep

class MyCustomStep(TypedStep):
    pass

class AnotherStep(TypedStep):
    pass
""")

            # Change to the user project directory
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_path)

                # Test performance from user project
                times = []
                for _ in range(3):
                    start = time.perf_counter()
                    results = complete_step_import("")
                    end = time.perf_counter()
                    duration = end - start
                    times.append(duration)

                avg_time = sum(times) / len(times)
                max_time = max(times)

                # Assert fast performance even with user project scanning
                assert avg_time < 1.0, f"User project autocompletion too slow: {avg_time:.3f}s average (expected < 1.0s)"
                assert max_time < 2.0, f"User project autocompletion max time too slow: {max_time:.3f}s (expected < 2.0s)"

                # Verify it finds both wurzel steps and user steps
                assert len(results) > 0, "Should find some steps"
                assert any("wurzel.steps." in r for r in results), "Should include wurzel built-in steps"
                assert any("mysteps." in r for r in results), "Should include user-defined steps"

            finally:
                os.chdir(original_cwd)

    def test_autocompletion_performance_with_prefix(self):
        """Test that autocompletion with prefix filtering is fast."""
        times = []
        for _ in range(3):
            start = time.perf_counter()
            results = complete_step_import("wurzel.steps.")
            end = time.perf_counter()
            duration = end - start
            times.append(duration)

        avg_time = sum(times) / len(times)

        # Should be fast since we're filtering
        assert avg_time < 0.7, f"Prefix autocompletion too slow: {avg_time:.3f}s average (expected < 0.7s)"

        # All results should match the prefix
        for result in results:
            assert result.startswith("wurzel.steps."), f"Result '{result}' doesn't match prefix 'wurzel.steps.'"

    def test_autocompletion_functionality_regression(self):
        """Test that performance optimizations don't break functionality."""
        # Test empty prefix - should return all available steps
        all_results = complete_step_import("")
        assert len(all_results) > 0, "Should return steps for empty prefix"

        # Test specific prefix
        wurzel_results = complete_step_import("wurzel.steps.")
        assert len(wurzel_results) > 0, "Should return wurzel steps"
        assert all(r.startswith("wurzel.steps.") for r in wurzel_results), "All results should match prefix"

        # Test non-matching prefix
        no_results = complete_step_import("nonexistent.module.")
        assert len(no_results) == 0, "Should return no results for non-matching prefix"

        # Verify specific known steps are included
        known_steps = [
            "wurzel.steps.manual_markdown.ManualMarkdownStep",
            "wurzel.steps.duplication.DropDuplicationStep",
            "wurzel.steps.splitter.SimpleSplitterStep",
        ]

        for step in known_steps:
            step_results = complete_step_import(step[:20])  # Use partial prefix
            assert any(step in result for result in step_results), f"Known step '{step}' not found in autocompletion"

    def test_autocompletion_performance_large_project_simulation(self):
        """Test performance with a simulated larger project structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create multiple directories and files to simulate a larger project
            for i in range(10):
                subdir = temp_path / f"module_{i}"
                subdir.mkdir()

                # Create some Python files (but not all will be TypedStep)
                for j in range(5):
                    file_path = subdir / f"file_{j}.py"
                    if j % 3 == 0:  # Only some files have TypedStep
                        file_path.write_text(f"""
from wurzel.step import TypedStep

class Step{i}{j}(TypedStep):
    pass
""")
                    else:
                        file_path.write_text(f"""
# Regular Python file {i}-{j}
def some_function():
    pass
""")

            # Change to the simulated project directory
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_path)

                # Test performance
                start = time.perf_counter()
                results = complete_step_import("")
                end = time.perf_counter()
                duration = end - start

                # Should still be fast even with more files
                assert duration < 1.5, f"Large project autocompletion too slow: {duration:.3f}s (expected < 1.5s)"

                # Should find the TypedStep classes
                typed_step_results = [r for r in results if not r.startswith("wurzel.")]
                assert len(typed_step_results) > 0, "Should find user TypedStep classes in large project"

            finally:
                os.chdir(original_cwd)

    @pytest.mark.parametrize("incomplete", ["", "w", "wurzel", "wurzel.steps", "nonexistent"])
    def test_autocompletion_performance_various_inputs(self, incomplete: str):
        """Test performance with various input patterns."""
        start = time.perf_counter()
        results = complete_step_import(incomplete)
        end = time.perf_counter()
        duration = end - start

        # All autocompletion calls should be fast regardless of input
        assert duration < 1.0, f"Autocompletion with input '{incomplete}' too slow: {duration:.3f}s (expected < 1.0s)"

        # Results should match the prefix if provided
        if incomplete:
            for result in results:
                assert result.startswith(incomplete), f"Result '{result}' doesn't match prefix '{incomplete}'"
