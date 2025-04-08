# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

import json
import unittest
from pathlib import Path

from wurzel.steps.step_docling.docling_step import DoclingStep


class TestDoclingStepWithRealPath(unittest.TestCase):
    def setUp(self):
        """Set up the test with a real path and expected output file."""
        self.real_data_path = ["https://www.telekom.de/pdf/family-card-basic-infos"]
        self.expected_output_file = Path("tests/data/docling/expected_output.json")

        # Instantiate DoclingStep with real settings
        self.docling_step = DoclingStep()
        self.docling_step.settings = type(
            "Settings",
            (object,),
            {
                "PDF_URLS": self.real_data_path,
                "FORMATS": [
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
                ],
            },
        )

    def test_run_docling(self):
        """Test run() with real data and compare with expected output."""

        contracts = self.docling_step.run({})

        self.assertGreater(len(contracts), 0, "No contracts were generated.")
        with self.expected_output_file.open("r") as expected_file:
            expected_content = json.load(expected_file)

        actual_content = [
            {
                "md": contract["md"],
                "keywords": contract["keywords"],
                "url": contract["url"],
            }
            for contract in contracts
        ]

        self.assertEqual(
            actual_content,
            expected_content,
            "The actual output does not match the expected output.",
        )
