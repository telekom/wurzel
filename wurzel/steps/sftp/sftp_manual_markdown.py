# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""SFTP Manual Markdown Step for loading Markdown files from SFTP servers."""

import logging
import stat
import tempfile
from pathlib import Path, PurePosixPath
from typing import Optional

import paramiko
from pydantic import Field, SecretStr

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed
from wurzel.step import Settings, TypedStep

logger = logging.getLogger(__name__)


class SFTPManualMarkdownSettings(Settings):
    """Settings for SFTP Manual Markdown Step.

    These settings configure the SFTP connection and file retrieval parameters.
    All settings can be provided via environment variables with the prefix
    SFTPMANUALMARKDOWNSTEP__ (e.g., SFTPMANUALMARKDOWNSTEP__HOST=sftp.example.com)
    """

    HOST: str = Field(..., description="SFTP server hostname or IP address")
    PORT: int = Field(22, description="SFTP server port")
    USERNAME: str = Field(..., description="SFTP username")
    PASSWORD: Optional[SecretStr] = Field(None, description="SFTP password (optional if using key)")
    PRIVATE_KEY_PATH: Optional[Path] = Field(None, description="Path to SSH private key file")
    PRIVATE_KEY_PASSPHRASE: Optional[SecretStr] = Field(None, description="Passphrase for private key")
    REMOTE_PATH: str = Field(..., description="Remote path on SFTP server to search for .md files")
    RECURSIVE: bool = Field(True, description="Whether to search recursively for .md files")
    TIMEOUT: float = Field(30.0, description="Connection timeout in seconds")


