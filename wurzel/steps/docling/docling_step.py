# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

"""Note: Known Limitations with EasyOCR (`EasyOcrOptions`).

1. Table structure is often lost or misaligned in the OCR output.
2. Spelling inaccuracies are occasionally observed (e.g., "Verlängern" → "Verlängenng").
3. URLs are not parsed correctly (e.g., "www.telekom.de/agb" → "www telekom delagb").

While investigating EasyOCR issues and testing alternative OCR engines,
we observed that some documents produced distorted text with irregular whitespace.
This disrupts the natural sentence flow and significantly reduces readability.

Example:
"pra kti sche  i nform ati o nen zu  i h rer  fam i l y  card  basi c Li eber
  Tel ekom   Kunde, schön,   dass  Si e  si ch  f ür..."

Despite these limitations, we have decided to proceed with EasyOCR.

"""

from logging import getLogger

from bs4 import BeautifulSoup, Comment
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import EasyOcrOptions, PdfPipelineOptions
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
)
from mistletoe import Document, HTMLRenderer

from wurzel.datacontract.common import MarkdownDataContract
from wurzel.step.typed_step import TypedStep

from .settings import DoclingSettings

log = getLogger(__name__)


class CleanMarkdownRenderer(HTMLRenderer):
    """Custom Markdown renderer extending mistletoe's HTMLRenderer to clean up
    unwanted elements from Markdown input.
    """

    @staticmethod
    def render_html_block(token):
        """Render HTML block tokens and clean up unwanted elements.

        This method removes HTML comments and returns the cleaned HTML content.
        Remove comments like <!-- image -->
        """
        soup = BeautifulSoup(token.content, "html.parser")

        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        return soup.decode_contents().strip()


class DoclingStep(TypedStep[DoclingSettings, None, list[MarkdownDataContract]]):
    """Step to return local Markdown files with enhanced PDF extraction for German."""

    def __init__(self):
        super().__init__()
        self.converter = self.create_converter()

    def create_converter(self) -> DocumentConverter:
        """Create and configure the document converter for PDF and DOCX.

        Returns:
            DocumentConverter: Configured document converter.

        """
        pipeline_options = PdfPipelineOptions()
        ocr_options = EasyOcrOptions(force_full_page_ocr=self.settings.FORCE_FULL_PAGE_OCR)
        pipeline_options.ocr_options = ocr_options

        return DocumentConverter(
            allowed_formats=self.settings.FORMATS,
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                )
            },
        )

    @staticmethod
    def clean_markdown_with_mistletoe(md_text: str) -> tuple[str, str]:
        """Cleans a Markdown string using mistletoe and extracts useful content.

        - Parses and renders the Markdown content into HTML using a custom HTML renderer
        - Removes unwanted HTML comments and escaped underscores
        - Extracts the first heading from the content (e.g., `<h1>` to `<h6>`)
        - Converts the cleaned HTML into plain text

        Args:
            md_text (str): The raw Markdown input string.

        """
        with CleanMarkdownRenderer() as renderer:
            ast = Document(md_text)
            cleaned = renderer.render(ast).replace("\n", "")
            soup = BeautifulSoup(cleaned, "html.parser")
            first_heading_tag = soup.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            heading = first_heading_tag.get_text(strip=True) if first_heading_tag else ""
            plain_text = soup.get_text(separator=" ").strip()
            return heading, plain_text

    def run(self, inpt: None) -> list[MarkdownDataContract]:
        """Run the document extraction and conversion process for German PDFs.

        Args:
            inpt (None): Input parameter (not used).

        Returns:
            List[MarkdownDataContract]: List of converted Markdown contracts.

        """
        urls = self.settings.URLS
        contracts = []

        for url in urls:
            try:
                converted_contract = self.converter.convert(url)
                md = converted_contract.document.export_to_markdown()
                keyword, cleaned_md = self.clean_markdown_with_mistletoe(md)
                contract_instance = {"md": cleaned_md, "keywords": keyword, "url": url}
                contracts.append(contract_instance)

            except (FileNotFoundError, OSError) as e:
                log.error(f"Failed to verify URL: {url}. Error: {e}")
                continue

        return contracts
