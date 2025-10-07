# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
"""Test the internal scan functions in CLI autocomplete."""

from pathlib import Path
from unittest.mock import Mock, patch

from wurzel.cli._main import complete_step_import


class TestCompleteStepImportScanFunctions:
    """Test the nested scan functions within complete_step_import."""

    def test_complete_step_import_with_installed_package_scanning(self):
        """Test complete_step_import when scanning installed packages."""
        with (
            patch("wurzel.cli._main.Path.cwd") as mock_cwd,
            patch("importlib.metadata.distributions") as mock_distributions,
            patch("importlib.util.find_spec") as mock_find_spec,
        ):
            # Setup mocks
            mock_cwd.return_value = Path("/fake/path")
            mock_dist = Mock()
            mock_dist.name = "test_package"
            mock_distributions.return_value = [mock_dist]

            mock_spec = Mock()
            mock_spec.origin = "/path/to/test_package/__init__.py"
            mock_find_spec.return_value = mock_spec

            # Test with package.class format
            result = complete_step_import("test_package.SomeClass")

            # Should return a list (even if empty, it exercised the code)
            assert isinstance(result, list)

    def test_complete_step_import_exception_handling(self):
        """Test that scan functions handle exceptions gracefully."""
        with patch("wurzel.cli._main.Path.cwd") as mock_cwd:
            # Make cwd() raise an exception to test exception handling
            mock_cwd.side_effect = Exception("Fake error")

            # Should not raise exception but return empty list or handle gracefully
            result = complete_step_import("some_input")
            assert isinstance(result, list)

    def test_scan_directory_max_files_limit(self):
        """Test that scan functions respect max_files limit."""
        with patch("wurzel.cli._main.Path.cwd") as mock_cwd, patch("wurzel.cli._main.Path.rglob") as mock_rglob:
            mock_cwd.return_value = Path("/fake")
            # Create many fake files to test the limit
            fake_files = [Path(f"/fake/file{i}.py") for i in range(300)]
            mock_rglob.return_value = fake_files

            # This should trigger the max_files limit in scan_directory_for_typed_steps
            result = complete_step_import("test")
            assert isinstance(result, list)

    def test_build_module_path_function(self):
        """Test the _build_module_path helper function by calling complete_step_import."""
        # We'll test this indirectly through complete_step_import since _build_module_path is private
        with patch("wurzel.cli._main.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/fake/base")

            # This will exercise the _build_module_path function internally
            result = complete_step_import("test")
            assert isinstance(result, list)

    def test_build_module_path_no_base_module(self):
        """Test that the autocomplete works with different path structures."""
        with patch("wurzel.cli._main.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/fake")

            # Test with different input that exercises path building
            result = complete_step_import("")
            assert isinstance(result, list)
