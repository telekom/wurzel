# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
from wurzel.utils import HAS_MILVUS as _HAS_MILVUS

from .settings import MilvusSettings  # noqa: F401

if _HAS_MILVUS:
    from .step import MilvusConnectorStep  # noqa: F401
