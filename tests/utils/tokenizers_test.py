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


@pytest.mark.skipif(tiktoken_missing, reason="tiktoken not installed")
def test_tiktoken_limit_token_count_basic():
    """Test limit_token_count on TiktokenTokenizer."""
    tok = Tokenizer.from_name("gpt2")
    text = "Hello world this is a test"

    # Limit to 2 tokens
    limited_text = tok.limit_token_count(text, max_token_count=2)
    assert len(tok.encode(limited_text)) <= 2
    assert limited_text == "Hello world"


@pytest.mark.skipif(tiktoken_missing, reason="tiktoken not installed")
def test_tiktoken_limit_token_count_with_discarded():
    """Test limit_token_count with return_discarded_text=True."""
    tok = Tokenizer.from_name("gpt2")
    text = "Hello world this is a test"

    # Limit to 2 tokens and get discarded text
    output_text, discarded_text = tok.limit_token_count(text, max_token_count=2, return_discarded_text=True)
    assert len(tok.encode(output_text)) <= 2
    assert discarded_text  # There should be discarded text


@pytest.mark.skipif(transformers_missing, reason="transformers not installed")
def test_hf_limit_token_count_text_already_within_limit():
    """Test HFTokenizer.limit_token_count when text is already within limit."""
    from transformers import AutoTokenizer

    hf = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-large")
    tok = HFTokenizer(hf)

    text = "Hello"
    # High token limit, text should not change
    result = tok.limit_token_count(text, max_token_count=100)
    assert result == text


@pytest.mark.skipif(transformers_missing, reason="transformers not installed")
def test_hf_limit_token_count_text_already_within_limit_with_discarded():
    """Test HFTokenizer.limit_token_count with return_discarded_text when within limit."""
    from transformers import AutoTokenizer

    hf = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-large")
    tok = HFTokenizer(hf)

    text = "Hello"
    output_text, discarded_text = tok.limit_token_count(text, max_token_count=100, return_discarded_text=True)
    assert output_text == text
    assert discarded_text == ""


@pytest.mark.skipif(transformers_missing, reason="transformers not installed")
def test_hf_limit_token_count_exceeds_limit():
    """Test HFTokenizer.limit_token_count when text exceeds token limit."""
    from transformers import AutoTokenizer

    hf = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-large")
    tok = HFTokenizer(hf)

    text = "Hello world this is a longer test string with multiple words"
    # Limit to 5 tokens
    result = tok.limit_token_count(text, max_token_count=5)
    # Result should be shorter than original
    assert len(result) < len(text)


@pytest.mark.skipif(transformers_missing, reason="transformers not installed")
def test_hf_limit_token_count_exceeds_limit_with_discarded():
    """Test HFTokenizer.limit_token_count with return_discarded_text when exceeding limit."""
    from transformers import AutoTokenizer

    hf = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-large")
    tok = HFTokenizer(hf)

    text = "Hello world this is a longer test string with multiple words"
    output_text, discarded_text = tok.limit_token_count(text, max_token_count=5, return_discarded_text=True)
    # Output + discarded should equal original
    assert output_text + discarded_text == text
    assert len(discarded_text) > 0
