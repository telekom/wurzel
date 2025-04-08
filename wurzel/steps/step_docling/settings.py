# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

"""Specific docling settings"""

from docling.datamodel.base_models import InputFormat

from wurzel import Settings


class DoclingSettings(Settings):
    """settings"""

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
    PDF_URLS: list[str] = [
        "https://www.telekom.de/pdf/bedienungsanleitung-bosch-rauchwarnmelder",
        "https://www.telekom.de/pdf/family-card-basic-infos",
        "https://www.telekom.de/pdf/wow-nutzungsbedingungen",
    ]
