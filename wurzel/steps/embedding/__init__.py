# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
from wurzel.utils import HAS_LANGCHAIN_CORE

if HAS_LANGCHAIN_CORE:
    from .huggingface import HuggingFaceInferenceAPIEmbeddings, PrefixedAPIEmbeddings  # noqa: F401
    from .step import (
        EmbeddingStep,  # noqa: F401
        TruncatedEmbeddingStep,  # noqa: F401
    )
