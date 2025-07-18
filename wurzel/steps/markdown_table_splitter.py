import re

import tiktoken  # pip install tiktoken

# Regex that matches a Markdown table alignment row, such as
# |---|:---:|---| or  --- | --- |
TABLE_SEP_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$")


def split_markdown_table_safe(
    md: str,
    token_limit: int,
    enc: tiktoken.Encoding,
) -> list[str]:
    """Chunk a Markdown document by token count while preserving table integrity.

    - Guarantees that no chunk exceeds ``token_limit`` (counted with the provided
      ``enc`` tokenizer).
    - If the document contains Markdown tables:
        - A split never occurs inside a table row.
        - If a single row itself exceeds ``token_limit``, the row is split at
          column boundaries, producing multiple column slices.
    - Whenever a new chunk continues a table, the header row and its alignment
      row are repeated so each chunk remains a valid standalone table.

    Output chunks therefore take the form of:
    ```markdown
        | COL1 | COL2 |
        |:----:|------|
        | …    | …    |
    ```

    Args:
        md (str): The full Markdown string to split.
        token_limit (int): Maximum number of tokens allowed per chunk.
        enc (tiktoken.Encoding): OpenAI tokenizer used for token counting.

    Returns:
        list[str]: A list of Markdown chunks, each within the token limit.

    """
    # --------------------------------------------------------------------- #
    # Helper functions that close over `enc` so they see the same encoding. #
    # --------------------------------------------------------------------- #

    def _mk_row(cells) -> str:
        """Return a Markdown row string from a list of cell strings."""
        return "|" + " | ".join(cells) + "|\n"

    def _row_tokens(cells) -> int:
        """Return token count of one Markdown row."""
        return len(enc.encode(_mk_row(cells)))

    def _flush(buf, out):
        """Append current buffer to output list and clear the buffer."""
        if buf:
            out.append("".join(buf))
            buf.clear()

    # --------------------------------------------------------------------- #
    # Main algorithm starts here.                                           #
    # --------------------------------------------------------------------- #
    lines = md.splitlines(keepends=True)  # Keep newline chars for exact rebuild
    chunks: list[str] = []  # Final list of Markdown chunks
    buf: list[str] = []  # Current chunk under construction
    buf_tok = 0  # Token count of current buffer
    i = 0  # Index into `lines`

    while i < len(lines):
        line = lines[i]

        # -------------------------------------------------------------- #
        # Detect start of a Markdown pipe table: current line is a row   #
        # and next line is an alignment row like |---|:---:|             #
        # -------------------------------------------------------------- #
        if "|" in line and i + 1 < len(lines) and TABLE_SEP_RE.match(lines[i + 1]):
            # Capture header and alignment lines
            header_line, sep_line = line, lines[i + 1]
            header_cells = [c.strip() for c in header_line.strip().strip("|").split("|")]
            sep_cells = [c.strip() for c in sep_line.strip().strip("|").split("|")]

            # Token count for header plus alignment lines
            header_tok = len(enc.encode(header_line + sep_line))

            # If adding header would exceed limit, start a new chunk
            if buf_tok + header_tok > token_limit:
                _flush(buf, chunks)
                buf_tok = 0

            # Add header and alignment to buffer
            buf.extend([header_line, sep_line])
            buf_tok += header_tok
            i += 2  # Advance past header and alignment

            # ---------------------------- #
            # Process the table body rows  #
            # ---------------------------- #
            while i < len(lines) and "|" in lines[i]:
                row_line = lines[i]
                row_cells = [c.strip() for c in row_line.strip().strip("|").split("|")]
                row_tok = _row_tokens(row_cells)

                # Case 1: Row fits in current buffer
                if buf_tok + row_tok <= token_limit:
                    buf.append(row_line)
                    buf_tok += row_tok
                    i += 1
                    continue

                # Case 2: Row does not fit, so start a new chunk
                _flush(buf, chunks)
                buf.extend([header_line, sep_line])  # Repeat header for new chunk
                buf_tok = header_tok

                # Case 2a: Row still exceeds token_limit by itself
                if row_tok > token_limit:
                    col_idx = 0
                    # Break the row into slices, each fitting within limit
                    while col_idx < len(row_cells):
                        slice_cells: list[str] = []

                        # Add columns until the slice would overflow
                        while col_idx < len(row_cells):
                            tentative = slice_cells + [row_cells[col_idx]]
                            next_tok = _row_tokens(tentative)
                            header_slice_tok = _row_tokens(header_cells[: len(tentative)]) + _row_tokens(sep_cells[: len(tentative)])
                            # Stop when adding the next column would overflow
                            if header_slice_tok + next_tok > token_limit and slice_cells:
                                break
                            slice_cells.append(row_cells[col_idx])
                            col_idx += 1

                        # Build chunk for this slice: header slice + row slice
                        buf_slice = [
                            _mk_row(header_cells[: len(slice_cells)]),
                            _mk_row(sep_cells[: len(slice_cells)]),
                            _mk_row(slice_cells),
                        ]
                        buf.extend(buf_slice)
                        _flush(buf, chunks)  # Emit slice as its own chunk
                        buf_tok = 0  # Reset buffer token count

                        # If more columns remain, repeat header for next slice
                        if col_idx < len(row_cells):
                            buf.extend([header_line, sep_line])
                            buf_tok = header_tok
                    i += 1  # Done with this long row
                else:
                    # Case 2b: Row now fits in fresh buffer
                    buf.append(row_line)
                    buf_tok += row_tok
                    i += 1
            # End of table; jump back to main while loop
            continue

        # -------------------------------------------------------------- #
        # Non-table line processing                                     #
        # -------------------------------------------------------------- #
        line_tok = len(enc.encode(line))

        # If adding the line would overflow, cut a new chunk first
        if buf_tok + line_tok > token_limit:
            _flush(buf, chunks)
            buf_tok = 0

        # Add line and update token count
        buf.append(line)
        buf_tok += line_tok
        i += 1

    # Flush anything remaining in buffer after loop
    _flush(buf, chunks)
    return chunks
