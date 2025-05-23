# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0


import pytest

from wurzel.utils import HAS_DOCLING

from .conftest import skip_if_mac_os_and_github_action  # noqa: F401

if not HAS_DOCLING:
    pytest.skip("Docling is not available", allow_module_level=True)
from wurzel.steps.docling.docling_step import CleanMarkdownRenderer, DoclingStep


@pytest.mark.parametrize(
    "real_data_path, expected_md_start, expected_contract_count",
    [
        (
            ["https://pdfobject.com/pdf/sample.pdf"],
            "## Sample PDF\n\n## This is a simple PDF file. Fun fun fun.\n\nLorem ipsum dolor sit amet,  consectetuer",
            1,
        ),
        (["example.com/pdf"], "", 0),
    ],
)
def test_docling_step(real_data_path, expected_md_start, expected_contract_count, skip_if_mac_os_and_github_action):  # noqa: F811
    docling_step = DoclingStep()
    docling_step.settings = type(
        "Settings",
        (object,),
        {
            "URLS": real_data_path,
            "FORCE_FULL_PAGE_OCR": docling_step.settings.FORCE_FULL_PAGE_OCR,
            "FORMATS": docling_step.settings.FORMATS,
            "DEFAULT_KEYWORD": "",
        },
    )

    contracts = docling_step.run({})
    assert len(contracts) == expected_contract_count, f"Expected {expected_contract_count} contracts, got {len(contracts)}"
    if contracts:
        actual_md = contracts[0]["md"].strip()
        assert actual_md.startswith(expected_md_start), "Markdown content does not match expected start."


def test_render_html_block_removes_image_tag():
    class DummyToken:
        def __init__(self, content):
            self.content = content

    token_with_image = DummyToken("<!-- image --> text for this contract")
    token_without_image = DummyToken("<div>Real content</div>")

    assert CleanMarkdownRenderer.render_html_block(token_with_image) == "text for this contract"
    assert CleanMarkdownRenderer.render_html_block(token_without_image) == "<div>Real content</div>"
