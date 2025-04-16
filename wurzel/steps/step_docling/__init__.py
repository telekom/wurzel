# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.utils import HAS_DOCLING as _HAS_DOCLING

__all__ = []
if _HAS_DOCLING:
    from .docling_step import DoclingStep  # noqa: F401

    __all__.append("DoclingStep")
else:
    pass
