# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

"""Specific docling settings."""

from docling.datamodel.base_models import InputFormat

from wurzel.step import Settings


class DoclingSettings(Settings):
    """DoclingSettings is a configuration class that inherits from the base `Settings` class.
    It provides customizable settings for document processing.

    Attributes:
        FORCE_FULL_PAGE_OCR (bool): A flag to enforce full-page OCR processing. Defaults to True.
        FORMATS (list[InputFormat]): A list of supported input formats for document processing.
            Supported formats include:
            - "docx"
            - "asciidoc"
            - "pptx"
            - "html"
            - "image"
            - "pdf"
            - "md"
            - "csv"
            - "xlsx"
            - "xml_uspto"
            - "xml_jats"
            - "json_docling"
        URLS (list[str]): A list of URLs for additional configuration or resources. Defaults to an empty list.

    """

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
