# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""consists of DVCSteps to embedd files and save them as for example as csv."""

# Standard library imports
from logging import getLogger
from typing import TypedDict

import numpy as np
from joblib import Parallel, delayed
from pandera.typing import DataFrame

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import EmbeddingAPIException, SplittException, StepFailed
from wurzel.step import TypedStep
from wurzel.steps.embedding import EmbeddingStep

from .data import EmbeddingMultiVectorResult

# Local application/library specific imports
from .settings import EmbeddingSettings

log = getLogger(__name__)


class _EmbeddedMultiVector(TypedDict):
    """dict definition of a embedded document."""

    text: str
    url: str
    vectors: np.ndarray
    splits: list[str]


class EmbeddingMultiVectorStep(
    EmbeddingStep,
    TypedStep[
        EmbeddingSettings,
        list[MarkdownDataContract],
        DataFrame[EmbeddingMultiVectorResult],
    ],
):
    """Step for consuming list[MarkdownDataContract]
    and returning DataFrame[EmbeddingMultiVectorResult].
    """

    def run(self, inpt: list[MarkdownDataContract]) -> DataFrame[EmbeddingMultiVectorResult]:
        """Executes the embedding step by processing a list of MarkdownDataContract objects,
        generating embeddings for each document, and returning the results as a DataFrame.

        Args:
            inpt (list[MarkdownDataContract]): A list of markdown data contracts to process.

        Returns:
            DataFrame[EmbeddingMultiVectorResult]: A DataFrame containing the embedding results.

        Raises:
            StepFailed: If all input documents fail to generate embeddings.

        Logs:
            - Warnings for documents skipped due to EmbeddingAPIException.
            - A summary warning if some or all documents are skipped.

        """

        def process_document(doc):
            try:
                return self._get_embedding(doc)
            except EmbeddingAPIException as err:
                log.warning(
                    f"Skipped because EmbeddingAPIException: {err.message}",
                    extra={"markdown": str(doc)},
                )
                return None

        results = Parallel(backend="threading", n_jobs=self.settings.N_JOBS)(delayed(process_document)(doc) for doc in inpt)

        rows = [res for res in results if res is not None]
        failed = len(results) - len(rows)

        if failed:
            log.warning(f"{failed}/{len(inpt)} got skipped")
        if failed == len(inpt):
            raise StepFailed(f"All {len(inpt)} embeddings got skipped")

        return DataFrame[EmbeddingMultiVectorResult](DataFrame[EmbeddingMultiVectorResult](rows))

    def _get_embedding(self, doc: MarkdownDataContract) -> _EmbeddedMultiVector:
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

        def prepare_plain(document: MarkdownDataContract) -> str:
            plain_text = self.markdown.convert(document.md)
            plain_text = self._replace_link(plain_text)
            return plain_text

        try:
            splitted_md_rows = self._split_markdown([doc])
        except SplittException as err:
            raise EmbeddingAPIException("splitting failed") from err
        vectors = [self.embedding.embed_query(prepare_plain(split)) for split in splitted_md_rows]
        if not vectors:
            raise EmbeddingAPIException("Embedding failed for all splits")

        context = self.get_simple_context(doc.keywords)

        return {
            "text": doc.md,
            "vectors": vectors,
            "url": doc.url,
            "keywords": context,
            "splits": [split.md for split in splitted_md_rows],
        }
