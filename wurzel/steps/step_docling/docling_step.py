# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

from logging import getLogger
from pathlib import Path

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

    def get_paths(self) -> list[Path]:
        """Retrieve all Markdown file paths.

        Returns:
            List[Path]: List of valid file paths.

        """
        path = Path(self.settings.FILE_PATHS)

        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"Invalid path: {path}")

        files = [file for file in path.iterdir() if file.is_file()]
        if not files:
            raise ValueError(f"No valid files found in {path}")

        return files

    def create_converter(self) -> DocumentConverter:
        """Create and configure the document converter.

        Returns:
            DocumentConverter: Configured document converter.
        """
        return DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.IMAGE,
                InputFormat.DOCX,
                InputFormat.HTML,
                InputFormat.PPTX,
                InputFormat.ASCIIDOC,
                InputFormat.CSV,
                InputFormat.MD,
            ],
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
        files = self.get_paths()
        doc_converter = self.create_converter()
        contracts = [
            MarkdownDataContract.from_docling_file(
                doc_converter.convert_all([file]), file
            )
            for file in files
        ]

        return contracts
