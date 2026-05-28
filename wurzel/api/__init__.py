# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Wurzel API — Knowledge as a Service.

Optional subpackage. Install with::

    pip install wurzel[api]

Usage::

    from wurzel.api import create_app

    app = create_app()
"""

from __future__ import annotations

try:
    from wurzel.api.app import create_app

    __all__ = ["create_app"]
except ImportError as exc:  # pragma: no cover
    raise ImportError("wurzel[api] is not installed. Run: pip install wurzel[api]") from exc
