# Data contracts

Data contracts are the primarily inputs and outputs of pipeline steps, e.g., Markdown documents.

## Metrics

Data contracts can optionally expose numeric metrics (for example, counts or sizes).
For `PydanticModel`-based contracts, implement a `metrics()` method on the instance.
For `PanderaDataFrameModel` contracts, override `get_metrics(cls, obj)` on the class.
Middlewares (like Prometheus) can use these metrics if provided.

## MarkdownDataContract

::: wurzel.datacontract.common.MarkdownDataContract
    options:
      show_source: false
      heading_level: 3
