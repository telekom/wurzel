# 🔗 Defining a Pipeline in Wurzel

At the heart of Wurzel lies the concept of the pipeline — a chain of steps that are connected and executed in sequence. Each step processes the output of the previous one, enabling modular, reusable, and optimally scheduled workflows.

## 🧩 What is a Wurzel Pipeline?

A pipeline in Wurzel is a chain of TypedStep instances, linked using the >> operator. This chaining mechanism makes it easy to define complex data processing flows that remain clean and composable.

Wurzel optimizes the execution of these pipelines automatically based on dependencies and contracts.

## 🛠️ How to Define a Pipeline

To define a pipeline:

1. Instantiate your steps using the helper WZ(...).
2. Chain them together using >>.
3. Return the final step (which implicitly carries the full chain).

### 📦 Example

```python
from wurzel.steps import (
    EmbeddingStep,
    QdrantConnectorStep,
)
from wurzel.utils import WZ
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.step import TypedStep

def pipeline() -> TypedStep:
    """Defines a Wurzel pipeline that embeds manual markdown and stores it in Qdrant."""

    # Step 1: Load markdown input manually
    md = WZ(ManualMarkdownStep)

    # Step 2: Generate embeddings from markdown content
    embed = WZ(EmbeddingStep)

    # Step 3: Store embeddings in a Qdrant vector database
    db = WZ(QdrantConnectorStep)

    # Chain the steps
    md >> embed >> db

    # Return the final step in the chain
    return db
```

## 🔄 Execution Order

Even though the function returns only the last step (db), Wurzel automatically resolves and runs all upstream dependencies in the correct order:

1. ManualMarkdownStep runs first to provide data.
2. EmbeddingStep transforms that data into vectors.
3. QdrantConnectorStep persists the result.
