# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Comprehensive tests for SFTPManualMarkdownStep."""

import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Check if paramiko is available
try:
    import paramiko

    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False

if not HAS_PARAMIKO:
    pytest.skip("Paramiko is not available", allow_module_level=True)

from pydantic import SecretStr

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed
from wurzel.steps.sftp import SFTPManualMarkdownSettings, SFTPManualMarkdownStep

# Test fixtures for markdown content
MARKDOWN_WITH_METADATA = """---
keywords: "test,markdown"
url: "test/file.md"
---
# Test Markdown
This is a test."""

MARKDOWN_WITHOUT_URL = """---
keywords: "test,markdown"
---
# Test without URL
Content here."""

MARKDOWN_NO_METADATA = """# Simple Markdown
No metadata here."""


# Mock classes for SFTP objects
class MockSFTPAttributes:
    """Mock SFTP file attributes."""

    def __init__(self, filename: str, is_dir: bool = False):
        self.filename = filename
        self.st_mode = stat.S_IFDIR if is_dir else stat.S_IFREG


class MockSFTPFile:
    """Mock SFTP file object."""

    def __init__(self, content: str):
        self.content = content.encode("utf-8")
        self._closed = False

    def read(self):
        return self.content

    def close(self):
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


@pytest.fixture
def mock_sftp_client():
    """Mock SFTP client."""
    return MagicMock(spec=paramiko.SFTPClient)


@pytest.fixture
def mock_transport():
    """Mock Transport object."""
    transport = MagicMock(spec=paramiko.Transport)
    transport.connect = MagicMock()
    transport.close = MagicMock()
    return transport


def create_step_with_settings(settings: SFTPManualMarkdownSettings) -> SFTPManualMarkdownStep:
    """Helper to create a step with given settings, bypassing normal initialization."""
    with patch.object(SFTPManualMarkdownSettings, "model_validate", return_value=settings):
        with patch.object(SFTPManualMarkdownStep, "__init__", lambda self: None):
            step = SFTPManualMarkdownStep()
            step.settings = settings
            return step


class TestMetadataParsing:
    """Tests for YAML metadata parsing in markdown files."""

    @pytest.mark.parametrize(
        "markdown_content,expected_keywords,expected_url_contains,check_keywords_exact",
        [
            (MARKDOWN_WITH_METADATA, "test,markdown", "test/file.md", True),
            (MARKDOWN_WITHOUT_URL, "test,markdown", "/remote/path/test.md", True),
            # For no metadata, keywords will be temp filename, so we just check it's not empty
            (MARKDOWN_NO_METADATA, None, "/remote/path/test.md", False),
        ],
    )
    def test_metadata_parsing(
        self,
        markdown_content,
        expected_keywords,
        expected_url_contains,
        check_keywords_exact,
        mock_transport,
        mock_sftp_client,
    ):
        """Test parsing of YAML metadata in markdown files."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("testpass"),
            REMOTE_PATH="/remote/path",
        )

        # Setup mock SFTP responses
        mock_sftp_client.listdir_attr.return_value = [MockSFTPAttributes("test.md", is_dir=False)]
        mock_sftp_client.open.return_value = MockSFTPFile(markdown_content)

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                step = create_step_with_settings(settings)
                results = [item for batch in step.run(None) for item in batch]

                assert len(results) == 1
                assert isinstance(results[0], MarkdownDataContract)
                if check_keywords_exact:
                    assert results[0].keywords == expected_keywords
                else:
                    # When no metadata, keywords defaults to temp filename (not empty)
                    assert results[0].keywords != ""
                assert expected_url_contains in results[0].url


class TestAuthentication:
    """Tests for different authentication methods."""

    def test_password_authentication(self, mock_transport, mock_sftp_client):
        """Test SFTP connection with password authentication."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("testpass"),
            REMOTE_PATH="/remote/path",
        )

        mock_sftp_client.listdir_attr.return_value = []

        with patch("paramiko.Transport", return_value=mock_transport) as mock_transport_class:
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                step = create_step_with_settings(settings)

                # Should raise StepFailed when no files found
                with pytest.raises(StepFailed, match="No Markdown files found"):
                    list(step.run(None))

                # Verify Transport was created with correct host/port
                mock_transport_class.assert_called_once_with(("test.example.com", 22))

                # Verify connect was called with password
                mock_transport.connect.assert_called_once()
                call_kwargs = mock_transport.connect.call_args.kwargs
                assert call_kwargs["username"] == "testuser"
                assert call_kwargs["password"] == "testpass"  # pragma: allowlist secret
                assert call_kwargs["pkey"] is None

    def test_ssh_key_authentication(self, mock_transport, mock_sftp_client):
        """Test SFTP connection with SSH key authentication."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PRIVATE_KEY_PATH="/path/to/key",
            REMOTE_PATH="/remote/path",
        )

        mock_sftp_client.listdir_attr.return_value = []
        mock_key = MagicMock(spec=paramiko.RSAKey)

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                with patch("paramiko.RSAKey.from_private_key_file", return_value=mock_key):
                    step = create_step_with_settings(settings)

                    # Should raise StepFailed when no files found
                    with pytest.raises(StepFailed, match="No Markdown files found"):
                        list(step.run(None))

                    # Verify connect was called with key
                    mock_transport.connect.assert_called_once()
                    call_kwargs = mock_transport.connect.call_args.kwargs
                    assert call_kwargs["username"] == "testuser"
                    assert call_kwargs["pkey"] == mock_key
                    assert call_kwargs["password"] is None

    def test_key_with_passphrase(self, mock_transport, mock_sftp_client):
        """Test SSH key loading with passphrase."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PRIVATE_KEY_PATH="/path/to/key",
            PRIVATE_KEY_PASSPHRASE=SecretStr("keypass"),
            REMOTE_PATH="/remote/path",
        )

        mock_sftp_client.listdir_attr.return_value = []
        mock_key = MagicMock(spec=paramiko.RSAKey)

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                with patch("paramiko.RSAKey.from_private_key_file", return_value=mock_key) as mock_rsa:
                    step = create_step_with_settings(settings)

                    # Will raise StepFailed due to no files
                    with pytest.raises(StepFailed):
                        list(step.run(None))

                    # Verify key was loaded with passphrase (string value is passed)
                    call_args = mock_rsa.call_args
                    assert Path(call_args[0][0]) == Path("/path/to/key")
                    assert call_args[1]["password"] == "keypass"  # pragma: allowlist secret


