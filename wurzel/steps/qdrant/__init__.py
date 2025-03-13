# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import warnings
from typing import Type
from ...step import TypedStep
from .data import QdrantResult

__all__ = []
try:
    _HAS_QDRANT = True
    import qdrant_client as _
except ImportError:
    _HAS_QDRANT = False
__all__ = ["QdrantResult", "STEPS"]
STEPS: list[Type[TypedStep]] = []
if _HAS_QDRANT:
    from .step import QdrantConnectorStep
    from .step_mutli_vector import QdrantConnectorMultiVectorStep

    __all__.extend(["QdrantConnectorStep", "QdrantConnectorMultiVectorStep"])
else:
    pass
