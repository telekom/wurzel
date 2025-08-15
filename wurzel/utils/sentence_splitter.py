# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
import logging
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import spacy

logger = logging.getLogger(__name__)


class SentenceSplitter(ABC):
    """Abstract base class for sentence splitter.

    This interface provides a common API (`get_sentences`) for sentence splitters.

    Current implementations:
    - Regex
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
        """Instantiate a sentence splitter based on a given name.

        Args:
            name: Model name. Can be an Spacy model (e.g.,
                "en_core_web_sm", "xx_ent_wiki_sm"), or "regex" ...

        Returns:
            An instance of `SentenceSplitter`.
        """
        if name == "regex":
            return RegexSentenceSplitter()

        # Try to load a Spacy model
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


class RegexSentenceSplitter(SentenceSplitter):
    """A sentence splitter based on regular expressions.

    Heuristics:
    - Split after sentence-ending punctuation (. ! ? …) and any closing quotes/brackets.
    - Only split if the next non-space token *looks* like a sentence start
      (capital letter or digit, optionally after an opening quote/paren).
    - Merge back false positives caused by common abbreviations, initials,
      dotted acronyms (e.g., U.S.), decimals (e.g., 3.14), ordinals (No. 5), and ellipses.

    Notes:
    - Tweak `self.abbreviations` for your domain/corpus.
    - For chatty/poetic text where sentences may start lowercase, relax
      `self._split_re`'s lookahead (see comment in __init__).
    """

    def __init__(self):
        """Initialize a regex sentence splitter (compile regex, set abbreviations)."""
        self._split_re = re.compile(
            r"(?<=[.!?…])"  # fixed-width lookbehind (only punctuation)
            r'(?:[\'")\]]*)'  # match any closing quotes/brackets (no lookbehind)
            r'(?=\s+(?=[“"\'(\[]?[A-Z0-9]))'
        )

        self.abbreviations: set[str] = {
            "mr",
            "mrs",
            "ms",
            "dr",
            "prof",
            "sr",
            "jr",
            "sir",
            "madam",
            "st",
            "a.m",
            "p.m",
            "etc",
            "e.g",
            "i.e",
            "vs",
            "cf",
            "al",
            "ca",
            "resp",
            "jan",
            "feb",
            "mar",
            "apr",
            "jun",
            "jul",
            "aug",
            "sep",
            "sept",
            "oct",
            "nov",
            "dec",
            "no",
            "dept",
            "fig",
            "eq",
            "inc",
            "ltd",
        }

        # All other regex patterns grouped in one dict
        self._patterns: dict[str, re.Pattern] = {
            "ends_with_initials": re.compile(r"(?:\b[A-Z]\.){1,3}\s*$"),
            "ends_with_acronym": re.compile(r"(?:\b[A-Z]\.){2,}\s*$"),
            "ends_with_decimal": re.compile(r"\d\.\d+\s*$"),
            "ends_with_ellipsis": re.compile(r"\.\.\.\s*$"),
            "ends_with_ordinal": re.compile(r"\bNo\.\s*\d+\s*$", re.I),
            "trail_word_before_dot": re.compile(r"([^\W\d_]+)\.\s*$", re.UNICODE),
        }

    def _ends_with_known_abbrev(self, chunk: str) -> bool:
        m = self._patterns["trail_word_before_dot"].search(chunk.rstrip())
        return bool(m and m.group(1).lower() in self.abbreviations)

    def _should_merge_with_next(self, chunk: str) -> bool:
        chunk = chunk.rstrip()
        return self._ends_with_known_abbrev(chunk) or any(
            self._patterns[name].search(chunk)
            for name in [
                "ends_with_initials",
                "ends_with_acronym",
                "ends_with_decimal",
                "ends_with_ellipsis",
                "ends_with_ordinal",
            ]
        )

    def get_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        if not text:
            return []

        normalized = re.sub(r"[ \t]*\n[ \t]*", " ", text.strip())
        parts = self._split_re.split(normalized)

        sentences: list[str] = []
        for part in parts:
            if not part:
                continue
            if not sentences:
                sentences.append(part)
                continue
            if self._should_merge_with_next(sentences[-1]):
                sentences[-1] = sentences[-1].rstrip() + " " + part.lstrip()
            else:
                sentences.append(part)

        return [s.strip() for s in sentences if s.strip()]