class TestFileDiscovery:
    """Tests for file discovery in SFTP directories."""

    def test_recursive_file_discovery(self, mock_transport, mock_sftp_client):
        """Test recursive discovery of markdown files."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("testpass"),
            REMOTE_PATH="/remote/path",
            RECURSIVE=True,
        )

        # Mock directory structure: root has 1 file + 1 subdir, subdir has 1 file
        root_items = [
            MockSFTPAttributes("file1.md", is_dir=False),
            MockSFTPAttributes("subdir", is_dir=True),
        ]
        subdir_items = [MockSFTPAttributes("file2.md", is_dir=False)]

        def listdir_side_effect(path):
            if path == "/remote/path":
                return root_items
            elif path == "/remote/path/subdir":
                return subdir_items
            return []

        mock_sftp_client.listdir_attr.side_effect = listdir_side_effect
        mock_sftp_client.open.return_value = MockSFTPFile(MARKDOWN_NO_METADATA)

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                step = create_step_with_settings(settings)
                results = [item for batch in step.run(None) for item in batch]

                # Should find files in root and subdirectory
                assert len(results) == 2
                assert all(isinstance(r, MarkdownDataContract) for r in results)

    def test_non_recursive_file_discovery(self, mock_transport, mock_sftp_client):
        """Test non-recursive discovery (only root directory)."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("testpass"),
            REMOTE_PATH="/remote/path",
            RECURSIVE=False,
        )

        # Mock directory with file and subdir
        root_items = [
            MockSFTPAttributes("file1.md", is_dir=False),
            MockSFTPAttributes("subdir", is_dir=True),
        ]

        mock_sftp_client.listdir_attr.return_value = root_items
        mock_sftp_client.open.return_value = MockSFTPFile(MARKDOWN_NO_METADATA)

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                step = create_step_with_settings(settings)
                results = [item for batch in step.run(None) for item in batch]

                # Should only find file in root, not enter subdirectory
                assert len(results) == 1
                assert isinstance(results[0], MarkdownDataContract)

    def test_filter_non_markdown_files(self, mock_transport, mock_sftp_client):
        """Test that only .md files are processed."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("testpass"),
            REMOTE_PATH="/remote/path",
        )

        # Mix of markdown and non-markdown files
        root_items = [
            MockSFTPAttributes("file.md", is_dir=False),
            MockSFTPAttributes("file.txt", is_dir=False),
            MockSFTPAttributes("file.pdf", is_dir=False),
        ]

        mock_sftp_client.listdir_attr.return_value = root_items
        mock_sftp_client.open.return_value = MockSFTPFile(MARKDOWN_NO_METADATA)

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                step = create_step_with_settings(settings)
                results = [item for batch in step.run(None) for item in batch]

                # Should only find .md files
                assert len(results) == 1

    def test_empty_directory(self, mock_transport, mock_sftp_client):
        """Test handling of empty directory."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("testpass"),
            REMOTE_PATH="/remote/path",
        )

        mock_sftp_client.listdir_attr.return_value = []

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                step = create_step_with_settings(settings)

                # Should raise StepFailed when no files found
                with pytest.raises(StepFailed, match="No Markdown files found"):
                    list(step.run(None))


