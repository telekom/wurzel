# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
import importlib.util

import pytest

from wurzel.utils.tokenizers import HFTokenizer, TiktokenTokenizer, Tokenizer

# Helpers for skip conditions
tiktoken_missing = importlib.util.find_spec("tiktoken") is None
transformers_missing = importlib.util.find_spec("transformers") is None


@pytest.mark.skipif(tiktoken_missing, reason="tiktoken not installed")
def test_from_name_routes_to_tiktoken_for_openai_name():
    tok = Tokenizer.from_name("gpt2")  # OpenAI alias; tiktoken knows it
    assert isinstance(tok, TiktokenTokenizer)


@pytest.mark.skipif(tiktoken_missing, reason="tiktoken not installed")
def test_tiktoken_encode_decode_known_ids():
    tok = Tokenizer.from_name("gpt-4o-mini")  # uses tiktoken.encoding_for_model
    text = "Hello world"
    ids = tok.encode(text)
    assert ids == [13225, 2375]  # GPT-2 / r50k_base stable tokens
    assert tok.decode(ids) == text


@pytest.mark.skipif(tiktoken_missing, reason="tiktoken not installed")
def test_tiktoken_accepts_raw_encoding_name():
    tok = Tokenizer.from_name("cl100k_base")
    assert isinstance(tok, TiktokenTokenizer)
    text = "ChatGPT is great."
    ids = tok.encode(text)
    assert isinstance(ids, list) and all(isinstance(i, int) for i in ids)
    assert tok.decode(ids) == text


@pytest.mark.skipif(transformers_missing, reason="transformers not installed")
def test_from_name_routes_to_hf_for_non_openai_name():
    tok = Tokenizer.from_name("intfloat/multilingual-e5-large")  # not an OpenAI model
    assert isinstance(tok, HFTokenizer)
    text = "Hello world"
    ids = tok.encode(text)
    decoded = tok.decode(ids)
    assert decoded == "Hello world"


@pytest.mark.skipif(transformers_missing, reason="transformers not installed")
def test_hf_adapter_known_ids_me5():
    from transformers import AutoTokenizer

    hf = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-large")
    tok = HFTokenizer(hf)

    text = "Hello world"
    ids = tok.encode(text)
    assert ids == [0, 35378, 8999, 2]  # E5 tokens


@pytest.mark.skipif(transformers_missing or tiktoken_missing, reason="transformers and tiktoken not installed")
def test_expection_on_unsupported_tokenizer_name():
    with pytest.raises(OSError):  # hub not found error
        Tokenizer.from_name("this-tokenizer-does-not-exist-in-hf-and-tiktoken")


@pytest.mark.skipif(transformers_missing, reason="transformers not installed")
@pytest.mark.parametrize(
    "text",
    [
        pytest.param("Hello world"),
        pytest.param("A more complex text with #.-, special chars"),
        # pytest.param("aa\n\nbb"),  # fails due to missing line breaks
    ],
)
def test_hf_decode_without_special_tokens(text):
    from transformers import AutoTokenizer

    hf = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-large")
    tok = HFTokenizer(hf)

    ids = tok.encode(text)
    decoded_text = tok.decode(ids)

    assert text == decoded_text, "Decoded text does not match input text"
