# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

from logging import getLogger
from pathlib import Path

import requests
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
    WordFormatOption,
)
from docling.pipeline.simple_pipeline import SimplePipeline
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

from wurzel.step.typed_step import TypedStep

from .common import MarkdownDataContract
from .settings import DoclingSettings

log = getLogger(__name__)


class DoclingStep(TypedStep[DoclingSettings, None, list[MarkdownDataContract]]):
    """Step to return local Markdown files."""

    def create_converter(self) -> DocumentConverter:
        """Create and configure the document converter.

        Returns:
            DocumentConverter: Configured document converter.
        """
        return DocumentConverter(
            allowed_formats=self.settings.FORMATE,
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline, backend=PyPdfiumDocumentBackend
                ),
                InputFormat.DOCX: WordFormatOption(pipeline_cls=SimplePipeline),
            },
        )

    def validate_urls(self, urls: list[str]) -> list[str]:
        """Validate URLs by checking their availability.

        Args:
            urls (List[str]): List of URLs to validate.

        Returns:
            List[str]: List of valid URLs.
        """
        valid_urls = []
        for url in set(urls):
            try:
                response = requests.head(url, timeout=5)
                if response.status_code == 200:
                    valid_urls.append(url)
            except requests.RequestException as e:
                log.error(f"Failed to verify URL: {url}. Error: {e}")
        return valid_urls

    def run(self, inpt: None) -> list[MarkdownDataContract]:
        """Run the document extraction and conversion process.

        Args:
            inpt (None): Input parameter (not used).

        Returns:
            List[MarkdownDataContract]: List of converted Markdown contracts.
        """

        files = self.settings.FILE_LINK
        valid_urls = self.validate_urls(files)

        doc_converter = self.create_converter()
        contracts = [
            MarkdownDataContract.from_docling_file(
                doc_converter.convert(file), Path(file)
            )
            for file in valid_urls
        ]

        return contracts
