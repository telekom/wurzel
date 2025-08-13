# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
import importlib.util

import pytest

from wurzel.utils.sentence_splitter import SentenceSplitter, SpacySentenceSplitter

# Helpers for skip conditions
spacy_missing = importlib.util.find_spec("spacy") is None
spacy_default_model_name = "de_core_news_sm"
spacy_default_model_missing = importlib.util.find_spec(spacy_default_model_name) is None


@pytest.mark.skipif(spacy_missing or spacy_default_model_missing, reason="spacy or model not installed")
def test_from_name_routes_to_spacy():
    splitter = SentenceSplitter.from_name(spacy_default_model_name)
    assert isinstance(splitter, SpacySentenceSplitter)


@pytest.mark.skipif(spacy_missing or spacy_default_model_missing, reason="spacy or model not installed")
def test_spacy_sentence_splitter():
    splitter = SentenceSplitter.from_name(spacy_default_model_name)

    text = "Hello world. Wie gehts?\nWas ist dein Name. #.-"
    sents = splitter.get_sentences(text)

    assert sents == ["Hello world.", "Wie gehts?\n", "Was ist dein Name.", "#.-"]


@pytest.mark.skipif(spacy_missing, reason="spacy not installed")
def test_expection_on_unsupported_splitter_name():
    with pytest.raises(OSError):  # model not found error
        SentenceSplitter.from_name("this-splitter-does-not-exist")
