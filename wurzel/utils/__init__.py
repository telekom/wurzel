# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: Apache-2.0

from importlib.util import find_spec as _find_spec
from logging import getLogger
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .meta_settings import WZ, create_model  # noqa: F401
    from .meta_steps import find_typed_steps_in_package  # noqa: F401
    from .splitters import semantic_splitter  # noqa: F401
    from .to_markdown.html2md import MarkdownConverterSettings, to_markdown  # noqa: F401

log = getLogger(__name__)

_opt_deps = {
    k: bool(_find_spec(k))
    for k in [
        "tlsh",
        "pymilvus",
        "qdrant_client",
        "docling",
        "langchain_core",
        "requests",
        "joblib",
        "hera",
        "spacy",
        "tiktoken",
        "transformers",
        "paramiko",
    ]
}
HAS_TLSH = _opt_deps["tlsh"]
HAS_MILVUS = _opt_deps["pymilvus"]
HAS_QDRANT = _opt_deps["qdrant_client"]
HAS_DOCLING = _opt_deps["docling"]
HAS_LANGCHAIN_CORE = _opt_deps["langchain_core"]
HAS_REQUESTS = _opt_deps["requests"]
HAS_JOBLIB = _opt_deps["joblib"]
HAS_HERA = _opt_deps["hera"]
HAS_SPACY = _opt_deps["spacy"]
HAS_TIKTOKEN = _opt_deps["tiktoken"]
HAS_TRANSFORMERS = _opt_deps["transformers"]
HAS_PARAMIKO = _opt_deps["paramiko"]


def __getattr__(name: str) -> Any:
    """Lazy import heavy dependencies to avoid slowing down CLI startup."""
    if name == "WZ":
        from .meta_settings import WZ  # pylint: disable=import-outside-toplevel

        return WZ
    if name == "create_model":
        from .meta_settings import create_model  # pylint: disable=import-outside-toplevel

        return create_model
    if name == "find_typed_steps_in_package":
        from .meta_steps import find_typed_steps_in_package  # pylint: disable=import-outside-toplevel

        return find_typed_steps_in_package
    if name == "semantic_splitter":
        from .splitters import semantic_splitter  # pylint: disable=import-outside-toplevel

        return semantic_splitter
    if name == "MarkdownConverterSettings":
        from .to_markdown.html2md import MarkdownConverterSettings  # pylint: disable=import-outside-toplevel

        return MarkdownConverterSettings
    if name == "to_markdown":
        from .to_markdown.html2md import to_markdown  # pylint: disable=import-outside-toplevel

        return to_markdown

    raise AttributeError(f"module 'wurzel.utils' has no attribute '{name}'")


log.info("Optional deps in env", extra={**_opt_deps})
__all__ = [
    "semantic_splitter",
    "WZ",
    "create_model",
    "try_get_length",
    "find_typed_steps_in_package",
    "to_markdown",
    "HAS_MILVUS",
    "HAS_TLSH",
    "HAS_DOCLING",
    "HAS_LANGCHAIN_CORE",
    "HAS_REQUESTS",
    "HAS_JOBLIB",
    "HAS_HERA",
    "HAS_PARAMIKO",
    "MarkdownConverterSettings",
]


def try_get_length(x: Any) -> int:
    """Tries to get length, return 1 if fails.

    Args:
        x (Any): get length of

    Returns:
        int: length or 1

    """
    try:
        return len(x)
    # pylint: disable=bare-except
    except:  # noqa: E722
        return 1
