# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

from logging import getLogger

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
    WordFormatOption,
)
from docling.pipeline.simple_pipeline import SimplePipeline
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

from wurzel.datacontract.common import MarkdownDataContract
from wurzel.step.typed_step import TypedStep

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
            allowed_formats=self.settings.FORMATS,
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline, backend=PyPdfiumDocumentBackend
                ),
                InputFormat.DOCX: WordFormatOption(pipeline_cls=SimplePipeline),
            },
        )

    def run(self, inpt: None) -> list[MarkdownDataContract]:
        """Run the document extraction and conversion process.

        Args:
            inpt (None): Input parameter (not used).

        Returns:
            List[MarkdownDataContract]: List of converted Markdown contracts.
        """
        urls = self.settings.PDF_URLS
        doc_converter = self.create_converter()
        contracts = []
        for url in urls:
            try:
                converted_contract = doc_converter.convert(url)
                md = converted_contract.document.export_to_markdown()
                contract_instance = {"md": md, "keywords": "", "url": url}
                contracts.append(contract_instance)

            except (FileNotFoundError, OSError) as e:
                log.error(f"Failed to verify URL: {url}. Error: {e}")
                continue

        return contracts