class TestErrorHandling:
    """Tests for error handling in various scenarios."""

    def test_connection_failure(self, mock_transport, mock_sftp_client):
        """Test handling of connection failures."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("testpass"),
            REMOTE_PATH="/remote/path",
        )

        mock_transport.connect.side_effect = Exception("Connection failed")

        with patch("paramiko.Transport", return_value=mock_transport):
            step = create_step_with_settings(settings)

            with pytest.raises(Exception, match="Connection failed"):
                list(step.run(None))

            # Verify cleanup was attempted
            mock_transport.close.assert_called_once()

    def test_authentication_failure(self, mock_transport, mock_sftp_client):
        """Test handling of authentication failures."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("wrongpass"),
            REMOTE_PATH="/remote/path",
        )

        mock_transport.connect.side_effect = paramiko.AuthenticationException("Auth failed")

        with patch("paramiko.Transport", return_value=mock_transport):
            step = create_step_with_settings(settings)

            with pytest.raises(paramiko.AuthenticationException):
                list(step.run(None))

    def test_file_read_error_handling(self, mock_transport, mock_sftp_client):
        """Test handling of file read errors (raises StepFailed immediately)."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("testpass"),
            REMOTE_PATH="/remote/path",
        )

        mock_sftp_client.listdir_attr.return_value = [MockSFTPAttributes("test.md", is_dir=False)]
        mock_sftp_client.open.side_effect = OSError("Permission denied")

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                step = create_step_with_settings(settings)

                # Should raise StepFailed with specific error message
                with pytest.raises(StepFailed, match="Failed to load markdown file"):
                    list(step.run(None))

    def test_directory_access_error(self, mock_transport, mock_sftp_client):
        """Test handling of directory access errors (logs warning and raises StepFailed)."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("testpass"),
            REMOTE_PATH="/remote/path",
        )

        mock_sftp_client.listdir_attr.side_effect = OSError("Access denied")

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                step = create_step_with_settings(settings)

                # Should log warning and raise StepFailed when no files found
                with pytest.raises(StepFailed, match="No Markdown files found"):
                    list(step.run(None))

    def test_invalid_key_file(self, mock_transport, mock_sftp_client):
        """Test handling of invalid SSH key file."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PRIVATE_KEY_PATH="/nonexistent/key",
            REMOTE_PATH="/remote/path",
        )

        mock_sftp_client.listdir_attr.return_value = []

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                with patch(
                    "paramiko.RSAKey.from_private_key_file",
                    side_effect=FileNotFoundError("Key not found"),
                ):
                    with patch(
                        "paramiko.Ed25519Key.from_private_key_file",
                        side_effect=FileNotFoundError("Key not found"),
                    ):
                        with patch(
                            "paramiko.ECDSAKey.from_private_key_file",
                            side_effect=FileNotFoundError("Key not found"),
                        ):
                            step = create_step_with_settings(settings)

                            # The actual exception message is "Key not found" not "Could not load..."
                            with pytest.raises(FileNotFoundError, match="Key not found"):
                                list(step.run(None))


class TestConnectionCleanup:
    """Tests for connection cleanup."""

    def test_connection_cleanup(self, mock_transport, mock_sftp_client):
        """Test that connections are properly closed after run (even with StepFailed)."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("testpass"),
            REMOTE_PATH="/remote/path",
        )

        mock_sftp_client.listdir_attr.return_value = []

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                step = create_step_with_settings(settings)

                # Will raise StepFailed due to no files
                with pytest.raises(StepFailed):
                    list(step.run(None))

                # Verify cleanup still happened
                mock_sftp_client.close.assert_called_once()
                mock_transport.close.assert_called_once()

    def test_connection_cleanup_on_error(self, mock_transport, mock_sftp_client):
        """Test that connections are closed even when errors occur."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("testpass"),
            REMOTE_PATH="/remote/path",
        )

        mock_sftp_client.listdir_attr.side_effect = Exception("Error during operation")

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                step = create_step_with_settings(settings)

                with pytest.raises(Exception):
                    list(step.run(None))

                # Verify cleanup still happened
                mock_sftp_client.close.assert_called_once()
                mock_transport.close.assert_called_once()


class TestSSHKeyTypes:
    """Tests for different SSH key types."""

    def test_multiple_key_types(self, mock_transport, mock_sftp_client):
        """Test loading different SSH key types (RSA, Ed25519, ECDSA)."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PRIVATE_KEY_PATH="/path/to/key",
            REMOTE_PATH="/remote/path",
        )

        mock_sftp_client.listdir_attr.return_value = []
        mock_key = MagicMock(spec=paramiko.Ed25519Key)

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                # Simulate RSA failing, Ed25519 succeeding
                with patch(
                    "paramiko.RSAKey.from_private_key_file",
                    side_effect=paramiko.SSHException("Not an RSA key"),
                ):
                    with patch("paramiko.Ed25519Key.from_private_key_file", return_value=mock_key):
                        step = create_step_with_settings(settings)

                        # Will raise StepFailed due to no files
                        with pytest.raises(StepFailed):
                            list(step.run(None))

                        # Verify Ed25519 key was used
                        call_kwargs = mock_transport.connect.call_args.kwargs
                        assert call_kwargs["pkey"] == mock_key


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_utf8_decoding(self, mock_transport, mock_sftp_client):
        """Test handling of UTF-8 encoded markdown files."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("testpass"),
            REMOTE_PATH="/remote/path",
        )

        # Content with UTF-8 characters
        utf8_content = """---
