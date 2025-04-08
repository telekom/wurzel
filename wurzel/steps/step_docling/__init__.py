# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

__all__ = []
try:
    _HAS_DOCLING = True
    import docling as _  # noqa: F401
except ImportError:
    _HAS_DOCLING = False
if _HAS_DOCLING:
    from .docling_step import DoclingStep  # noqa: F401

    __all__.append("DoclingStep")
else:
    pass
