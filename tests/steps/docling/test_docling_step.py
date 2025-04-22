# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

import pytest

from wurzel.steps.step_docling.docling_step import DoclingStep


@pytest.mark.parametrize(
    "real_data_path, expected_md_start, expected_contract_count",
    [
        (
            ["https://pdfobject.com/pdf/sample.pdf"],
            "Samole PDF This is a simple PDF file. Fun fun fun: Lorem ipsum dolor sit amet;",
            1,
        ),
        (["example.com/pdf"], "", 0),
    ],
)
def test_docling_step(
    real_data_path, expected_md_start, expected_contract_count
):
    docling_step = DoclingStep()
    docling_step.settings = type(
        "Settings",
        (object,),
        {
            "URLS": real_data_path,
            "FORCE_FULL_PAGE_OCR": docling_step.settings.FORCE_FULL_PAGE_OCR,
            "FORMATS": docling_step.settings.FORMATS,
        },
    )

    contracts = docling_step.run({})
    assert len(contracts) == expected_contract_count, (
        f"Expected {expected_contract_count} contracts, got {len(contracts)}"
    )
    if contracts:
        actual_md = contracts[0]["md"].strip()
        assert actual_md.startswith(expected_md_start), (
            "Markdown content does not match expected start."
        )
