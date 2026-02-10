# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
# pylint: disable=duplicate-code
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tiktoken
    import transformers

logger = logging.getLogger(__name__)


class Tokenizer(ABC):
    """Abstract base class for text tokenizers.

    This interface provides a common API (`encode`, `decode`) for both
    OpenAI's `tiktoken.Encoding` objects and Hugging Face tokenizers.

    Subclasses must implement `encode` and `decode`.

    The `from_name` class method will attempt to create the correct
    tokenizer type automatically based on the given model or encoding name.
    """

    @abstractmethod
    def encode(self, text: str, **kwargs) -> list[int]:
        """Convert text into a list of token IDs.

        Args:
            text: The input string to tokenize.

        Returns:
            A list of integer token IDs.
        """
        raise NotImplementedError

    @abstractmethod
    def decode(self, tokens: list[int], **kwargs) -> str:
        """Convert a list of token IDs back into a string.

        Args:
            tokens: A list of integer token IDs.

        Returns:
            The decoded string.
        """
        raise NotImplementedError

    def limit_token_count(self, text: str, max_token_count: int, return_discarded_text: bool = False) -> str | tuple[str, str]:
        """Enforces a max. token limit on the input text, i.e., the input text is cut-off at the max. token count.

        Args:
            text (str): The input text of arbitrary length.
            max_token_count (int): The output text has at max. this number of tokens.
            return_discarded_text (bool): If enabled, the function returns also the discarded text (beyond token limit). Defaults to False.

        Returns:
            str | tuple[str, str]: Text limited to max. token count (and the discarded text, depending on `return_discarded_text`)
        """
        input_tokens = self.encode(text)

        output_tokens = input_tokens[:max_token_count]  # ensure token length
        output_text = self.decode(output_tokens)  # convert back to text

        if return_discarded_text:
            discarded_tokens = input_tokens[max_token_count:]  # beyond token length
            discarded_text = self.decode(discarded_tokens)  # convert back to text

            return output_text, discarded_text

        return output_text

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

            tiktoken_installed = True
        except ImportError:
            tiktoken_installed = False

        if tiktoken_installed:
            try:
                # Try name as model name, like "gpt-4o"
                encoding_name = tiktoken.encoding_name_for_model(name)
            except (ValueError, KeyError):
                # Try name as encoding name, like "cl100k_base"
                encoding_name = name

            try:
                # If it's a raw encoding name like "cl100k_base"
                encoding = tiktoken.get_encoding(encoding_name)
                return TiktokenTokenizer(encoding)
            except (ValueError, KeyError):
                logger.warning(f"Tokenizer name '{encoding_name}' is not available with tiktoken, defaulting to HF")
        else:
            logger.warning("Tiktoken is not installed, defaulting to HF")

        # Defaulting to HF tokenizer
        try:
            from transformers import AutoTokenizer  # pylint: disable=import-outside-toplevel

            hf_tok = AutoTokenizer.from_pretrained(name)
            return HFTokenizer(hf_tok)

        except ImportError as e:
            raise RuntimeError(f"Could not load tokenizer '{name}': tiktoken or transformers is not installed.") from e


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
        """
        self._tok = tokenizer

    def encode(self, text: str, **kwargs) -> list[int]:
        """Tokenize text into token IDs."""
        return self._tok.encode(text, **kwargs)

    def decode(self, tokens: list[int], **kwargs) -> str:
        """Convert token IDs back into text."""
        return self._tok.decode(tokens, skip_special_tokens=kwargs.get("skip_special_tokens", True))

    def limit_token_count(self, text: str, max_token_count: int, return_discarded_text: bool = False) -> str | tuple[str, str]:
        """Enforces a max. token limit on the input text, i.e., the input text is cut-off at the max. token count.

        NOTE: The parent method is overloaded since many HF tokenizers change the text when calling decode(encode()).

        Args:
            text (str): The input text of arbitrary length.
            max_token_count (int): The output text has at max. this number of tokens.
            return_discarded_text (bool): If enabled, the function returns also the discarded text (beyond token limit). Defaults to False.

        Returns:
            str | tuple[str, str]: Text limited to max. token count (and the discarded text, depending on `return_discarded_text`)
        """
        tokenizer_out = self._tok(text, return_offsets_mapping=True, return_attention_mask=False, add_special_tokens=False)

        # Check token count of input text
        if len(tokenizer_out["input_ids"]) <= max_token_count:
            # input text already in limit, no change needed
            if return_discarded_text:
                return text, ""

            return text

        # At what string postion does the last token end?
        _, last_token_end = tokenizer_out["offset_mapping"][max_token_count - 1]

        output_text = text[:last_token_end]  # until token length

        if return_discarded_text:
            discarded_text = text[last_token_end:]  # beyond token length

            return output_text, discarded_text

        return output_text
