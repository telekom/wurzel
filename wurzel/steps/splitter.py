# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""consists of DVCSteps to embedd files and save them as for example as csv."""

# Standard library imports
from logging import getLogger

from joblib import Parallel, delayed
from pydantic import Field

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import MarkdownException, SplittException
from wurzel.step import Settings, TypedStep
from wurzel.utils.semantic_splitter import SemanticSplitter

# Local application/library specific imports


class SplitterSettings(Settings):
    """Anything Embedding-related."""

    BATCH_SIZE: int = Field(100, gt=0)
    NUM_THREADS: int = Field(4, gt=1)
    TOKEN_COUNT_MIN: int = Field(64, gt=0)
    TOKEN_COUNT_MAX: int = Field(1024, gt=1)
    TOKEN_COUNT_BUFFER: int = Field(32, gt=0)


log = getLogger(__name__)


class SimpleSplitterStep(TypedStep[SplitterSettings, list[MarkdownDataContract], list[MarkdownDataContract]]):
    """SimpleSplitterStep to split Markdown Documents rundimentory in medium size chunks."""

    def __init__(self) -> None:
        super().__init__()
        self.splitter = SemanticSplitter(
            token_limit=self.settings.TOKEN_COUNT_MAX,
            token_limit_buffer=self.settings.TOKEN_COUNT_BUFFER,
            token_limit_min=self.settings.TOKEN_COUNT_MIN,
        )

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Executes the split step by processing input markdown files and generating smaller split markdown files and preservs the headline.

        Args:
            inpt (list[MarkdownDataContract]): A list of MarkdownDataContract objects representing
                                               the input markdown files to be processed.

        Returns:
            list[MarkdownDataContract]: A list of MarkdownDataContract objects representing
                                         the smaller split markdown files.

        The method splits the input markdown files into batches based on the configured batch size
        (`self.settings.BATCH_SIZE`). Each batch is processed in parallel using threading, and the
        results are flattened into a single list of split markdown files.

        """

        def _batchify(data: list, size: int) -> list[list]:
            return [data[i : i + size] for i in range(0, len(data), size)]

        batches = _batchify(inpt, self.settings.BATCH_SIZE)

        # Run each batch in parallel using threading
        results = Parallel(n_jobs=self.settings.NUM_THREADS, prefer="threads")(delayed(self._split_markdown)(batch) for batch in batches)

        # Flatten the list of lists
        return [item for sublist in results for item in sublist]

    def _split_markdown(self, markdowns: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Creates data rows from a batch of markdown texts by splitting them and counting tokens."""
        rows = []
        skipped = 0
        for s in markdowns:
            try:
                rows.extend(self.splitter.split_markdown_document(s))
            except MarkdownException as err:
                log.warning(
                    "skipped dokument ",
                    extra={"reason": err.__class__.__name__, "doc": s},
                )
                skipped += 1
        if skipped == len(markdowns):
            raise SplittException("all Documents got skipped during splitting")
        if skipped:
            log.error(f"{(skipped / len(markdowns)) * 100}% got skipped")
        return rows
