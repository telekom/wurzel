# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import os
import platform

import pytest

IS_MACOS = platform.system() == "Darwin"


@pytest.fixture(scope="function")
def skip_if_mac_os_and_github_action():
    if IS_MACOS and os.environ.get("GITHUB_ACTIONS") == "true":
        pytest.skip("Skipping test on macOS due to MPS error in CI")
