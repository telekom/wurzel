# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tiktoken
    import transformers


class Tokenizer(ABC):
    """Abstract base class for text tokenizers.

    This interface provides a common API (`encode`, `decode`) for both
    OpenAI's `tiktoken.Encoding` objects and Hugging Face tokenizers.

    Subclasses must implement `encode` and `decode`.

    The `from_name` class method will attempt to create the correct
    tokenizer type automatically based on the given model or encoding name.
    """

    @abstractmethod
    def encode(self, text: str) -> list[int]:
        """Convert text into a list of token IDs.

        Args:
            text: The input string to tokenize.

        Returns:
            A list of integer token IDs.
        """
        raise NotImplementedError

    @abstractmethod
    def decode(self, tokens: list[int]) -> str:
        """Convert a list of token IDs back into a string.

        Args:
            tokens: A list of integer token IDs.

        Returns:
            The decoded string.
        """
        raise NotImplementedError

    @classmethod
    def from_name(cls, name: str) -> "Tokenizer":
        """Instantiate a tokenizer by model or encoding name.

        The method first tries to load an OpenAI tokenizer using
        `tiktoken.encoding_for_model(name)`. If that fails, it falls back
        to loading a Hugging Face tokenizer with
        `transformers.AutoTokenizer.from_pretrained(name)`.

        Args:
            name: Model or encoding name. Can be an OpenAI model (e.g.,
                "gpt-4o", "gpt-3.5-turbo"), an OpenAI encoding name
                (e.g., "cl100k_base"), or a Hugging Face model name
                (e.g., "bert-base-uncased").

        Returns:
            An instance of `TiktokenTokenizer` or `HFTokenizer`.
        """
        try:
            import tiktoken  # pylint: disable=import-outside-toplevel

            # First try by model name
            encoding = tiktoken.encoding_for_model(name)
            return TiktokenTokenizer(encoding)
        except (KeyError, ValueError):
            try:
                # If it's a raw encoding name like "cl100k_base"
                encoding = tiktoken.get_encoding(name)
                return TiktokenTokenizer(encoding)
            except (KeyError, ValueError):
                # Default to HF tokenizer
                from transformers import AutoTokenizer  # pylint: disable=import-outside-toplevel

                hf_tok = AutoTokenizer.from_pretrained(name)
                return HFTokenizer(hf_tok)


class TiktokenTokenizer(Tokenizer):
    """Adapter for OpenAI's `tiktoken.Encoding` tokenizer."""

    def __init__(self, encoding: "tiktoken.core.Encoding"):
        """Initialize a TiktokenTokenizer.

        Args:
            encoding: A `tiktoken.Encoding` instance.
        """
        self._enc = encoding

    def encode(self, text: str, **kwargs) -> list[int]:
        """Tokenize text into token IDs."""
        return self._enc.encode(text, **kwargs)

    def decode(self, tokens: list[int], **kwargs) -> str:
        """Convert token IDs back into text."""
        return self._enc.decode(tokens, **kwargs)


class HFTokenizer(Tokenizer):
    """Adapter for Hugging Face `PreTrainedTokenizerBase` objects."""

    def __init__(self, tokenizer: "transformers.PreTrainedTokenizerBase"):
        """Initialize an HFTokenizer.

        Args:
            tokenizer: A Hugging Face tokenizer instance.
            skip_special_tokens: Whether to remove special tokens during decoding.
        """
        self._tok = tokenizer

    def encode(self, text: str, **kwargs) -> list[int]:
        """Tokenize text into token IDs."""
        return self._tok.encode(text, **kwargs)

    def decode(self, tokens: list[int], **kwargs) -> str:
        """Convert token IDs back into text."""
        return self._tok.decode(tokens, **kwargs)
