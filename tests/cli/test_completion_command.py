# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for shell completion command."""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from wurzel.cli.completion_command import app as completion_app

runner = CliRunner()


class TestCompletionCommand:
    """Test shell completion installation command."""

    def test_completion_help(self):
        """Completion command should show help."""
        result = runner.invoke(completion_app, ["--help"])
        assert result.exit_code == 0
        assert "Manage shell completion" in result.stdout

    def test_install_help(self):
        """Install subcommand should show help."""
        result = runner.invoke(completion_app, ["install", "--help"])
        assert result.exit_code == 0
        assert "Install shell completion" in result.stdout
        assert "bash, zsh, fish" in result.stdout

    def test_uninstall_help(self):
        """Uninstall subcommand should show help."""
        result = runner.invoke(completion_app, ["uninstall", "--help"])
        assert result.exit_code == 0
        assert "Uninstall shell completion" in result.stdout

    def test_install_zsh_creates_file(self):
        """Installing zsh completion should create completion file."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home") as mock_home:
                home = Path(tmpdir)
                mock_home.return_value = home

                result = runner.invoke(completion_app, ["install", "--shell", "zsh"])
                assert result.exit_code == 0
                assert "✓ Zsh completion installed" in result.stdout

                # Check that file was created
                completion_file = home / ".zsh" / "completions" / "_wurzel"
                assert completion_file.exists()

    def test_install_bash_creates_file(self):
        """Installing bash completion should create completion file."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home") as mock_home:
                home = Path(tmpdir)
                mock_home.return_value = home

                result = runner.invoke(completion_app, ["install", "--shell", "bash"])
                assert result.exit_code == 0
                assert "✓ Bash completion installed" in result.stdout

                # Check that file was created
                completion_file = home / ".bash_completion.d" / "wurzel"
                assert completion_file.exists()

    def test_install_fish_creates_file(self):
        """Installing fish completion should create completion file."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home") as mock_home:
                home = Path(tmpdir)
                mock_home.return_value = home

                result = runner.invoke(completion_app, ["install", "--shell", "fish"])
                assert result.exit_code == 0
                assert "✓ Fish completion installed" in result.stdout

                # Check that file was created
                completion_file = home / ".config" / "fish" / "completions" / "wurzel.fish"
                assert completion_file.exists()

    def test_install_invalid_shell(self):
        """Installing for invalid shell should fail."""
        result = runner.invoke(completion_app, ["install", "--shell", "invalid"])
        assert result.exit_code != 0

    def test_uninstall_zsh_removes_file(self):
        """Uninstalling zsh completion should remove completion file."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home") as mock_home:
                home = Path(tmpdir)
                mock_home.return_value = home

                # First install
                result = runner.invoke(completion_app, ["install", "--shell", "zsh"])
                assert result.exit_code == 0

                # Then uninstall
                result = runner.invoke(completion_app, ["uninstall", "--shell", "zsh"])
                assert result.exit_code == 0
                assert "✓ Zsh completion uninstalled" in result.stdout

                # Check that file was removed
                completion_file = home / ".zsh" / "completions" / "_wurzel"
                assert not completion_file.exists()

    def test_uninstall_nonexistent_completion(self):
        """Uninstalling non-existent completion should handle gracefully."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home") as mock_home:
                home = Path(tmpdir)
                mock_home.return_value = home

                # Try to uninstall without installing
                result = runner.invoke(completion_app, ["uninstall", "--shell", "zsh"])
                assert result.exit_code == 0
                assert "not found" in result.stdout

    def test_install_default_shell_is_zsh(self):
        """Installing without specifying shell should default to zsh."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home") as mock_home:
                home = Path(tmpdir)
                mock_home.return_value = home

                result = runner.invoke(completion_app, ["install"])
                assert result.exit_code == 0
                assert "Zsh completion installed" in result.stdout

    def test_completion_file_contains_completion_logic(self):
        """Completion files should contain actual completion logic."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home") as mock_home:
                home = Path(tmpdir)
                mock_home.return_value = home

                # Install zsh completion
                result = runner.invoke(completion_app, ["install", "--shell", "zsh"])
                assert result.exit_code == 0

                # Check file contents
                completion_file = home / ".zsh" / "completions" / "_wurzel"
                content = completion_file.read_text()
                assert len(content) > 0
                assert "compdef" in content or "_wurzel" in content

    def test_bash_completion_file_has_content(self):
        """Bash completion file should have actual completion logic."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home") as mock_home:
                home = Path(tmpdir)
                mock_home.return_value = home

                result = runner.invoke(completion_app, ["install", "--shell", "bash"])
                assert result.exit_code == 0

                completion_file = home / ".bash_completion.d" / "wurzel"
                content = completion_file.read_text()
                assert len(content) > 0
                assert "complete" in content
                assert "_wurzel_completion" in content

    def test_fish_completion_file_has_content(self):
        """Fish completion file should have actual completion logic."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home") as mock_home:
                home = Path(tmpdir)
                mock_home.return_value = home

                result = runner.invoke(completion_app, ["install", "--shell", "fish"])
                assert result.exit_code == 0

                completion_file = home / ".config" / "fish" / "completions" / "wurzel.fish"
                content = completion_file.read_text()
                assert len(content) > 0
                assert "complete -c wurzel" in content


class TestCompletionIntegration:
    """Test completion integration with main CLI."""

    def test_completion_command_in_main_app(self):
        """Completion command should be registered in main app."""
        from wurzel.cli._main import app

        # The app should have completion registered
        assert app is not None
        # Try invoking help - it should work
        from typer.testing import CliRunner as TRunner

        runner = TRunner()
        result = runner.invoke(app, ["completion", "--help"])
        assert result.exit_code == 0
        assert "Manage shell completion" in result.stdout

    def test_wurzel_completion_in_cli(self):
        """Wurzel completion command should be accessible from main CLI."""
        from typer.testing import CliRunner as TRunner

        from wurzel.cli._main import app

        runner = TRunner()
        result = runner.invoke(app, ["completion", "install", "--help"])
        assert result.exit_code == 0
        assert "Install shell completion" in result.stdout