class SFTPManualMarkdownStep(TypedStep[SFTPManualMarkdownSettings, None, list[MarkdownDataContract]]):
    """Data Source for Markdown files from an SFTP server.

    This step connects to an SFTP server using Paramiko and retrieves all Markdown (.md) files
    from the specified remote path. It works similarly to ManualMarkdownStep but loads files
    from a remote SFTP server instead of the local filesystem.

    Features:
    - Supports password and key-based authentication
    - Recursive directory traversal
    - Automatic connection management
    - Preserves file metadata

    Example usage:
    ```python
    from wurzel.steps.sftp import SFTPManualMarkdownStep, SFTPManualMarkdownSettings

    settings = SFTPManualMarkdownSettings(HOST="sftp.example.com", USERNAME="user", PASSWORD="password", REMOTE_PATH="/documents")
    step = SFTPManualMarkdownStep(settings=settings)
    markdown_docs = step.run(None)
    ```
    """

    def run(self, inpt: None) -> list[MarkdownDataContract]:
        """Execute the step to retrieve Markdown files from SFTP server.

        Args:
            inpt: None (this is a leaf step)

        Returns:
            list[MarkdownDataContract]: List of loaded Markdown documents

        Raises:
            paramiko.SSHException: If connection or authentication fails
            IOError: If file operations fail
        """
        logger.info(
            f"Connecting to SFTP server {self.settings.HOST}:{self.settings.PORT}",
            extra={"host": self.settings.HOST, "port": self.settings.PORT, "remote_path": self.settings.REMOTE_PATH},
        )

        # Establish SFTP connection
        transport = None
        sftp = None

        try:
            # Create SSH transport
            transport = paramiko.Transport((self.settings.HOST, self.settings.PORT))
            transport.connect(
                username=self.settings.USERNAME,
                password=self.settings.PASSWORD.get_secret_value() if self.settings.PASSWORD else None,
                pkey=self._load_private_key() if self.settings.PRIVATE_KEY_PATH else None,
            )

            # Create SFTP client
            sftp = paramiko.SFTPClient.from_transport(transport)

            if sftp is None:
                raise OSError("Failed to create SFTP client")

            # Find all .md files
            md_files = self._find_markdown_files(sftp, self.settings.REMOTE_PATH)

            logger.info(f"Found {len(md_files)} Markdown files on SFTP server", extra={"file_count": len(md_files)})

            # Load each file into MarkdownDataContract
            results: list[MarkdownDataContract] = []
            for remote_file in md_files:
                try:
                    contract = self._load_markdown_from_sftp(sftp, remote_file)
                    if contract:
                        results.append(contract)
                except (OSError, paramiko.SSHException) as e:
                    logger.error(f"Failed to load file {remote_file}: {e}", extra={"remote_file": remote_file, "error": str(e)})

            logger.info(
                f"Successfully loaded {len(results)} Markdown files from SFTP",
                extra={"loaded_count": len(results), "total_found": len(md_files)},
            )
            if len(results) == 0:
                raise StepFailed("No Markdown files found or failed to load any")

            return results

        finally:
            # Clean up connections
            if sftp:
                sftp.close()
            if transport:
                transport.close()

    def _load_private_key(self) -> paramiko.PKey:
        """Load SSH private key from file.

        Returns:
            paramiko.PKey: Loaded private key

        Raises:
            paramiko.SSHException: If key cannot be loaded
        """
        key_path = self.settings.PRIVATE_KEY_PATH
        passphrase = self.settings.PRIVATE_KEY_PASSPHRASE.get_secret_value() if self.settings.PRIVATE_KEY_PASSPHRASE else None

        # Try different key types
        for key_class in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey):
            try:
                return key_class.from_private_key_file(str(key_path), password=passphrase)
            except paramiko.SSHException:
                continue

        raise paramiko.SSHException(f"Could not load private key from {key_path}")

    def _find_markdown_files(self, sftp: paramiko.SFTPClient, remote_path: str) -> list[str]:
        """Recursively find all .md files in the remote path.

        Args:
            sftp: Active SFTP client connection
            remote_path: Path to search for .md files

        Returns:
            list[str]: List of remote file paths
        """
        md_files = []

        try:
            # List directory contents
            for entry in sftp.listdir_attr(remote_path):
                full_path = str(PurePosixPath(remote_path) / entry.filename)

                # Check if it's a directory
                if self._is_directory(entry):
                    if self.settings.RECURSIVE:
                        # Recursively search subdirectories
                        md_files.extend(self._find_markdown_files(sftp, full_path))
                elif entry.filename.endswith(".md"):
                    # It's a markdown file
                    md_files.append(full_path)

        except OSError as e:
            logger.warning(f"Could not access directory {remote_path}: {e}", extra={"remote_path": remote_path, "error": str(e)})

        return md_files

    def _is_directory(self, attr: paramiko.SFTPAttributes) -> bool:
        """Check if an SFTP file attribute represents a directory.

        Args:
            attr: SFTP file attributes

        Returns:
            bool: True if it's a directory
        """
        if attr.st_mode is None:
            return False
        return stat.S_ISDIR(attr.st_mode)

    def _load_markdown_from_sftp(self, sftp: paramiko.SFTPClient, remote_file: str) -> Optional[MarkdownDataContract]:
        """Load a Markdown file from SFTP and convert to MarkdownDataContract.

        Args:
            sftp: Active SFTP client connection
            remote_file: Remote file path

        Returns:
            Optional[MarkdownDataContract]: Loaded contract or None if failed
        """
        try:
            # Download file to temporary location and use MarkdownDataContract.from_file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp_file:
                # Read content from SFTP
                with sftp.open(remote_file, "r") as remote:
                    content = remote.read().decode("utf-8")

                # Write to temp file
                tmp_file.write(content)
                tmp_path = Path(tmp_file.name)

            try:
                # Use MarkdownDataContract.from_file to handle metadata parsing
                url_prefix = f"{self.__class__.__name__}/{remote_file}"
                contract = MarkdownDataContract.from_file(tmp_path, url_prefix="")

                # Override URL if not set in metadata to use remote file path
                if contract.url == str(tmp_path.absolute()):
                    contract.url = url_prefix

                return contract
            finally:
                # Clean up temporary file
                tmp_path.unlink(missing_ok=True)

        except (OSError, paramiko.SSHException) as e:
            raise StepFailed(f"Failed to load markdown file {remote_file}: {e}") from e
