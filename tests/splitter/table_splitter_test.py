# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

import mdformat
import pytest

from wurzel.datacontract import MarkdownDataContract
from wurzel.utils.semantic_splitter import (
    SemanticSplitter,
)

FIXTURES_BASE_PATH = Path(__file__).parent.parent / "data/splitter/table_splitter"


@pytest.fixture(scope="function")
def Splitter(env):
    yield SemanticSplitter()


@pytest.mark.parametrize(
    "fixture_path",
    [
        pytest.param("short_table", id="Short table that should not be split"),
        pytest.param("standalone_table", id="Split a markdown file that contains only a table and nothing else"),
        pytest.param("long_table_and_long_text", id="Table and text"),  # TODO expected output is wrong!
    ],
)
def test_from_fixtures(fixture_path, Splitter):
    input_path = FIXTURES_BASE_PATH / fixture_path / "input.md"
    output_paths = sorted((FIXTURES_BASE_PATH / fixture_path).glob("expected_output_*.md"))

    input_text = open(input_path).read()
    expected_output_texts = [open(output_path).read() for output_path in output_paths]

    res = Splitter.split_markdown_document(MarkdownDataContract(md=input_text, url="test", keywords="pytest"))

    # save actual output
    for i, output_text in enumerate(res):
        with open(FIXTURES_BASE_PATH / fixture_path / f"actual_output_{i:03d}.md", "w") as f:
            f.write(output_text.md)

    # number of splits is correct
    assert len(res) == len(expected_output_texts), "incorrect split count"

    for x, expected_output_text in zip(res, expected_output_texts):
        # stripped split content is correct
        assert x.md == mdformat.text(expected_output_text).strip(), "incorrect split content"
