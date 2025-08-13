# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import spacy

logger = logging.getLogger(__name__)


class SentenceSplitter(ABC):
    """Abstract base class for sentence splitter.

    This interface provides a common API (`get_sentences`) for sentence splitters.

    Current implementations:
    - Spacy (https://spacy.io/usage/models)

    Subclasses must implement `get_sentences`.

    The `from_name` class method will attempt to create the correct
    spliter type automatically based on the given model name.
    """

    @abstractmethod
    def get_sentences(self, text: str) -> list[str]:
        """Convert text into a list of sentences.

        Args:
            text: The input string to split.

        Returns:
            A list of sentences.
        """
        raise NotImplementedError

    @classmethod
    def from_name(cls, name: str) -> "SentenceSplitter":
        """Instantiate a tokenizer by model or encoding name.

        The method first tries to load an Spacy model using
        `tiktoken.encoding_for_model(name)`. If that fails, it falls back
        to loading a Hugging Face tokenizer with
        `transformers.AutoTokenizer.from_pretrained(name)`.

        Args:
            name: Model name. Can be an Spacy model (e.g.,
                "en_core_web_sm", "xx_ent_wiki_sm"), or ...

        Returns:
            An instance of `SpacySentenceSplitter`.
        """
        try:
            import spacy  # pylint: disable=import-outside-toplevel

            # Try Spacy model name, like "en_core_web_sm"
            nlp = spacy.load(name)

            return SpacySentenceSplitter(nlp)
        except (ValueError, KeyError) as e:
            raise ValueError(f"Sentence splitter '{name}' is not available with SpaCy") from e

        except ImportError as e:
            raise RuntimeError(f"Could not load sentence splitter '{name}': spacy is not installed.") from e


class SpacySentenceSplitter(SentenceSplitter):
    """Adapter for Spacy sentence splitter."""

    def __init__(self, nlp: "spacy.language.Language"):
        """Initialize a SpacySentenceSplitter.

        Args:
            nlp: A Spacy model from spacy.load().
        """
        self._nlp = nlp

    def get_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        return [sentence_span.text for sentence_span in self._nlp(text).sents]
