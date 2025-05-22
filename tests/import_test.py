# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
"""Test for cyclic imports in utils."""

from unittest import mock

import pytest

from wurzel.utils import HAS_DOCLING, HAS_MILVUS, HAS_QDRANT


def test_import_utils():
    import wurzel.utils  # noqa: F401 I001


def test_import_steps():
    import wurzel.steps  # noqa: F401 I001
    import wurzel.steps.qdrant  # noqa: F401 I001
    import wurzel.steps.milvus  # noqa: F401 I001

    import wurzel.steps.embedding  # noqa: F401 I001
    import wurzel.steps.manual_markdown  # noqa: F401 I001
    import wurzel.steps.milvus.settings  # noqa: F401 I001
    import wurzel.steps.qdrant.settings  # noqa: F401 I001

    if HAS_QDRANT:
        import wurzel.steps.qdrant.step  # noqa: F401 I001
        from wurzel.steps import QdrantConnectorStep  # noqa: F401 I001
        from wurzel.steps import QdrantConnectorMultiVectorStep  # noqa: F401 I001

    if HAS_DOCLING:
        from wurzel.steps import DoclingStep  # noqa: F401 I001
        from wurzel.steps import DoclingSettings  # noqa: F401 I001
        import wurzel.steps.docling  # noqa: F401 I001
        import wurzel.steps.docling.settings  # noqa: F401 I001

    if HAS_MILVUS:
        import wurzel.steps.milvus.step  # noqa: F401 I001
        from wurzel.steps import MilvusConnectorStep  # noqa: F401 I001

    import wurzel.steps.embedding.settings  # noqa: F401 I001
    from wurzel.steps import ManualMarkdownStep  # noqa: F401 I001
    from wurzel.steps import EmbeddingStep  # noqa: F401 I001


def test_fail_import_steps():
    with (
        mock.patch("wurzel.utils.HAS_QDRANT", False),
        mock.patch("wurzel.utils.HAS_DOCLING", False),
        mock.patch("wurzel.utils.HAS_MILVUS", False),
    ):
        with pytest.raises(ImportError):
            pass

        with pytest.raises(ImportError):
            pass

        with pytest.raises(ImportError):
            from wurzel.steps import MilvusConnectorStep  # noqa: F401 I001


def test_import_utils_meta_settings():
    import wurzel.utils.meta_settings  # noqa: F401 I001
