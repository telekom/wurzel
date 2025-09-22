# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.utils import HAS_DOCLING, HAS_JOBLIB, HAS_LANGCHAIN_CORE, HAS_MILVUS, HAS_QDRANT, HAS_REQUESTS

from .manual_markdown import ManualMarkdownStep  # noqa: F401

if HAS_DOCLING:
    from .docling import *  # noqa: F403 Allow importing Step classes from docling

if HAS_LANGCHAIN_CORE and HAS_REQUESTS:
    from .embedding import *  # noqa: F403 Allow importing Step classes
    from .embedding import EmbeddingStep  # noqa: F401

if HAS_REQUESTS and HAS_JOBLIB:
    from .scraperapi.step import ScraperAPIStep  # noqa: F401

# These are already conditional in their own __init__.py
if HAS_QDRANT:
    from .qdrant import *  # noqa: F403 Allow importing Step classes

if HAS_MILVUS:
    from .milvus import *  # noqa: F403 Allow importing Step classes
