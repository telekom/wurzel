# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""consists of DVCSteps to embedd files and save them as for example as csv."""

# Standard library imports
import os
import re
from io import StringIO
from logging import getLogger
from pathlib import Path
from typing import Optional, TypedDict

from markdown import Markdown
from pandera.typing import DataFrame
from tqdm.auto import tqdm

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import EmbeddingAPIException, StepFailed
from wurzel.step import TypedStep
from wurzel.steps.embedding.huggingface import HuggingFaceInferenceAPIEmbeddings
from wurzel.steps.splitter import SimpleSplitterStep
from wurzel.utils.semantic_splitter import SemanticSplitter

from .data import EmbeddingResult

# Local application/library specific imports
from .settings import EmbeddingSettings

log = getLogger(__name__)


class Embedded(TypedDict):
    """dict definition of a embedded document."""

    text: str
    url: str
    vector: list[float]


class EmbeddingStep(
    SimpleSplitterStep,
    TypedStep[EmbeddingSettings, list[MarkdownDataContract], DataFrame[EmbeddingResult]],
):
    """Step for consuming list[MarkdownDataContract]
    and returning DataFrame[EmbeddingResult].
    """

    embedding: HuggingFaceInferenceAPIEmbeddings
    n_jobs: int
    markdown: Markdown
    stopwords: list[str]

    def __init__(self) -> None:
        super().__init__()
        self.settings = EmbeddingSettings()
        self.embedding = EmbeddingStep._select_embedding(self.settings.API)
        self.n_jobs = max(1, (os.cpu_count() or 0) - 1)
        # Inject net output_format into 3rd party library Markdown
        Markdown.output_formats["plain"] = EmbeddingStep.__md_to_plain  # type: ignore[index]
        self.markdown = Markdown(output_format="plain")  # type: ignore[arg-type]
        self.markdown.stripTopLevelTags = False
        self.settingstopwords = self._load_stopwords(self.settings.STEPWORDS_PATH)
        self.splitter = SemanticSplitter(
            token_limit=self.settings.TOKEN_COUNT_MAX,
            token_limit_buffer=self.settings.TOKEN_COUNT_BUFFER,
            token_limit_min=self.settings.TOKEN_COUNT_MIN,
        )

    @staticmethod
    def _load_stopwords(path: Path) -> list[str]:
        with path.open(encoding="utf-8") as f:
            stopwords = [w.strip() for w in f.readlines() if not w.startswith(";")]
        return stopwords

    @staticmethod
    def _select_embedding(*args, **kwargs) -> HuggingFaceInferenceAPIEmbeddings:
        """Selects the embedding model to be used for generating embeddings.

        Returns
        -------
        Embeddings
            An instance of the Embeddings class.

        """
        return HuggingFaceInferenceAPIEmbeddings(*args, **kwargs)

    def run(self, inpt: list[MarkdownDataContract]) -> DataFrame[EmbeddingResult]:
        """Executes the embedding step by processing input markdown files, generating embeddings,
        and saving them to a CSV file.
        """
        if len(inpt) == 0:
            log.info("Got empty result in Embedding - Skipping")
            return DataFrame[EmbeddingResult]([])
        splitted_md_rows = self._split_markdown(inpt)
        rows = []
        failed = 0
        for row in tqdm(splitted_md_rows, desc="Calculate Embeddings"):
            try:
                rows.append(self._get_embedding(row))
            except EmbeddingAPIException as err:
                log.warning(
                    f"Skipped because EmbeddingAPIException: {err.message}",
                    extra={"markdown": str(row)},
                )
                failed += 1
        if failed:
            log.warning(f"{failed}/{len(splitted_md_rows)} got skipped")
        if failed == len(splitted_md_rows):
            raise StepFailed(f"all {len(splitted_md_rows)} embeddings got skipped")
        return DataFrame[EmbeddingResult](DataFrame[EmbeddingResult](rows))

    def get_embedding_input_from_document(self, doc: MarkdownDataContract) -> str:
        """Clean the document such that it can be used as input to the embedding model.

        Parameters
        ----------
        doc : MarkdownDataContract
            The document containing the page content in Markdown format.

        Returns
        -------
        str
            Cleaned text that can be used as input to the embedding model.

        """
        plain_text = self.markdown.convert(doc.md)
        plain_text = self._replace_link(plain_text)

        return plain_text

    def _get_embedding(self, doc: MarkdownDataContract) -> Embedded:
        """Generates an embedding for a given text and context.

        Parameters
        ----------
        d : dict
            A dictionary containing the text and context for which to generate the embedding.

        Returns
        -------
        dict
            A dictionary containing the original text, its embedding, and the source URL.

        """
        context = self.get_simple_context(doc.keywords)
        plain_text = self.get_embedding_input_from_document(doc)
        vector = self.embedding.embed_query(plain_text)
        return {"text": doc.md, "vector": vector, "url": doc.url, "keywords": context}

    def is_stopword(self, word: str) -> bool:
        """Stopword Detection Function."""
        return word.lower() in self.settingstopwords

    @classmethod
    def whitespace_word_tokenizer(cls, text: str) -> list[str]:
        """Simple Regex based whitespace word tokenizer."""
        return [x for x in re.split(r"([.,!?]+)?\s+", text) if x]

    def get_simple_context(self, text):
        """Simple function to create a context from a text."""
        tokens = self.whitespace_word_tokenizer(text)
        filtered_tokens = [token for token in tokens if not self.is_stopword(token)]
        return " ".join(filtered_tokens)

    @staticmethod
    def __md_to_plain(element, stream: Optional[StringIO] = None):
        """Converts a markdown element into plain text.

        Parameters
        ----------
        element : Element
            The markdown element to convert.
        stream : StringIO, optional
            The stream to which the plain text is written. If None, a new stream is created.

        Returns
        -------
        str
            The plain text representation of the markdown element.

        """
        if stream is None:
            stream = StringIO()
        if element.text:
            stream.write(element.text)
        for sub in element:
            EmbeddingStep.__md_to_plain(sub, stream)
        if element.tail:
            stream.write(element.tail)
        return stream.getvalue()

    @classmethod
    def _replace_link(cls, text: str):
        """Replaces URLs in the text with a placeholder.

        Parameters
        ----------
        text : str
            The text in which URLs will be replaced.

        Returns
        -------
        str
            The text with URLs replaced by 'LINK'.

        """
        # Extract URL from a string
        url_extract_pattern = (
            "https?:\\/\\/(?:www\\.)?[-a-zA-Z0-9@:%._\\+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\\b(?:[-a-zA-Z0-9()@:%_\\+.~#?&\\/=]*)"  # pylint: disable=line-too-long
        )
        links = sorted(re.findall(url_extract_pattern, text), key=len, reverse=True)
        for link in links:
            text = text.replace(link, "LINK")
        return text
