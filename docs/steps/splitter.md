# Splitter

The splitter step (also known as chunking) takes a long Markdown document as the input and returns smaller splits (or chunks) that can easier processed by an embedding model or language model.
The splitter keeps the length of the output chunks below a defined threshold (token limit) and tries to split without breaking the document context, e.g., split only at the end of a sentence and not within a sentence.

## Semantic Splitter

Semantic document elements (e.g., headings) are repeated.

::: wurzel.utils.semantic_splitter.SemanticSplitter
    handler: python

## Table Splitter

For Markdown tables, a custom logic is implemented that preserves the table structure by repeating the header row if a split occurs within a table. So subsequent chunks maintain the semantic table information from the header row.
By default, tables are never broken in the middle of a row; if a *single* row exceeds the budget, it is split at column boundaries instead and full-header is repeated.

::: wurzel.utils.markdown_table_splitter.MarkdownTableSplitterUtil
    handler: python
