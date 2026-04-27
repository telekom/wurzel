# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.core.meta import find_typed_steps_in_package


def test_find_ts():
    pkgs = find_typed_steps_in_package(__package__)
    assert "StepA" in pkgs
    assert len(pkgs) == 3
