# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

import unittest

from wurzel.steps.step_docling.docling_step import DoclingStep


class TestDoclingStepWithRealPath(unittest.TestCase):
    def setUp(self):
        """Set up the test with a real path and expected output file."""
        self.real_data_path = ["https://www.telekom.de/pdf/family-card-basic-infos"]
        # Instantiate DoclingStep with real settings
        self.docling_step = DoclingStep()
        self.docling_step.settings = type(
            "Settings",
            (object,),
            {
                "URLS": self.real_data_path,
                "FORCE_FULL_PAGE_OCR": self.docling_step.settings.FORCE_FULL_PAGE_OCR,
                "FORMATS": self.docling_step.settings.FORMATS,
            },
        )

    def test_run_docling(self):
        """Test run() with real data and compare with expected output."""

        contracts = self.docling_step.run({})
        self.assertGreater(len(contracts), 0, "No contracts were generated.")
        actual_md = contracts[0]["md"].strip()
        self.assertTrue(
            actual_md.startswith(
                "PRAKTISCHE INFORMATIONEN ZU IHRER FAMILY CARD BASIC Lieber Telekom Kunde; schön, dass Sie sich für Family Card Basic entschieden haben. Ihre Ei"
            )
        )
