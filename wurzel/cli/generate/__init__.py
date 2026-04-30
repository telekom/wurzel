# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Generate CLI subpackage — re-exports for backwards compatibility."""

from wurzel.cli._main import backend_callback, get_available_backends

__all__ = ["backend_callback", "get_available_backends"]
