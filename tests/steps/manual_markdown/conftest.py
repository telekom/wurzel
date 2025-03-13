# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest


@pytest.fixture(scope="function", autouse=True)
def mm_env(env):
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", "/")
