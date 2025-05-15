# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.utils import HAS_DOCLING as _HAS_DOCLING

if _HAS_DOCLING:
    from .docling_step import DoclingStep  # noqa: F401
    from .settings import DoclingSettings  # noqa: F401
else:
    pass
