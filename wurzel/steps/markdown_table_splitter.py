# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
"""Markdown Table Splitter.

Utility functions for splitting large Markdown strings into **token‑bounded**
chunks while preserving table structure.  Tables are never broken in the middle
of a row; if a *single* row exceeds the budget, it is split at column
boundaries instead.

Usage example
-------------
>>> import pathlib, tiktoken, markdown_table_splitter as mts
>>> enc = tiktoken.get_encoding("cl100k_base")
>>> md_text = pathlib.Path("README.md").read_text()
>>> pieces = mts.split_markdown_table_safe(md_text, 8000, enc)
>>> len(pieces)
3
"""

from __future__ import annotations

import re

import tiktoken  # pip install tiktoken

# Regex that matches a Markdown table alignment row, e.g.  |---|:---:|---|
TABLE_SEP_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$")


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


def count_row_tokens(enc: tiktoken.Encoding, cells: list[str]) -> int:
    """Return token length of *cells* rendered as one Markdown row.

    Parameters
    ----------
    enc : tiktoken.Encoding
        Tokenizer used for counting.
    cells : list[str]
        Column values.

    Returns
    -------
    int
        Token count for the rendered row.

    """
    return len(enc.encode(make_row(cells)))


def flush_buffer(buf: list[str], out: list[str]) -> None:
    """Append joined *buf* to *out* and clear *buf*.

    Parameters
    ----------
    buf : list[str]
        Current chunk being built.
    out : list[str]
        list collecting completed chunks.

    """
    if buf:
        out.append("".join(buf))
        buf.clear()


def is_table_start(lines: list[str], idx: int) -> bool:
    """Return ``True`` iff ``lines[idx]`` begins a pipe table.

    A table start is defined as a row line containing at least one ``|`` whose
    *next* line matches ``TABLE_SEP_RE``.
    """
    return "|" in lines[idx] and idx + 1 < len(lines) and TABLE_SEP_RE.match(lines[idx + 1])


def slice_long_row(
    row_cells: list[str],
    header_cells: list[str],
    sep_cells: list[str],
    header_line: str,
    sep_line: str,
    *,
    token_limit: int,
    enc: tiktoken.Encoding,
    repeat_header_row: bool,
    buf: list[str],
    chunks: list[str],
) -> None:
    """Split an oversized table row at column boundaries.

    Side‑effects:
        * Extends/clears *buf*.
        * Appends new chunks to *chunks*.

    All other arguments are read‑only context.
    """
    col_idx = 0
    while col_idx < len(row_cells):
        slice_cells: list[str] = []

        # Grow slice until adding another column would overflow the budget.
        while col_idx < len(row_cells):
            tentative = slice_cells + [row_cells[col_idx]]
            next_tok = count_row_tokens(enc, tentative)
            header_slice_tok = 0
            if repeat_header_row:
                header_slice_tok = count_row_tokens(enc, header_cells[: len(tentative)]) + count_row_tokens(
                    enc, sep_cells[: len(tentative)]
                )
            if header_slice_tok + next_tok > token_limit and slice_cells:
                break
            slice_cells.append(row_cells[col_idx])
            col_idx += 1

        # Render and emit the slice
        if repeat_header_row:
            buf.extend(
                [
                    make_row(header_cells[: len(slice_cells)]),
                    make_row(sep_cells[: len(slice_cells)]),
                    make_row(slice_cells),
                ]
            )
        else:
            buf.append(make_row(slice_cells))

        flush_buffer(buf, chunks)

        # Prepare for next slice
        if col_idx < len(row_cells) and repeat_header_row:
            buf.extend([header_line, sep_line])
        else:
            buf.clear()


def process_table(
    lines: list[str],
    start_idx: int,
    *,
    token_limit: int,
    enc: tiktoken.Encoding,
    repeat_header_row: bool,
    buf: list[str],
    chunks: list[str],
    buf_tok: int,
) -> tuple[int, int]:
    """Process a whole Markdown table, returning new index and token count.

    The function mutates *buf* and *chunks* in place.
    """
    header_line, sep_line = lines[start_idx], lines[start_idx + 1]
    header_cells = [c.strip() for c in header_line.strip().strip("|").split("|")]
    sep_cells = [c.strip() for c in sep_line.strip().strip("|").split("|")]

    header_tok = len(enc.encode(header_line + sep_line))

    if buf_tok + header_tok > token_limit:
        flush_buffer(buf, chunks)
        buf_tok = 0

    buf.extend([header_line, sep_line])
    buf_tok += header_tok

    i = start_idx + 2  # First body row

    while i < len(lines) and "|" in lines[i]:
        row_line = lines[i]
        row_cells = [c.strip() for c in row_line.strip().strip("|").split("|")]
        row_tok = count_row_tokens(enc, row_cells)

        # Row fits current buffer
        if buf_tok + row_tok <= token_limit:
            buf.append(row_line)
            buf_tok += row_tok
            i += 1
            continue

        # Row does not fit
        flush_buffer(buf, chunks)
        buf_tok = 0
        if repeat_header_row:
            buf.extend([header_line, sep_line])
            buf_tok = header_tok

        # Oversized row: slice into columns.
        if row_tok > token_limit:
            slice_long_row(
                row_cells,
                header_cells,
                sep_cells,
                header_line,
                sep_line,
                token_limit=token_limit,
                enc=enc,
                repeat_header_row=repeat_header_row,
                buf=buf,
                chunks=chunks,
            )
            buf_tok = 0
            i += 1
        else:
            buf.append(row_line)
            buf_tok += row_tok
            i += 1

    return i, buf_tok


def split_markdown_table_safe(
    md: str,
    token_limit: int,
    enc: tiktoken.Encoding,
    repeat_header_row: bool = True,
) -> list[str]:
    """Split *md* into token-bounded chunks while respecting tables.

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
    lines = md.splitlines(keepends=True)
    chunks: list[str] = []
    buf: list[str] = []
    buf_tok = 0
    i = 0

    while i < len(lines):
        if is_table_start(lines, i):
            i, buf_tok = process_table(
                lines,
                i,
                token_limit=token_limit,
                enc=enc,
                repeat_header_row=repeat_header_row,
                buf=buf,
                chunks=chunks,
                buf_tok=buf_tok,
            )
            continue

        # Non‑table line processing
        line = lines[i]
        line_tok = len(enc.encode(line))

        if buf_tok + line_tok > token_limit:
            flush_buffer(buf, chunks)
            buf_tok = 0

        buf.append(line)
        buf_tok += line_tok
        i += 1

    flush_buffer(buf, chunks)
    return chunks
