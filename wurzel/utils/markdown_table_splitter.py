# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
"""Markdown Table Splitter.

Utility functions for splitting large markdown tables (given as string) into **token-bounded**
chunks while preserving table structure.  By default, tables are never broken in the middle
of a row; if a *single* row exceeds the max. length, it is split at column
boundaries instead and full-header is repeated.

Usage example
-------------
>>> import pathlib, tiktoken
>>> from markdown_table_splitter import split_markdown_table
>>> enc = tiktoken.get_encoding("cl100k_base")
>>> md_text = pathlib.Path("README.md").read_text()
>>> pieces = split_markdown_table(md_text, 8000, enc)
>>> len(pieces)
3
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import tiktoken  # pip install tiktoken

# Regex that matches a Markdown table alignment row, e.g.  |---|:---:|---|
TABLE_SEP_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$")


@dataclass
class MarkdownTableSplitter:
    """A class to split markdown tables into token-bounded chunks.

    This class encapsulates the logic for splitting large markdown tables while
    preserving table structure. Tables are never broken in the middle of a row;
    if a single row exceeds the max length, it is split at column boundaries
    instead and the full header is repeated.

    Examples
    --------
    >>> import tiktoken
    >>> enc = tiktoken.get_encoding("cl100k_base")
    >>> splitter = MarkdownTableSplitter(token_limit=8000, enc=enc)
    >>> chunks = splitter.split(markdown_text)
    >>> len(chunks)
    3

    Attributes
    ----------
    token_limit : int
        Maximum tokens per chunk (model tokens, not characters).
    enc : tiktoken.Encoding
        Tokenizer used for counting tokens.
    repeat_header_row : bool, default True
        Whether to repeat header row in each subsequent table chunk.
    chunks : list[str]
        List collecting completed chunks (internal state).
    buf : list[str]
        Current chunk being built (internal state).
    buf_tok : int
        Current token count in the buffer (internal state).

    """

    token_limit: int
    enc: tiktoken.Encoding
    repeat_header_row: bool = True
    chunks: list[str] = field(default_factory=lambda: [])
    buf: list[str] = field(default_factory=lambda: [])
    buf_tok: int = 0

    def reset_state(self) -> None:
        """Reset the internal state for a new splitting operation."""
        self.chunks.clear()
        self.buf.clear()
        self.buf_tok = 0

    def validate_config(self) -> None:
        """Validate the splitter configuration.

        Raises
        ------
        ValueError
            If token_limit is too small.

        """
        if self.token_limit < 10:
            raise ValueError("token_limit must be at least 10 tokens")

    def flush_buffer(self) -> None:
        """Append joined buffer to chunks and clear buffer."""
        if self.buf:
            self.chunks.append("".join(self.buf))
            self.buf.clear()
            self.buf_tok = 0

    def count_row_tokens(self, cells: list[str]) -> int:
        """Return token length of cells rendered as one Markdown row.

        Parameters
        ----------
        cells : list[str]
            Column values.

        Returns
        -------
        int
            Token count for the rendered row.

        """
        return len(self.enc.encode(make_row(cells)))

    # pylint: disable=too-many-positional-arguments
    def slice_long_row(
        self,
        row_cells: list[str],
        header_cells: list[str],
        sep_cells: list[str],
        header_line: str,
        sep_line: str,
    ) -> None:  # pylint: enable=too-many-positional-arguments
        """Split an oversized table row at column boundaries.

        Side‑effects:
            * Extends/clears buffer.
            * Appends new chunks to chunks.

        Parameters
        ----------
        row_cells : list[str]
            The row cells to split.
        header_cells : list[str]
            The header cells.
        sep_cells : list[str]
            The separator cells.
        header_line : str
            The full header line.
        sep_line : str
            The full separator line.

        """
        col_idx = 0
        while col_idx < len(row_cells):
            slice_cells: list[str] = []

            # Grow slice until adding another column would overflow the budget.
            while col_idx < len(row_cells):
                tentative = slice_cells + [row_cells[col_idx]]
                next_tok = self.count_row_tokens(tentative)
                header_slice_tok = 0
                if self.repeat_header_row:
                    header_slice_tok = self.count_row_tokens(header_cells[: len(tentative)]) + self.count_row_tokens(
                        sep_cells[: len(tentative)]
                    )
                if header_slice_tok + next_tok > self.token_limit and slice_cells:
                    break
                slice_cells.append(row_cells[col_idx])
                col_idx += 1

            # Render and emit the slice
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

            self.flush_buffer()

            # Prepare for next slice
            if col_idx < len(row_cells) and self.repeat_header_row:
                self.buf.extend([header_line, sep_line])
                # Update buf_tok for the next iteration
                self.buf_tok = len(self.enc.encode(header_line + sep_line))
            else:
                self.buf.clear()
                self.buf_tok = 0

    def process_table(self, lines: list[str], start_idx: int) -> int:
        """Process a whole Markdown table, returning new index.

        The function mutates internal buffer and chunks in place.

        Parameters
        ----------
        lines : list[str]
            The lines of the markdown document.
        start_idx : int
            Index of the table start line.

        Returns
        -------
        int
            New index after processing the table.

        """
        header_line, sep_line = lines[start_idx], lines[start_idx + 1]
        header_cells = [c.strip() for c in header_line.strip().strip("|").split("|")]
        sep_cells = [c.strip() for c in sep_line.strip().strip("|").split("|")]

        header_tok = len(self.enc.encode(header_line + sep_line))

        if self.buf_tok + header_tok > self.token_limit:
            self.flush_buffer()

        self.buf.extend([header_line, sep_line])
        self.buf_tok += header_tok

        i = start_idx + 2  # First body row

        while i < len(lines) and "|" in lines[i]:
            row_line = lines[i]
            row_cells = [c.strip() for c in row_line.strip().strip("|").split("|")]
            row_tok = self.count_row_tokens(row_cells)

            # Row fits current buffer
            if self.buf_tok + row_tok <= self.token_limit:
                self.buf.append(row_line)
                self.buf_tok += row_tok
                i += 1
                continue

            # Row does not fit
            self.flush_buffer()
            if self.repeat_header_row:
                self.buf.extend([header_line, sep_line])
                self.buf_tok = header_tok

            # Oversized row: slice into columns.
            if row_tok > self.token_limit:
                self.slice_long_row(
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

        Parameters
        ----------
        md : str
            Markdown document.

        Returns
        -------
        list[str]
            Chunks whose token counts are <= token_limit.

        Raises
        ------
        ValueError
            If the splitter configuration is invalid.

        """
        self.validate_config()
        self.reset_state()
        lines = md.splitlines(keepends=True)
        i = 0

        while i < len(lines):
            if is_table_start(lines, i):
                i = self.process_table(lines, i)
                continue

            # Non‑table line processing
            line = lines[i]
            line_tok = len(self.enc.encode(line))

            if self.buf_tok + line_tok > self.token_limit:
                self.flush_buffer()

            self.buf.append(line)
            self.buf_tok += line_tok
            i += 1

        self.flush_buffer()
        return self.chunks.copy()

    def get_metrics(self) -> dict[str, int]:
        """Get metrics about the last splitting operation.

        Returns
        -------
        dict[str, int]
            Dictionary containing metrics:
            - 'chunk_count': Number of chunks created
            - 'avg_tokens': Average tokens per chunk (approximation)
            - 'max_tokens': Maximum tokens in any chunk (approximation)
            - 'min_tokens': Minimum tokens in any chunk (approximation)

        """
        if not self.chunks:
            return {"chunk_count": 0, "avg_tokens": 0, "max_tokens": 0, "min_tokens": 0}

        token_counts = [len(self.enc.encode(chunk)) for chunk in self.chunks]

        return {
            "chunk_count": len(self.chunks),
            "avg_tokens": sum(token_counts) // len(token_counts),
            "max_tokens": max(token_counts),
            "min_tokens": min(token_counts),
        }


