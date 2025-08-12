# 🔗 Defining a Pipeline in Wurzel

At the heart of Wurzel lies the concept of the pipeline — a chain of steps that are connected and executed in sequence. Each step processes the output of the previous one, enabling modular, reusable, and optimally scheduled workflows.

## 🧩 What is a Wurzel Pipeline?

A pipeline in Wurzel is a chain of TypedStep instances, linked using the >> operator. This chaining mechanism makes it easy to define complex data processing flows that remain clean and composable.

Wurzel optimizes the execution of these pipelines automatically based on dependencies and contracts.

## 🛠️ How to Define a Pipeline

To define a pipeline:

1. Use step classes directly without any wrapper.
2. Chain them together using `>>`.
3. Return the final step (which implicitly carries the full chain).

> **Note**: As of version 2.x, you can use step classes directly without the `WZ()` wrapper. The old syntax using `WZ(StepClass)` is still supported for backwards compatibility, but the new direct syntax `StepClass` is recommended for cleaner code.

### 📦 Example

```python
from wurzel.steps import (
    EmbeddingStep,
    QdrantConnectorStep,
)
from wurzel.steps.manual_markdown import ManualMarkdownStep

# Define the pipeline using direct class chaining
# Steps will be executed in dependency order:
# 1. ManualMarkdownStep loads markdown input
# 2. EmbeddingStep generates embeddings from markdown content
# 3. QdrantConnectorStep stores embeddings in vector database
pipeline = ManualMarkdownStep >> EmbeddingStep >> QdrantConnectorStep
```

## 🔄 Execution Order

Wurzel automatically resolves and runs all upstream dependencies in the correct order:

1. ManualMarkdownStep runs first to provide data.
2. EmbeddingStep transforms that data into vectors.
3. QdrantConnectorStep persists the result.
