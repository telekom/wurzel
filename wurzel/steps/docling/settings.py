# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

"""Specific docling settings"""

from docling.datamodel.base_models import InputFormat

from wurzel.step import Settings


class DoclingSettings(Settings):
    """settings"""

    FORCE_FULL_PAGE_OCR: bool = True
    FORMATS: list[InputFormat] = [
        "docx",
        "asciidoc",
        "pptx",
        "html",
        "image",
        "pdf",
        "md",
        "csv",
        "xlsx",
        "xml_uspto",
        "xml_jats",
        "json_docling",
    ]
    URLS: list[str] = []
