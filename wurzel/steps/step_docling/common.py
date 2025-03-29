# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
# pylint: disable=R0801
from pathlib import Path
from re import Pattern as _re_pattern
from re import compile as _re_compile
from typing import Self

from docling.document_converter import DocumentConverter

from wurzel.datacontract import PydanticModel

_RE_TOPIC = _re_compile(r"topics:\s*(.*)")
_RE_URL = _re_compile(r"url:\s*(.*)")
_RE_BODY = _re_compile(r"---[\s\S]*?---\s*([\s\S]*)")


class MarkdownDataContract(PydanticModel):
    """contract of the input of the EmbeddingStep"""

    md: str
    keywords: str
    url: str

    @classmethod
    def from_docling_file(
        cls, contract: DocumentConverter, paths: Path, url_prefix: str = ""
    ) -> Self:
        """
        Creates a `MarkdownDataContract` instance from a file.
        """

        md = contract.document.export_to_markdown()

        def find_first(pattern: _re_pattern, text: str, fallback: str):
            x = pattern.findall(text)
            return x[0] if len(x) >= 1 else fallback

        return MarkdownDataContract(
            md=str(find_first(_RE_BODY, md, md)),
            url=str(find_first(_RE_URL, md, url_prefix + paths.as_posix())),
            keywords=str(find_first(_RE_TOPIC, md, paths.name.split(".")[0])),
        )
