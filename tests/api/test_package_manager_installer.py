# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.api.package_manager.installer."""

import csv
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestValidatePackageSpec:
    @pytest.mark.parametrize(
        "spec",
        [
            "mypkg",
            "mypkg==1.0.0",
            "my-pkg>=2.0,<3.0",
            "my_pkg[extra]==1.2.3",
            "My.Pkg!=1.0",
        ],
    )
    def test_valid_specs(self, spec):
        from wurzel.api.package_manager.installer import validate_package_spec

        validate_package_spec(spec)  # should not raise

    @pytest.mark.parametrize(
        "spec",
        [
            "pkg; rm -rf /",
            "pkg && echo hi",
            "pkg | cat /etc/passwd",
            "`whoami`",
            "$(id)",
        ],
    )
    def test_invalid_specs_raise(self, spec):
        from wurzel.api.package_manager.installer import validate_package_spec

        with pytest.raises(ValueError, match="Invalid package spec"):
            validate_package_spec(spec)


class TestGetProjectPackageDir:
    def test_returns_correct_path(self, tmp_path):
        from wurzel.api.package_manager.installer import get_project_package_dir

        project_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        result = get_project_package_dir(project_id, tmp_path)
        assert result == tmp_path / "12345678-1234-5678-1234-567812345678"


class TestInstallPackage:
    def test_success(self, tmp_path):
        from wurzel.api.package_manager.installer import install_package

        project_id = uuid.uuid4()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            install_package(project_id, "mypkg==1.0.0", None, tmp_path, "uv")

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "uv" in call_args
        assert "mypkg==1.0.0" in call_args
        assert "--index-url" not in call_args

    def test_success_with_index_url(self, tmp_path):
        from wurzel.api.package_manager.installer import install_package

        project_id = uuid.uuid4()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            install_package(project_id, "mypkg==1.0.0", "https://my.index/simple", tmp_path, "uv")

        call_args = mock_run.call_args[0][0]
        assert "--index-url" in call_args
        assert "https://my.index/simple" in call_args

    def test_failure_raises_runtime_error(self, tmp_path):
        from wurzel.api.package_manager.installer import install_package

        project_id = uuid.uuid4()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="package not found")
            with pytest.raises(RuntimeError, match="uv install failed"):
                install_package(project_id, "nonexistent==9.9.9", None, tmp_path, "uv")

    def test_no_shell_true(self, tmp_path):
        """subprocess.run must never be called with shell=True."""
        from wurzel.api.package_manager.installer import install_package

        project_id = uuid.uuid4()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            install_package(project_id, "mypkg==1.0.0", None, tmp_path, "uv")

        _, kwargs = mock_run.call_args
        assert kwargs.get("shell", False) is False


class TestReadLockEntries:
    def _write_record(self, dist_info_dir: Path, rows: list[tuple]) -> None:
        dist_info_dir.mkdir(parents=True, exist_ok=True)
        record_path = dist_info_dir / "RECORD"
        with record_path.open("w", newline="") as fh:
            writer = csv.writer(fh)
            for row in writer:
                writer.writerow(row)
            # Use direct write for simplicity
        with record_path.open("w") as fh:
            fh.write("".join(f"{r[0]},{r[1]},{r[2]}\n" for r in rows))

    def test_reads_sha256_from_record(self, tmp_path):
        from wurzel.api.package_manager.installer import read_lock_entries

        dist_info = tmp_path / "mypkg-1.0.0.dist-info"
        dist_info.mkdir()
        record = dist_info / "RECORD"
        record.write_text("mypkg/__init__.py,sha256:abc123def456,1234\nmypkg-1.0.0.dist-info/RECORD,,\n")

        entries = read_lock_entries(tmp_path)
        assert len(entries) == 1
        assert entries[0]["requirement"] == "mypkg==1.0.0"
        assert entries[0]["sha256"] == "abc123def456"  # pragma: allowlist secret

    def test_multiple_packages(self, tmp_path):
        from wurzel.api.package_manager.installer import read_lock_entries

        for name, version, sha in [("pkg_a", "1.0.0", "aaa"), ("pkg-b", "2.3.1", "bbb")]:
            dist_info = tmp_path / f"{name}-{version}.dist-info"
            dist_info.mkdir()
            (dist_info / "RECORD").write_text(f"{name}/__init__.py,sha256:{sha},100\n")

        entries = read_lock_entries(tmp_path)
        assert len(entries) == 2
        requirements = {e["requirement"] for e in entries}
        assert "pkg_a==1.0.0" in requirements
        assert "pkg-b==2.3.1" in requirements

    def test_no_dist_info_returns_empty(self, tmp_path):
        from wurzel.api.package_manager.installer import read_lock_entries

        entries = read_lock_entries(tmp_path)
        assert entries == []

    def test_missing_sha256_skipped(self, tmp_path):
        from wurzel.api.package_manager.installer import read_lock_entries

        dist_info = tmp_path / "mypkg-1.0.0.dist-info"
        dist_info.mkdir()
        (dist_info / "RECORD").write_text("mypkg/__init__.py,,100\n")

        entries = read_lock_entries(tmp_path)
        assert entries == []
