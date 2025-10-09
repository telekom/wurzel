# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.executors.middlewares.settings import MiddlewareSettings


def test_middleware_settings_default():
    s = MiddlewareSettings(MIDDLEWARES="")
    assert isinstance(s.MIDDLEWARES, str)
    assert s.MIDDLEWARES == ""