keywords: "test,unicode"
---
# UTF-8 Test
Content with émojis 🎉 and spëcial çharacters."""

        mock_sftp_client.listdir_attr.return_value = [MockSFTPAttributes("test.md", is_dir=False)]
        mock_sftp_client.open.return_value = MockSFTPFile(utf8_content)

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                step = create_step_with_settings(settings)
                results = [item for batch in step.run(None) for item in batch]

                assert len(results) == 1
                # MarkdownDataContract uses 'md' not 'content'
                assert "🎉" in results[0].md

    def test_st_mode_none_handling(self, mock_transport, mock_sftp_client):
        """Test handling of SFTP attributes with None st_mode."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("testpass"),
            REMOTE_PATH="/remote/path",
        )

        # Create attribute with None st_mode
        attr = MockSFTPAttributes("test.md", is_dir=False)
        attr.st_mode = None

        mock_sftp_client.listdir_attr.return_value = [attr]
        mock_sftp_client.open.return_value = MockSFTPFile(MARKDOWN_NO_METADATA)

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", return_value=mock_sftp_client):
                step = create_step_with_settings(settings)
                results = [item for batch in step.run(None) for item in batch]

                # Should still load the file (treating None as regular file)
                assert len(results) == 1


class TestSettings:
    """Tests for settings configuration."""

    def test_sftp_client_creation_failure(self, mock_transport):
        """Test handling of SFTP client creation failure."""
        settings = SFTPManualMarkdownSettings(
            HOST="test.example.com",
            USERNAME="testuser",
            PASSWORD=SecretStr("testpass"),
            REMOTE_PATH="/remote/path",
        )

        with patch("paramiko.Transport", return_value=mock_transport):
            with patch("paramiko.SFTPClient.from_transport", side_effect=Exception("SFTP creation failed")):
                step = create_step_with_settings(settings)

                with pytest.raises(Exception, match="SFTP creation failed"):
                    list(step.run(None))
