# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
"""Test for cyclic imports in utils"""


def test_import_utils():
    import wurzel.utils # noqa: F401 I001


def test_import_steps():
    import wurzel.steps # noqa: F401 I001


def test_import_utils_meta_settings():
    import wurzel.utils.meta_settings # noqa: F401 I001
