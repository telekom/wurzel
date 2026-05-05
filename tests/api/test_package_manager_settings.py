# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.api.package_manager.settings."""

import pytest


class TestPackageManagerSettings:
    def test_requires_packages_dir(self):
        from wurzel.api.package_manager.settings import PackageManagerSettings

        with pytest.raises(Exception):
            PackageManagerSettings()  # PACKAGES_DIR is required

    def test_defaults(self, tmp_path, env):
        from wurzel.api.package_manager.settings import PackageManagerSettings

        env.set("PACKAGE_MANAGER__PACKAGES_DIR", str(tmp_path))
        s = PackageManagerSettings()
        assert s.PACKAGES_DIR == tmp_path
        assert s.UV_EXECUTABLE == "uv"
        assert s.INSTALLING_TIMEOUT_SECONDS == 300
        assert s.INSTALLER_ID  # auto-generated UUID

    def test_override_via_env(self, tmp_path, env):
        from wurzel.api.package_manager.settings import PackageManagerSettings

        env.set("PACKAGE_MANAGER__PACKAGES_DIR", str(tmp_path))
        env.set("PACKAGE_MANAGER__UV_EXECUTABLE", "/usr/local/bin/uv")
        env.set("PACKAGE_MANAGER__INSTALLING_TIMEOUT_SECONDS", "120")
        env.set("PACKAGE_MANAGER__INSTALLER_ID", "fixed-id")
        s = PackageManagerSettings()
        assert s.UV_EXECUTABLE == "/usr/local/bin/uv"
        assert s.INSTALLING_TIMEOUT_SECONDS == 120
        assert s.INSTALLER_ID == "fixed-id"

    def test_installer_id_unique_per_instance(self, tmp_path, env):
        from wurzel.api.package_manager.settings import PackageManagerSettings

        env.set("PACKAGE_MANAGER__PACKAGES_DIR", str(tmp_path))
        s1 = PackageManagerSettings()
        s2 = PackageManagerSettings()
        # Each instantiation produces a different UUID (default_factory)
        assert s1.INSTALLER_ID != s2.INSTALLER_ID
