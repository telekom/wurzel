# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
"""Markdown Table Splitter utility.

Utility for splitting large markdown tables into token-bounded chunks while preserving table structure.
Tables are never broken in the middle of a row; if a single row exceeds the max length, it is split at
column boundaries and the full header is repeated.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from logging import getLogger

import tiktoken  # pip install tiktoken

# Regex that matches a Markdown table alignment row, e.g.  |---|:---:|---|
TABLE_SEP_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$")

log = getLogger(__name__)


@dataclass
class SplittingOperationMetrics:
    """Metrics about a splitting operation.

    Args:
        chunk_count (int): Number of chunks created
        avg_tokens (int): Average tokens per chunk (approximation)
        max_tokens (int): Maximum tokens in any chunk (approximation)
        min_tokens (int): Minimum tokens in any chunk (approximation)
        total_output_tokens (int): Total tokens in all chunks
        total_output_chars (int): Total characters in all chunks

    """

    chunk_count: int = 0
    avg_tokens: int = 0
    max_tokens: int = 0
    min_tokens: int = 0
    total_output_tokens: int = 0
    total_output_chars: int = 0


@dataclass
class MarkdownTableSplitterUtil:
    """A class to split markdown tables into token-bounded chunks.

    This class encapsulates the logic for splitting large markdown tables while
    preserving table structure. Tables are never broken in the middle of a row;
    if a single row exceeds the max length, it is split at column boundaries
    instead and the full header is repeated.

    Example:
    ```
    >>> import tiktoken
    >>> enc = tiktoken.get_encoding("cl100k_base")
    >>> splitter = MarkdownTableSplitterUtil(token_limit=8000, enc=enc)
    >>> chunks = splitter.split(markdown_text)
    >>> len(chunks)
    3
    ```

    Args:
        token_limit (int): Maximum tokens per chunk (model tokens, not characters).
        enc (tiktoken.Encoding): Tokenizer used for counting tokens.
        repeat_header_row (bool, optional): If True, repeat the header row in each chunk. Defaults to True.

    Attributes:
        chunks (list[str]): Completed chunks of markdown.
        buf (list[str]): Current buffer of lines.
        buf_tok (int): Current token count in buffer.
        min_safety_token_limit (int): A minimum of 10 tokens is a safety threshold to ensure the splitter can
            always fit at least a minimal table structure in a chunk.

    """

    token_limit: int
    enc: tiktoken.Encoding
    repeat_header_row: bool = True
    chunks: list[str] = field(default_factory=lambda: [])
    buf: list[str] = field(default_factory=lambda: [])
    buf_tok: int = 0
    min_safety_token_limit: int = 10

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate_config()

    def _reset_state(self) -> None:
        """Reset the internal state for a new splitting operation."""
        self.chunks.clear()
        self.buf.clear()
        self.buf_tok = 0

    def _validate_config(self) -> None:
        """Validate the splitter configuration.

        Raises:
            ValueError: If token_limit is too small.

        """
        if self.token_limit < self.min_safety_token_limit:
            raise ValueError(f"token_limit must be at least {self.min_safety_token_limit} tokens (safety threshold)")

    def _flush_buffer(self) -> None:
        """Append joined buffer to chunks and clear buffer."""
        if self.buf:
            self.chunks.append("".join(self.buf))
            self.buf.clear()
            self.buf_tok = 0

    def _add_line_to_buffer(self, line: str) -> None:
        """Add a line to the buffer, checking token limits.

        Args:
            line (str): The line to add to the buffer.

        """
        line_tok = len(self.enc.encode(line))

        if self.buf_tok + line_tok > self.token_limit:
            self._flush_buffer()

        self.buf.append(line)
        self.buf_tok += line_tok

    def _extract_table_header_info(self, lines: list[str], start_idx: int) -> tuple[str, str, list[str], list[str], int]:
        """Extract table header information.

        Args:
            lines (list[str]): The lines of the markdown document.
            start_idx (int): Index of the table start line.

        Returns:
            tuple[str, str, list[str], list[str], int]
                header_line, sep_line, header_cells, sep_cells, header_tok

        """
        header_line, sep_line = lines[start_idx], lines[start_idx + 1]
        header_cells = [c.strip() for c in header_line.strip().strip("|").split("|")]
        sep_cells = [c.strip() for c in sep_line.strip().strip("|").split("|")]
        header_tok = len(self.enc.encode(header_line + sep_line))

        return header_line, sep_line, header_cells, sep_cells, header_tok

    def _count_row_tokens(self, cells: list[str]) -> int:
        """Return token length of cells rendered as one Markdown row.

        Args:
            cells (list[str]): Column values.

        Returns:
            int: Token count for the rendered row.

        """
        return len(self.enc.encode(make_row(cells)))

    # pylint: disable=too-many-positional-arguments
    def _slice_long_row(
        self,
        row_cells: list[str],
        header_cells: list[str],
        sep_cells: list[str],
        header_line: str,
        sep_line: str,
    ) -> None:  # pylint: enable=too-many-positional-arguments
        """Split an oversized table row at column boundaries.

        Side-effects:
            * Extends/clears buffer.
            * Appends new chunks to chunks.

        Args:
            row_cells (list[str]): The row cells to split.
            header_cells (list[str]): The header cells.
            sep_cells (list[str]): The separator cells.
            header_line (str): The full header line.
            sep_line (str): The full separator line.

        """
        col_idx = 0
        while col_idx < len(row_cells):
            slice_cells: list[str] = []

            # Grow slice until adding another column would overflow the budget.
            while col_idx < len(row_cells):
                tentative = slice_cells + [row_cells[col_idx]]
                total_tok = self._calculate_slice_budget(tentative, header_cells, sep_cells)

                if total_tok > self.token_limit and slice_cells:
                    break
                slice_cells.append(row_cells[col_idx])
                col_idx += 1

            # Render and emit the slice
            self._render_table_slice(slice_cells, header_cells, sep_cells)
            self._flush_buffer()

            # Prepare for next slice
            if col_idx < len(row_cells) and self.repeat_header_row:
                self.buf.extend([header_line, sep_line])
                # Update buf_tok for the next iteration
                self.buf_tok = len(self.enc.encode(header_line + sep_line))
            else:
                self.buf.clear()
                self.buf_tok = 0

    def _calculate_slice_budget(self, tentative_cells: list[str], header_cells: list[str], sep_cells: list[str]) -> int:
        """Calculate token budget for a table slice.

        Args:
            tentative_cells : list[str]
                The tentative slice cells.
            header_cells : list[str]
                The header cells.
            sep_cells : list[str]
                The separator cells.

        Returns:
            int: Total token count for this slice including headers if needed.

        """
        slice_tok = self._count_row_tokens(tentative_cells)
        header_slice_tok = 0

        if self.repeat_header_row:
            header_slice_tok = self._count_row_tokens(header_cells[: len(tentative_cells)]) + self._count_row_tokens(
                sep_cells[: len(tentative_cells)]
            )

        return header_slice_tok + slice_tok

    def _render_table_slice(self, slice_cells: list[str], header_cells: list[str], sep_cells: list[str]) -> None:
        """Render a table slice to the buffer.

        Args:
            slice_cells : list[str]
                The slice cells to render.
            header_cells : list[str]
                The header cells.
            sep_cells : list[str]
                The separator cells.

        """
        if self.repeat_header_row:
            self.buf.extend(
                [
                    make_row(header_cells[: len(slice_cells)]),
                    make_row(sep_cells[: len(slice_cells)]),
                    make_row(slice_cells),
                ]
            )
        else:
            self.buf.append(make_row(slice_cells))

    def _process_table(self, lines: list[str], start_idx: int) -> int:
        """Process a whole Markdown table, returning new index.

        The function mutates internal buffer and chunks in place.

        Args:
            lines : list[str]
                The lines of the markdown document.
            start_idx : int
                Index of the table start line.

        Returns:
            int: New index after processing the table.

        """
        header_line, sep_line, header_cells, sep_cells, header_tok = self._extract_table_header_info(lines, start_idx)

        if self.buf_tok + header_tok > self.token_limit:
            self._flush_buffer()

        self.buf.extend([header_line, sep_line])
        self.buf_tok += header_tok

        return self._process_table_rows(lines, start_idx + 2, header_line, sep_line, header_cells, sep_cells, header_tok)

    def _process_table_rows(
        self,
        lines: list[str],
        start_row_idx: int,
        header_line: str,
        sep_line: str,
        header_cells: list[str],
        sep_cells: list[str],
        header_tok: int,
    ) -> int:
        """Process table rows starting from start_row_idx.

        Args:
            lines : list[str]
                The lines of the markdown document.
            start_row_idx : int
                Index of the first row to process.
            header_line : str
                The header line string.
            sep_line : str
                The separator line string.
            header_cells : list[str]
                The header cells.
            sep_cells : list[str]
                The separator cells.
            header_tok : int
                Token count of header and separator lines.

        Returns:
            int: New index after processing all rows.

        """
        i = start_row_idx

        while i < len(lines) and "|" in lines[i]:
            row_line = lines[i]
            row_cells = [c.strip() for c in row_line.strip().strip("|").split("|")]
            row_tok = self._count_row_tokens(row_cells)

            # Row fits current buffer
            if self.buf_tok + row_tok <= self.token_limit:
                self.buf.append(row_line)
                self.buf_tok += row_tok
                i += 1
                continue

            # Row does not fit
            self._flush_buffer()
            if self.repeat_header_row:
                self.buf.extend([header_line, sep_line])
                self.buf_tok = header_tok

            # Oversized row: slice into columns.
            if row_tok > self.token_limit:
                self._slice_long_row(
                    row_cells,
                    header_cells,
                    sep_cells,
                    header_line,
                    sep_line,
                )
                i += 1
            else:
                self.buf.append(row_line)
                self.buf_tok += row_tok
                i += 1

        return i

    def split(self, md: str) -> list[str]:
        """Split a markdown document into token-bounded chunks while respecting tables.

        Args:
            md : str
                Markdown document.

        Returns:
            list[str]: Chunks whose token counts are <= token_limit.

        """
        self._reset_state()

        input_length = len(md)
        input_tokens = len(self.enc.encode(md))
        table_count = self._count_tables_in_text(md)

        lines = md.splitlines(keepends=True)
        i = 0

        while i < len(lines):
            if is_table_start(lines, i):
                i = self._process_table(lines, i)
                continue

            # Non‑table line processing
            self._add_line_to_buffer(lines[i])
            i += 1

        self._flush_buffer()

        metrics = self._get_metrics()
        log.info(
            "Markdown table splitting completed",
            extra={
                "input_markdown": md,
                "input_length": input_length,
                "input_tokens": input_tokens,
                "input_table_count": table_count,
                "token_limit": self.token_limit,
                "repeat_header_row": self.repeat_header_row,
                **asdict(metrics),
            },
        )

        return self.chunks.copy()

    def _get_metrics(self) -> SplittingOperationMetrics:
        """Get metrics about the last splitting operation.

        Returns:
            SplittingOperationMetrics: Data class containing metrics:

        """
        if not self.chunks:
            return SplittingOperationMetrics()

        token_counts = [len(self.enc.encode(chunk)) for chunk in self.chunks]
        total_chars = sum(len(chunk) for chunk in self.chunks)
        total_tokens = sum(token_counts)

        return SplittingOperationMetrics(
            chunk_count=len(self.chunks),
            avg_tokens=total_tokens // len(self.chunks),
            max_tokens=max(token_counts),
            min_tokens=min(token_counts),
            total_output_tokens=total_tokens,
            total_output_chars=total_chars,
        )

    def _count_tables_in_text(self, md: str) -> int:
        """Count the number of tables in the markdown text.

        Args:
            md : str
                Markdown document.

        Returns:
            int: Number of tables found.

        """
        lines = md.splitlines(keepends=True)
        table_count = 0
        i = 0

        while i < len(lines):
            if is_table_start(lines, i):
                table_count += 1
                # Skip to the end of this table
                i += 2  # Skip header and separator
                while i < len(lines) and "|" in lines[i]:
                    i += 1
            else:
                i += 1

        return table_count


def make_row(cells: list[str]) -> str:
    r"""Convert *cells* to a Markdown table row.

    Args:
        cells : list[str]
            Column values.

    Returns:
        str: A string like ``"| col1 | col2 |\n"``.

    """
    return "|" + " | ".join(cells) + "|\n"


def is_table_start(lines: list[str], idx: int) -> bool:
    """Return ``True`` if ``lines[idx]`` begins a pipe table.

    A table start is defined as a row line containing at least one ``|`` whose
    *next* line matches ``TABLE_SEP_RE``.
    """
    return "|" in lines[idx] and idx + 1 < len(lines) and bool(TABLE_SEP_RE.match(lines[idx + 1]))
