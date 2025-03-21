# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

"""Specific docling settings"""

from wurzel import Settings


class DoclingSettings(Settings):
    "Docling settings"

    FILE_PATHS: str = "data"
