# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""consists of DVCSteps to embedd files and save them as for example as csv."""

# Standard library imports
import os
import re
from collections import defaultdict
from io import StringIO
from logging import getLogger
from typing import Optional, TypedDict

import numpy as np
from markdown import Markdown
from pandera.typing import DataFrame
from tqdm.auto import tqdm

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import EmbeddingAPIException, StepFailed
from wurzel.step import TypedStep
from wurzel.steps.data import EmbeddingResult
from wurzel.steps.embedding.huggingface import HuggingFaceInferenceAPIEmbeddings, PrefixedAPIEmbeddings
from wurzel.steps.splitter import SimpleSplitterStep
from wurzel.utils.tokenizers import Tokenizer

# Local application/library specific imports
from .settings import EmbeddingSettings

log = getLogger(__name__)


class Embedded(TypedDict):
    """dict definition of a embedded document."""

    text: str
    url: str
    vector: list[float]


class BaseEmbeddingStep(TypedStep[EmbeddingSettings, list[MarkdownDataContract], DataFrame[EmbeddingResult]]):
    """Parent class for embedding-related steps implementing common methods."""

    embedding: HuggingFaceInferenceAPIEmbeddings
    n_jobs: int
    markdown: Markdown
    stopwords: list[str]
    settings: EmbeddingSettings

    def __init__(self) -> None:
        super().__init__()
        self.embedding = self._select_embedding()
        self.n_jobs = max(1, (os.cpu_count() or 0) - 1)
        # Inject net output_format into 3rd party library Markdown
        Markdown.output_formats["plain"] = self.__md_to_plain  # type: ignore[index]
        self.markdown = Markdown(output_format="plain")  # type: ignore[arg-type]
        self.markdown.stripTopLevelTags = False
        self.stopwords = self._load_stopwords()

    def _load_stopwords(self) -> list[str]:
        """Load stopwords from path (stop words are used by `get_simple_context`)."""
        path = self.settings.STEPWORDS_PATH
        with path.open(encoding="utf-8") as f:
            stopwords = [w.strip() for w in f.readlines() if not w.startswith(";")]
        return stopwords

    def _select_embedding(self) -> HuggingFaceInferenceAPIEmbeddings:
        """Selects the embedding model to be used for generating embeddings.

        Returns:
        -------
        Embeddings
            An instance of the Embeddings class.

        """
        return PrefixedAPIEmbeddings(self.settings.API, self.settings.PREFIX_MAP)

    def log_statistics(self, series: np.ndarray, name: str):
        """Log descriptive statistics for all documents.

        Parameters
        ----------
        series : np.ndarray
            Numerical values representing the documents.
        name : str
            The name of the document metric.
        """
        stats = {
            "count": len(series),
            "mean": None,
            "std": None,
        }

        if len(series) > 0:
            stats.update(
                {
                    "mean": np.mean(series),
                    "median": np.median(series),
                    "std": np.std(series),
                    "var": np.var(series),
                    "min": np.min(series),
                    "percentile_5": np.percentile(series, 5),
                    "percentile_25": np.percentile(series, 25),
                    "percentile_75": np.percentile(series, 75),
                    "percentile_95": np.percentile(series, 95),
                    "max": np.max(series),
                }
            )

        log.info(f"Distribution of {name}: count={stats['count']}; mean={stats['mean']}; std={stats['std']}", extra=stats)

    def get_embedding_input_from_document(self, doc: MarkdownDataContract) -> str:
        """Clean the document such that it can be used as input to the embedding model.

        Parameters
        ----------
        doc : MarkdownDataContract
            The document containing the page content in Markdown format.

        Returns:
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

        Returns:
        -------
        dict
            A dictionary containing the original text, its embedding, and the source URL.

        """
        context = self.get_simple_context(doc.keywords)
        text = self.get_embedding_input_from_document(doc) if self.settings.CLEAN_MD_BEFORE_EMBEDDING else doc.md
        vector = self.embedding.embed_query(text)
        return {"text": doc.md, "vector": vector, "url": doc.url, "keywords": context, "embedding_input_text": text}

    def is_stopword(self, word: str) -> bool:
        """Stopword Detection Function."""
        return word.lower() in self.stopwords

    @classmethod
    def whitespace_word_tokenizer(cls, text: str) -> list[str]:
        """Simple Regex based whitespace word tokenizer."""
        return [x for x in re.split(r"([.,!?]+)?\s+", text) if x]

    def get_simple_context(self, text):
        """Simple function to create a context from a text."""
        tokens = self.whitespace_word_tokenizer(text)
        filtered_tokens = [token for token in tokens if not self.is_stopword(token)]
        return " ".join(filtered_tokens)

    @classmethod
    def __md_to_plain(cls, element, stream: Optional[StringIO] = None):
        """Converts a markdown element into plain text.

        Parameters
        ----------
        element : Element
            The markdown element to convert.
        stream : StringIO, optional
            The stream to which the plain text is written. If None, a new stream is created.

        Returns:
        -------
        str
            The plain text representation of the markdown element.

        """
        if stream is None:
            stream = StringIO()
        if element.text:
            stream.write(element.text)
        for sub in element:
            cls.__md_to_plain(sub, stream)
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

        Returns:
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

    def preprocess_inputs(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Custom preprocessing of inputs (called by `run` before embedding calculation)."""
        raise NotImplementedError

    def run(self, inpt: list[MarkdownDataContract]) -> DataFrame[EmbeddingResult]:
        """Executes the embedding step by processing input markdown files, generating embeddings,
        and saving them to a CSV file.
        """
        if len(inpt) == 0:
            log.info("Got empty result in Embedding - Skipping")
            return DataFrame[EmbeddingResult]([])

        preprocessed_inputs = self.preprocess_inputs(inpt)

        output_rows = []
        failed = 0
        stats = defaultdict(list)

        for input_row in tqdm(preprocessed_inputs, desc="Calculate Embeddings"):
            try:
                output_rows.append(self._get_embedding(input_row))

                # collect statistics
                if input_row.metadata is not None:
                    stats["char length"].append(input_row.metadata.get("char_len", 0))
                    stats["token length"].append(input_row.metadata.get("token_len", 0))
                    stats["chunks count"].append(input_row.metadata.get("chunks_count", 0))

            except EmbeddingAPIException as err:
                log.warning(
                    f"Skipped because EmbeddingAPIException: {err.message}",
                    extra={"markdown": str(input_row)},
                )
                failed += 1
        if failed:
            log.warning(f"{failed}/{len(preprocessed_inputs)} got skipped")
        if failed == len(preprocessed_inputs):
            raise StepFailed(f"all {len(preprocessed_inputs)} embeddings got skipped")

        # log statistics
        for k, v in stats.items():
            self.log_statistics(series=np.array(v), name=k)

        return DataFrame[EmbeddingResult](output_rows)


class EmbeddingStep(BaseEmbeddingStep, SimpleSplitterStep):
    """Step for consuming list[MarkdownDataContract] and returning DataFrame[EmbeddingResult].

    This step inherits both from BaseEmbeddingStep and SimpleSplitterStep, meaning that
    inputs are first splitted and then embeddings of the splits are generated.

    TODO Due to this, a better name of this step would be "EmbeddingSplitterStep", but keeping the name to avoid breaking changes.
    """

    def preprocess_inputs(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Split inputs into chunks (called by `run` before embedding calculation)."""
        return self._split_markdown(inpt)


class TruncatedEmbeddingStep(BaseEmbeddingStep):
    """Step for consuming list[MarkdownDataContract] and returning DataFrame[EmbeddingResult].

    In contrast to `EmbeddingStep`, this step does not perform any splitting but instead the
    steps truncates all inputs such that the max. token count is fulfiled.
    """

    def __init__(self) -> None:
        super().__init__()

        self.tokenizer = Tokenizer.from_name(self.settings.TOKENIZER_MODEL)

    def preprocess_inputs(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """No custom processing is performed."""
        return inpt

    def get_embedding_input_from_document(self, doc: MarkdownDataContract) -> str:
        """Clean the document and truncate it to max. token count such that it can be used as input to the embedding model.

        The setting `CLEAN_MD_BEFORE_EMBEDDING` must be enabled.

        Parameters
        ----------
        doc : MarkdownDataContract
            The document containing the page content in Markdown format.

        Returns:
        -------
        str
            Cleaned and truncated text that can be used as input to the embedding model.

        """
        plain_text = super().get_embedding_input_from_document(doc)

        token_ids = self.tokenizer.encode(plain_text)

        if len(token_ids) > self.settings.TOKEN_COUNT_MAX:
            log.warning(
                "Truncating %i tokens from embedding input text: %i input tokens > %i max tokens",
                len(token_ids) - self.settings.TOKEN_COUNT_MAX,
                len(token_ids),
                self.settings.TOKEN_COUNT_MAX,
                extra={
                    "text": plain_text,
                    "input_token_count": len(token_ids),
                    "max_token_count": self.settings.TOKEN_COUNT_MAX,
                },
            )

            token_ids = token_ids[: self.settings.TOKEN_COUNT_MAX]

        return self.tokenizer.decode(token_ids)
