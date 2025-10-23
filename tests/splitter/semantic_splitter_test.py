# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

import mdformat
import pytest

from tests.splitter import tokenizer_missing
from wurzel.datacontract import MarkdownDataContract
from wurzel.utils.splitters.semantic_splitter import (
    SemanticSplitter,
)

FIXTURES_BASE_PATH = Path(__file__).parent.parent / "data/splitter/semantic_splitter"


@pytest.fixture(scope="function")
def semantic_splitter():
    yield SemanticSplitter()


@pytest.mark.skip(reason="fails currently")  # TODO check why this test fails and fix the code!
@pytest.mark.skipif(tokenizer_missing, reason="tiktoken or transformers not installed")
@pytest.mark.parametrize(
    "fixture_path",
    [
        # pytest.param("long_table", id="Simple long table split"),
        pytest.param("text_with_headings", id="Text with headings"),
    ],
)
def test_from_fixtures(fixture_path, semantic_splitter):
    input_path = FIXTURES_BASE_PATH / fixture_path / "input.md"
    output_paths = sorted((FIXTURES_BASE_PATH / fixture_path).glob("expected_output_*.md"))

    input_text = open(input_path).read()
    expected_output_texts = [open(output_path).read() for output_path in output_paths]

    res = semantic_splitter.split_markdown_document(MarkdownDataContract(md=input_text, url="test", keywords="pytest"))

    # save actual output
    for i, output_text in enumerate(res):
        with open(FIXTURES_BASE_PATH / fixture_path / f"actual_output_{i:03d}.md", "w") as f:
            f.write(output_text.md)

    # number of splits is correct
    assert len(res) == len(expected_output_texts), "incorrect split count"

    for x, expected_output_text in zip(res, expected_output_texts):
        # stripped split content is correct
        assert x.md == mdformat.text(expected_output_text).strip(), "incorrect split content"


@pytest.mark.skipif(tokenizer_missing, reason="tiktoken or transformers not installed")
def test_semantic_splitter_preserves_urls(env):
    env.set("SENTENCE_SPLITTER_MODEL", "regex")

    splitter = SemanticSplitter(
        token_limit=102,
        token_limit_buffer=0,
        token_limit_min=10,
        sentence_splitter_model="regex",
        tokenizer_model="cl100k_base",
    )

    url = "https://docs.example.com/platform/product/overview"
    leading_words = " ".join(f"leading{i}" for i in range(50))
    trailing_words = " ".join(f"trailing{i}" for i in range(50))
    markdown = f"# Product Overview\n\n{leading_words} {url} {trailing_words}"

    doc_contract = MarkdownDataContract(md=markdown, url="test://source", keywords="integration")
    chunks = splitter.split_markdown_document(doc_contract)

    assert any(url in chunk.md for chunk in chunks), "URL missing from all chunks"

    partial_url_chunks = [chunk for chunk in chunks if "https://" in chunk.md and url not in chunk.md]
    assert not partial_url_chunks, "No chunk should contain partial URL fragments"

    for chunk in chunks:
        if "https://" in chunk.md:
            assert url in chunk.md, "URL must remain intact within its chunk"
            if chunk.metadata and "token_len" in chunk.metadata:
                assert chunk.metadata["token_len"] >= splitter.token_limit, "URL completion should not shrink token count"