def make_row(cells: list[str]) -> str:
    r"""Convert *cells* to a Markdown table row.

    Parameters
    ----------
    cells : list[str]
        Column values.

    Returns
    -------
    str
        A string like ``"| col1 | col2 |\n"``.

    """
    return "|" + " | ".join(cells) + "|\n"


def is_table_start(lines: list[str], idx: int) -> bool:
    """Return ``True`` if ``lines[idx]`` begins a pipe table.

    A table start is defined as a row line containing at least one ``|`` whose
    *next* line matches ``TABLE_SEP_RE``.
    """
    return "|" in lines[idx] and idx + 1 < len(lines) and bool(TABLE_SEP_RE.match(lines[idx + 1]))


def split_markdown_table(
    md: str,
    token_limit: int,
    enc: tiktoken.Encoding,
    repeat_header_row: bool = True,
) -> list[str]:
    """Split a markdown document into token-bounded chunks while respecting tables.

    Parameters
    ----------
    md : str
        Markdown document.
    token_limit : int
        Maximum tokens per chunk (model tokens, not characters).
    enc : tiktoken.Encoding
        Tokenizer used for counting.
    repeat_header_row : bool, default True
        Repeat header row in each subsequent table chunk.

    Returns
    -------
    list[str]
        Chunks whose token counts are <= *token_limit*.

    """
    splitter = MarkdownTableSplitter(token_limit=token_limit, enc=enc, repeat_header_row=repeat_header_row)
    return splitter.split(md)
