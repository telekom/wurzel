# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.api.package_manager.background."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch


class TestPerformInstall:
    def _make_settings(self, tmp_path):
        s = MagicMock()
        s.INSTALLER_ID = "test-replica"
        s.PACKAGES_DIR = tmp_path
        s.UV_EXECUTABLE = "uv"
        return s

    def test_bails_out_when_claim_fails(self, tmp_path):
        """If another replica claimed the row, perform_install returns early."""
        from wurzel.api.package_manager.background import perform_install

        settings = self._make_settings(tmp_path)
        package_id = uuid.uuid4()

        with (
            patch("wurzel.api.package_manager.background._perform_install_async", new_callable=AsyncMock) as mock_async,
        ):
            # Simulate the async function claiming failure (returns without marking installed)
            mock_async.return_value = None
            asyncio.run(perform_install(package_id, settings))
            mock_async.assert_called_once_with(package_id, settings)

    def test_perform_install_swallows_unhandled_exception(self, tmp_path):
        """Wrapper should log and swallow exceptions from async worker."""
        from wurzel.api.package_manager.background import perform_install

        settings = self._make_settings(tmp_path)
        package_id = uuid.uuid4()

        with patch(
            "wurzel.api.package_manager.background._perform_install_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            asyncio.run(perform_install(package_id, settings))

    def test_marks_failed_on_install_error(self, tmp_path):
        """Runtime errors from install_package are caught and persisted as 'failed'."""
        import asyncio

        from wurzel.api.package_manager.background import _perform_install_async

        settings = self._make_settings(tmp_path)
        package_id = uuid.uuid4()

        pkg_row = {
            "id": str(package_id),
            "project_id": str(uuid.uuid4()),
            "package_spec": "badpkg==0.0.1",
            "index_secret_name": None,
        }

        mock_db_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = pkg_row
        mock_db_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(
            return_value=mock_result
        )

        with (
            patch("wurzel.api.package_manager.db.db_claim_pending_package", new_callable=AsyncMock, return_value=True),
            patch("wurzel.api.package_manager.db.db_get_secret_value", new_callable=AsyncMock, return_value=None),
            patch("wurzel.api.package_manager.db.db_mark_installed", new_callable=AsyncMock),
            patch("wurzel.api.package_manager.db.db_mark_failed", new_callable=AsyncMock) as mock_failed,
            patch("wurzel.api.backends.supabase.client._get_async_client", new_callable=AsyncMock, return_value=mock_db_client),
            patch(
                "wurzel.api.package_manager.installer.install_package",
                side_effect=RuntimeError("uv install failed: no such package"),
            ),
        ):
            asyncio.run(_perform_install_async(package_id, settings))
            mock_failed.assert_called_once()
            assert "uv install failed" in mock_failed.call_args[0][1]

    def test_marks_failed_when_uv_executable_missing(self, tmp_path):
        """Unexpected installer exceptions (e.g., FileNotFoundError) are persisted as failed."""
        import asyncio

        from wurzel.api.package_manager.background import _perform_install_async

        settings = self._make_settings(tmp_path)
        package_id = uuid.uuid4()

        pkg_row = {
            "id": str(package_id),
            "project_id": str(uuid.uuid4()),
            "package_spec": "mypkg==1.0.0",
            "index_secret_name": None,
        }

        mock_db_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = pkg_row
        mock_db_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(
            return_value=mock_result
        )

        with (
            patch("wurzel.api.package_manager.db.db_claim_pending_package", new_callable=AsyncMock, return_value=True),
            patch("wurzel.api.package_manager.db.db_mark_installed", new_callable=AsyncMock),
            patch("wurzel.api.package_manager.db.db_mark_failed", new_callable=AsyncMock) as mock_failed,
            patch("wurzel.api.backends.supabase.client._get_async_client", new_callable=AsyncMock, return_value=mock_db_client),
            patch(
                "wurzel.api.package_manager.installer.install_package",
                side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'uv'"),
            ),
        ):
            asyncio.run(_perform_install_async(package_id, settings))
            mock_failed.assert_called_once()
            assert "Package install failed unexpectedly" in mock_failed.call_args[0][1]

    def test_returns_when_not_claimed(self, tmp_path):
        from wurzel.api.package_manager.background import _perform_install_async

        settings = self._make_settings(tmp_path)
        package_id = uuid.uuid4()

        with patch("wurzel.api.package_manager.db.db_claim_pending_package", new_callable=AsyncMock, return_value=False):
            import asyncio

            asyncio.run(_perform_install_async(package_id, settings))

    def test_marks_failed_when_secret_missing(self, tmp_path):
        import asyncio

        from wurzel.api.package_manager.background import _perform_install_async

        settings = self._make_settings(tmp_path)
        package_id = uuid.uuid4()
        pkg_row = {
            "id": str(package_id),
            "project_id": str(uuid.uuid4()),
            "package_spec": "privatepkg==1.0.0",
            "index_secret_name": "private_index",  # pragma: allowlist secret
        }

        db_client = MagicMock()
        db_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(
            return_value=MagicMock(data=pkg_row)
        )

        with (
            patch("wurzel.api.package_manager.db.db_claim_pending_package", new_callable=AsyncMock, return_value=True),
            patch("wurzel.api.package_manager.db.db_get_secret_value", new_callable=AsyncMock, return_value=None),
            patch("wurzel.api.package_manager.db.db_mark_failed", new_callable=AsyncMock) as mock_failed,
            patch("wurzel.api.backends.supabase.client._get_async_client", new_callable=AsyncMock, return_value=db_client),
        ):
            asyncio.run(_perform_install_async(package_id, settings))

        mock_failed.assert_called_once()

    def test_returns_when_row_missing_after_claim(self, tmp_path):
        import asyncio

        from wurzel.api.package_manager.background import _perform_install_async

        settings = self._make_settings(tmp_path)
        package_id = uuid.uuid4()

        db_client = MagicMock()
        db_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(
            return_value=MagicMock(data=None)
        )

        with (
            patch("wurzel.api.package_manager.db.db_claim_pending_package", new_callable=AsyncMock, return_value=True),
            patch("wurzel.api.backends.supabase.client._get_async_client", new_callable=AsyncMock, return_value=db_client),
        ):
            asyncio.run(_perform_install_async(package_id, settings))

    def test_successful_install_marks_installed(self, tmp_path):
        import asyncio

        from wurzel.api.package_manager.background import _perform_install_async

        settings = self._make_settings(tmp_path)
        package_id = uuid.uuid4()
        project_id = uuid.uuid4()
        pkg_row = {
            "id": str(package_id),
            "project_id": str(project_id),
            "package_spec": "okpkg==1.0.0",
            "index_secret_name": None,
        }

        db_client = MagicMock()
        db_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(
            return_value=MagicMock(data=pkg_row)
        )

        with (
            patch("wurzel.api.package_manager.db.db_claim_pending_package", new_callable=AsyncMock, return_value=True),
            patch("wurzel.api.package_manager.db.db_mark_installed", new_callable=AsyncMock) as mock_mark_installed,
            patch("wurzel.api.backends.supabase.client._get_async_client", new_callable=AsyncMock, return_value=db_client),
            patch("wurzel.api.package_manager.installer.install_package"),
            patch(
                "wurzel.api.package_manager.installer.read_lock_entries", return_value=[{"requirement": "okpkg==1.0.0", "sha256": "abc"}]
            ),
            patch("wurzel.api.package_manager.background._invalidate_project_step_cache") as mock_invalidate,
        ):
            asyncio.run(_perform_install_async(package_id, settings))

        mock_mark_installed.assert_called_once()
        mock_invalidate.assert_called_once_with(project_id)

    def test_successful_install_with_secret_index(self, tmp_path):
        import asyncio

        from wurzel.api.package_manager.background import _perform_install_async

        settings = self._make_settings(tmp_path)
        package_id = uuid.uuid4()
        project_id = uuid.uuid4()
        pkg_row = {
            "id": str(package_id),
            "project_id": str(project_id),
            "package_spec": "privatepkg==1.0.0",
            "index_secret_name": "private_index",  # pragma: allowlist secret
        }

        db_client = MagicMock()
        db_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(
            return_value=MagicMock(data=pkg_row)
        )

        with (
            patch("wurzel.api.package_manager.db.db_claim_pending_package", new_callable=AsyncMock, return_value=True),
            patch(
                "wurzel.api.package_manager.db.db_get_secret_value",
                new_callable=AsyncMock,
                return_value="https://user:pw@example/simple",  # pragma: allowlist secret
            ),
            patch("wurzel.api.package_manager.db.db_mark_installed", new_callable=AsyncMock),
            patch("wurzel.api.backends.supabase.client._get_async_client", new_callable=AsyncMock, return_value=db_client),
            patch("wurzel.api.package_manager.installer.install_package") as mock_install,
            patch("wurzel.api.package_manager.installer.read_lock_entries", return_value=[]),
            patch("wurzel.api.package_manager.background._invalidate_project_step_cache"),
        ):
            asyncio.run(_perform_install_async(package_id, settings))

        assert mock_install.call_args[0][2] == "https://user:pw@example/simple"  # pragma: allowlist secret

    def test_invalidate_cache_swallows_exceptions(self):
        from wurzel.api.package_manager.background import _invalidate_project_step_cache

        project_id = uuid.uuid4()
        with patch("wurzel.api.routes.steps.service._DEFAULT_CACHE.clear_project", side_effect=RuntimeError("boom")):
            _invalidate_project_step_cache(project_id)


class TestRecoverAndReinstallOnStartup:
    def _make_settings(self, tmp_path):
        s = MagicMock()
        s.INSTALLER_ID = "test-replica"
        s.PACKAGES_DIR = tmp_path
        s.UV_EXECUTABLE = "uv"
        s.INSTALLING_TIMEOUT_SECONDS = 300
        return s

    def test_resets_stale_rows(self, tmp_path):
        from wurzel.api.package_manager.background import recover_and_reinstall_on_startup

        settings = self._make_settings(tmp_path)

        with (
            patch("wurzel.api.package_manager.db.db_reset_stale_installing", new_callable=AsyncMock, return_value=2) as mock_reset,
            patch("wurzel.api.package_manager.db.db_get_installed_packages_with_locks", new_callable=AsyncMock, return_value=[]),
            patch("wurzel.api.package_manager.db.db_get_pending_packages", new_callable=AsyncMock, return_value=[]),
            patch("wurzel.api.package_manager.db.db_mark_failed", new_callable=AsyncMock),
        ):
            recover_and_reinstall_on_startup(settings)
            mock_reset.assert_called_once_with("test-replica", 300)

    def test_recover_wrapper_swallows_unhandled_exception(self, tmp_path):
        from wurzel.api.package_manager.background import recover_and_reinstall_on_startup

        settings = self._make_settings(tmp_path)
        with patch(
            "wurzel.api.package_manager.background._recover_and_reinstall_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            recover_and_reinstall_on_startup(settings)

    def test_skips_reinstall_when_no_lock_entries(self, tmp_path):
        from wurzel.api.package_manager.background import recover_and_reinstall_on_startup

        settings = self._make_settings(tmp_path)
        installed = [
            {
                "id": str(uuid.uuid4()),
                "project_id": str(uuid.uuid4()),
                "package_spec": "mypkg==1.0.0",
                "project_package_locks": [],
            }
        ]

        with (
            patch("wurzel.api.package_manager.db.db_reset_stale_installing", new_callable=AsyncMock, return_value=0),
            patch("wurzel.api.package_manager.db.db_get_installed_packages_with_locks", new_callable=AsyncMock, return_value=installed),
            patch("wurzel.api.package_manager.db.db_get_pending_packages", new_callable=AsyncMock, return_value=[]),
            patch("subprocess.run") as mock_run,
        ):
            recover_and_reinstall_on_startup(settings)

        mock_run.assert_not_called()

    def test_marks_failed_when_startup_reinstall_fails(self, tmp_path):
        from wurzel.api.package_manager.background import recover_and_reinstall_on_startup

        settings = self._make_settings(tmp_path)
        project_id = uuid.uuid4()
        package_id = uuid.uuid4()
        installed = [
            {
                "id": str(package_id),
                "project_id": str(project_id),
                "package_spec": "mypkg==1.0.0",
                "project_package_locks": [{"requirement": "mypkg==1.0.0", "sha256": "deadbeef"}],
            }
        ]

        with (
            patch("wurzel.api.package_manager.db.db_reset_stale_installing", new_callable=AsyncMock, return_value=0),
            patch("wurzel.api.package_manager.db.db_get_installed_packages_with_locks", new_callable=AsyncMock, return_value=installed),
            patch("wurzel.api.package_manager.db.db_get_pending_packages", new_callable=AsyncMock, return_value=[]),
            patch("wurzel.api.package_manager.db.db_mark_failed", new_callable=AsyncMock) as mock_failed,
            patch("subprocess.run") as mock_run,
        ):
            from unittest.mock import MagicMock

            mock_run.return_value = MagicMock(returncode=1, stderr="nope")
            recover_and_reinstall_on_startup(settings)

        mock_failed.assert_called_once()

    def test_triggers_pending_installs(self, tmp_path):
        from wurzel.api.package_manager.background import recover_and_reinstall_on_startup

        settings = self._make_settings(tmp_path)
        pending_id = str(uuid.uuid4())

        with (
            patch("wurzel.api.package_manager.db.db_reset_stale_installing", new_callable=AsyncMock, return_value=0),
            patch("wurzel.api.package_manager.db.db_get_installed_packages_with_locks", new_callable=AsyncMock, return_value=[]),
            patch("wurzel.api.package_manager.db.db_get_pending_packages", new_callable=AsyncMock, return_value=[{"id": pending_id}]),
            patch("wurzel.api.package_manager.background.perform_install", new_callable=AsyncMock) as mock_perform,
        ):
            recover_and_reinstall_on_startup(settings)

        mock_perform.assert_called_once()

    def test_skips_reinstall_when_dir_exists(self, tmp_path):
        """Packages whose target dir already exists are not re-installed."""
        from wurzel.api.package_manager.background import recover_and_reinstall_on_startup

        settings = self._make_settings(tmp_path)
        project_id = uuid.uuid4()
        package_id = uuid.uuid4()

        # Create the target dir to simulate an already-populated volume
        target = tmp_path / str(project_id)
        target.mkdir()

        installed = [
            {
                "id": str(package_id),
                "project_id": str(project_id),
                "package_spec": "mypkg==1.0.0",
                "index_secret_name": None,
                "project_package_locks": [{"requirement": "mypkg==1.0.0", "sha256": "abc"}],
            }
        ]

        with (
            patch("wurzel.api.package_manager.db.db_reset_stale_installing", new_callable=AsyncMock, return_value=0),
            patch("wurzel.api.package_manager.db.db_get_installed_packages_with_locks", new_callable=AsyncMock, return_value=installed),
            patch("wurzel.api.package_manager.db.db_get_pending_packages", new_callable=AsyncMock, return_value=[]),
            patch("subprocess.run") as mock_run,
        ):
            recover_and_reinstall_on_startup(settings)
            mock_run.assert_not_called()

    def test_reinstalls_when_dir_missing(self, tmp_path):
        """Packages with no on-disk dir are re-installed using --require-hashes."""
        from wurzel.api.package_manager.background import recover_and_reinstall_on_startup

        settings = self._make_settings(tmp_path)
        project_id = uuid.uuid4()
        package_id = uuid.uuid4()
        # Do NOT create the target dir

        installed = [
            {
                "id": str(package_id),
                "project_id": str(project_id),
                "package_spec": "mypkg==1.0.0",
                "index_secret_name": None,
                "project_package_locks": [{"requirement": "mypkg==1.0.0", "sha256": "deadbeef"}],
            }
        ]

        with (
            patch("wurzel.api.package_manager.db.db_reset_stale_installing", new_callable=AsyncMock, return_value=0),
            patch("wurzel.api.package_manager.db.db_get_installed_packages_with_locks", new_callable=AsyncMock, return_value=installed),
            patch("wurzel.api.package_manager.db.db_get_pending_packages", new_callable=AsyncMock, return_value=[]),
            patch("wurzel.api.package_manager.db.db_mark_failed", new_callable=AsyncMock),
            patch("subprocess.run") as mock_run,
        ):
            from unittest.mock import MagicMock

            mock_run.return_value = MagicMock(returncode=0, stderr="")
            recover_and_reinstall_on_startup(settings)

            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "--require-hashes" in cmd
            assert "sha256:deadbeef" in " ".join(cmd)
