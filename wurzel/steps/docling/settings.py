# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

"""Specific docling settings."""

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import AcceleratorDevice, AcceleratorOptions, PdfPipelineOptions
from pydantic import computed_field

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
    DOCLING_PDF_PIPLINE_OPTIONS: PdfPipelineOptions = PdfPipelineOptions(
        accelerator_options=AcceleratorOptions(device=AcceleratorDevice.AUTO)
    )
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

    @computed_field
    @property
    def use_gpu(self) -> bool:
        """Check if GPU is selected for processing.

        Returns:
            bool: True if GPU is selected, False otherwise.

        """
        if self.DOCLING_PDF_PIPLINE_OPTIONS.accelerator_options.device in [AcceleratorDevice.CUDA, AcceleratorDevice.MPS]:
            return True
        return False
