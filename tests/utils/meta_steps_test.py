# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.utils.meta_steps import *


def test_find_ts():
    pkgs = find_typed_steps_in_package(__package__)
    assert "StepA" in pkgs
    assert len(pkgs) == 3
