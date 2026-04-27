# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.core.meta import find_typed_steps_in_package


def test_find_ts():
    pkgs = find_typed_steps_in_package(__package__)
    expected = {"StepA", "StepB", "StepC"}
    assert expected.issubset(pkgs.keys())
    # Each expected class must be defined inside tests.utils, not leaked from an import
    for name in expected:
        assert pkgs[name].__module__.startswith("tests.utils"), f"{name} should be from tests.utils"
