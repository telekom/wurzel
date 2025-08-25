# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import logging

from wurzel.utils.splitters.semantic_splitter import DocumentNode, MetaDataDict, SemanticSplitter


def test_cut_off():
    splitter = SemanticSplitter()
    input_text = "This is a very long long text with many many words that produce a lengthy sentence that is the input for the splitter."

    cut_off_text_10 = splitter._cut_to_tokenlen(text=input_text, token_len=10)
    cut_off_text_20 = splitter._cut_to_tokenlen(text=input_text, token_len=20)
    cut_off_text_100 = splitter._cut_to_tokenlen(text=input_text, token_len=100)  # no cut off

    assert cut_off_text_10 == input_text[:44]
    assert cut_off_text_20 == input_text[:100]
    assert cut_off_text_100 == input_text


def test_cut_off_with_returned_discarded_text():
    splitter = SemanticSplitter()
    input_text = "This is a very long long text with many many words that produce a lengthy sentence that is the input for the splitter."

    cut_off_text_10 = splitter._cut_to_tokenlen(text=input_text, token_len=10, return_discarded_text=True)
    cut_off_text_20 = splitter._cut_to_tokenlen(text=input_text, token_len=20, return_discarded_text=True)
    cut_off_text_100 = splitter._cut_to_tokenlen(text=input_text, token_len=100, return_discarded_text=True)  # no cut off

    assert cut_off_text_10[0] == input_text[:44]
    assert cut_off_text_10[1] == input_text[44:]

    assert cut_off_text_20[0] == input_text[:100]
    assert cut_off_text_20[1] == input_text[100:]

    assert cut_off_text_100[0] == input_text
    assert cut_off_text_100[1] == ""


def test_cut_off_logging(caplog):
    # capture logging
    caplog.set_level(logging.WARNING, logger="wurzel.utils.semantic_splitter")

    splitter = SemanticSplitter(token_limit=10)
    input_text = "This is a very long long text with many many words that produce a lengthy sentence that is the input for the splitter."
    input_doc = DocumentNode(text=input_text, metadata=MetaDataDict(keywords="test", url="http://example.com/"))

    cut_off_doc_10 = splitter._md_data_from_dict_cut(doc=input_doc)

    assert cut_off_doc_10.md == input_text[:44]

    # check if logs are correct
    assert caplog.records[0].discarded_text == input_text[44:]
    assert caplog.records[0].text == input_text
