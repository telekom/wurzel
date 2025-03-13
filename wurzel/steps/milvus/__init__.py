# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from .settings import MilvusSettings

__all__ = ["MilvusSettings"]
try:
    _HAS_MILVUS = True
    import pymilvus as _
except ImportError:
    _HAS_MILVUS = False
if _HAS_MILVUS:
    from .step import MilvusConnectorStep

    __all__ = [*__all__, "MilvusConnectorStep"]
