# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


import pytest

from wurzel.utils import HAS_SPACY

if not HAS_SPACY:
    pytest.skip("Spacy is not available", allow_module_level=True)

from pathlib import Path

import mdformat

from wurzel.datacontract import MarkdownDataContract
from wurzel.utils.splitters.semantic_splitter import (
    SemanticSplitter,
)

FIXTURES_BASE_PATH = Path(__file__).parent.parent / "data/splitter/table_splitter"


def assert_splitter_outputs(Splitter, fixture_path: Path, save_actual_output: bool = False):
    input_path = fixture_path / "input.md"
    output_paths = sorted(fixture_path.glob("expected_output_*.md"))

    input_text = open(input_path, encoding="utf-8").read()
    expected_output_texts = [open(output_path, encoding="utf-8").read() for output_path in output_paths]

    res = Splitter.split_markdown_document(MarkdownDataContract(md=input_text, url="test", keywords="pytest"))

    # save actual output
    if save_actual_output:
        for p in fixture_path.glob("actual_output_*.md"):
            if p.exists():
                p.unlink()

        for i, output_text in enumerate(res):
            with open(fixture_path / f"actual_output_{i:03d}.md", "w", encoding="utf-8") as f:
                f.write(output_text.md)

    # number of splits is correct
    assert len(res) == len(expected_output_texts), "incorrect split count"

    for x, expected_output_text in zip(res, expected_output_texts):
        # stripped split content is correct
        assert x.md == mdformat.text(expected_output_text).strip(), "incorrect split content"


@pytest.fixture(scope="function")
def Splitter(env):
    yield SemanticSplitter()


@pytest.fixture(scope="function")
def SplitterDontRepeatHeader(env):
    yield SemanticSplitter(repeat_table_header_row=False)


@pytest.mark.parametrize(
    "fixture_path",
    [
        pytest.param("short_table", id="Short table that should not be split"),
        pytest.param("standalone_table", id="Split a markdown file that contains only a table and nothing else"),
        pytest.param("table_and_text", id="Table and text"),
        pytest.param("many_rows_table", id="Long table with multiple row splits"),
        pytest.param("many_columns_table", id="Table with multiple column splits"),
        # TODO Expected output is wrong (not related to table)! See https://github.com/telekom/wurzel/issues/103
        # pytest.param("long_table_and_long_text", id="Table and long text"),
    ],
)
def test_from_fixtures(fixture_path, Splitter):
    assert_splitter_outputs(Splitter, FIXTURES_BASE_PATH / fixture_path, save_actual_output=True)


@pytest.mark.parametrize(
    "fixture_path",
    [
        pytest.param("many_rows_table_dont_repeat_header", id="Long table with multiple row splits, do not repeat header"),
    ],
)
def test_from_fixtures_dont_repeat_header(fixture_path, SplitterDontRepeatHeader):
    assert_splitter_outputs(SplitterDontRepeatHeader, FIXTURES_BASE_PATH / fixture_path, save_actual_output=True)
