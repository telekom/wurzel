# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from re import Pattern as _re_pattern
from re import compile as _re_compile
from typing import Any, Callable, Self

import pydantic

from .datacontract import PydanticModel

_RE_HEADER = _re_compile(r"---\s*([\s\S]*?)\s*---")
_RE_TOPIC = _re_compile(r"topics:\s*(.*)")
_RE_URL = _re_compile(r"url:\s*(.*)")
_RE_BODY = _re_compile(r"---[\s\S]*?---\s*([\s\S]*)")


class MarkdownDataContract(PydanticModel):
    """contract of the input of the EmbeddingStep."""

    md: str
    keywords: str
    url: str  # Url of pydantic is buggy in serialization

    @classmethod
    @pydantic.validate_call
    def from_dict_w_function(cls, doc: dict[str, Any], func: Callable[[str], str]):
        """Create a MarkdownDataContract from a dict and apply a custom func to test."""
        return cls(
            md=func(doc["text"]),
            url=doc["metadata"]["url"],
            keywords=doc["metadata"]["keywords"],
        )

    @classmethod
    def from_file(cls, path: Path, url_prefix: str = "") -> Self:
        """Load MdContract from .md file.

        Args:
            path (Path): Path to file

        Returns:
            MarkdownDataContract: The file that was loaded

        """

        def find_first(pattern: _re_pattern, text: str, fallback: str):
            x = pattern.findall(text)
            return x[0] if len(x) >= 1 else fallback

        def find_header(text: str):
            match = _RE_HEADER.search(text)
            return match.group() if match else ""

        md = path.read_text()
        return MarkdownDataContract(
            md=str(find_first(_RE_BODY, md, md)),
            url=str(find_first(_RE_URL, find_header(md), url_prefix + path.as_posix())),
            keywords=str(find_first(_RE_TOPIC, find_header(md), path.name.split(".")[0])),
        )
