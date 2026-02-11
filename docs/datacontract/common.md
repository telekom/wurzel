# Data contracts

Data contracts are the primary inputs and outputs of pipeline steps, e.g., Markdown documents.

## MarkdownDataContract

::: wurzel.datacontract.common.MarkdownDataContract
    options:
      show_source: false
      heading_level: 3

## BatchWriter

A context manager for writing large result sets to disk in numbered batch files.
Used internally by the executor for generator steps, but also available for direct use.
See [Batch Writing and Streaming](../developer-guide/data-contracts.md#batchwriter) for usage examples.

::: wurzel.datacontract.datacontract.BatchWriter
    options:
      show_source: false
      heading_level: 3
      members:
        - extend
        - flush
        - total_items
        - file_count
        - store_time
        - DEFAULT_FLUSH_SIZE
