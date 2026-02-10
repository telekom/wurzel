# Building Pipelines

Learn how to define and structure data processing pipelines in Wurzel using the intuitive chaining syntax and modular step architecture.

## What is a Wurzel Pipeline?

A pipeline in Wurzel is a **chain of processing steps** that are connected and executed in sequence. Each step processes the output of the previous one, enabling modular, reusable, and optimally scheduled workflows.

### Key Concepts

- **TypedStep**: Individual processing units with defined input/output contracts
- **Pipeline Chaining**: Steps are connected using the `>>` operator
- **Automatic Dependency Resolution**: Wurzel determines execution order automatically

## Basic Pipeline Structure

### The WZ Utility

Use `WZ(StepClass)` to create step instances and `>>` to chain them:

```python
from wurzel.steps import EmbeddingStep, QdrantConnectorStep
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.utils import WZ

source = WZ(ManualMarkdownStep)
embedding = WZ(EmbeddingStep)
storage = WZ(QdrantConnectorStep)
source >> embedding >> storage
```

## Defining a Complete Pipeline

<a id="defining-a-pipeline"></a>
### Basic Example

Define a function that builds the chain and returns the last step. Wurzel runs upstream steps in order:

```python
from wurzel.core import TypedStep
from wurzel.steps import EmbeddingStep, QdrantConnectorStep
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.utils import WZ


def pipeline() -> TypedStep:
    md = WZ(ManualMarkdownStep)
    embed = WZ(EmbeddingStep)
    db = WZ(QdrantConnectorStep)
    md >> embed >> db
    return db
```

Execution order: ManualMarkdownStep → EmbeddingStep → QdrantConnectorStep.

## Advanced Pipeline Patterns

### Branching

One source can feed multiple downstream steps:

```python
from wurzel.core import TypedStep
from wurzel.steps import EmbeddingStep, QdrantConnectorStep
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.steps.splitter import SimpleSplitterStep
from wurzel.utils import WZ


def branching_pipeline() -> TypedStep:
    source = WZ(ManualMarkdownStep)
    embedding = WZ(EmbeddingStep)
    splitter = WZ(SimpleSplitterStep)
    vector_db = WZ(QdrantConnectorStep)
    source >> embedding >> vector_db
    source >> splitter
    return vector_db
```

### Conditional Processing

Choose steps at build time:

```python
from wurzel.core import TypedStep
from wurzel.steps import EmbeddingStep, QdrantConnectorStep
from wurzel.steps.embedding import TruncatedEmbeddingStep
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.utils import WZ


def conditional_pipeline(use_truncated: bool = False) -> TypedStep:
    source = WZ(ManualMarkdownStep)
    processor = WZ(TruncatedEmbeddingStep) if use_truncated else WZ(EmbeddingStep)
    storage = WZ(QdrantConnectorStep)
    source >> processor >> storage
    return storage
```

## Pipeline Configuration

### Step Settings

Each step can be configured through environment variables or settings classes. See [Creating Custom Steps](creating-steps.md#step-settings) for details.

### Pipeline-Level Configuration

Use environment variables to choose steps:

```python
import os

from wurzel.core import TypedStep
from wurzel.steps import EmbeddingStep, QdrantConnectorStep
from wurzel.steps.embedding import TruncatedEmbeddingStep
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.utils import WZ


def configurable_pipeline() -> TypedStep:
    source = WZ(ManualMarkdownStep)
    use_truncated = os.getenv("EMBEDDING_MODEL", "").lower() == "truncated"
    embedding = WZ(TruncatedEmbeddingStep) if use_truncated else WZ(EmbeddingStep)
    storage = WZ(QdrantConnectorStep)
    source >> embedding >> storage
    return storage
```

## Testing Pipelines

```python
from wurzel.core import TypedStep
from wurzel.steps import EmbeddingStep, QdrantConnectorStep
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.utils import WZ


def test_markdown_step():
    step = WZ(ManualMarkdownStep)
    result = step.run(None)
    assert result is not None
    assert isinstance(result, list)


def pipeline() -> TypedStep:
    md = WZ(ManualMarkdownStep)
    embed = WZ(EmbeddingStep)
    db = WZ(QdrantConnectorStep)
    md >> embed >> db
    return db


def test_complete_pipeline():
    assert pipeline() is not None
```

## Pipeline Optimization

### Parallel Execution

Independent branches can run in parallel (backend-dependent):

```python
from wurzel.core import TypedStep
from wurzel.steps import EmbeddingStep, QdrantConnectorStep
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.utils import WZ


def parallel_pipeline() -> TypedStep:
    source = WZ(ManualMarkdownStep)
    embedding_a = WZ(EmbeddingStep)
    embedding_b = WZ(EmbeddingStep)
    storage = WZ(QdrantConnectorStep)
    source >> embedding_a >> storage
    source >> embedding_b
    return storage
```

Steps cache outputs based on input changes; backends handle persistence.

## Best Practices

### Pipeline Design

1. **Keep steps focused**: Each step should have a single, clear responsibility
2. **Use meaningful names**: Choose descriptive names for your pipeline functions and step variables
3. **Document data flow**: Use comments to explain complex pipeline logic
4. **Handle errors gracefully**: Implement proper error handling in custom steps

### Performance Considerations

1. **Minimize data copying**: Use efficient data structures and avoid unnecessary transformations
2. **Batch processing**: Design steps to handle multiple items efficiently
3. **Resource management**: Be mindful of memory usage in data-intensive steps

## Common Patterns

### ETL-style (extract → transform → load)

```python
from wurzel.core import TypedStep
from wurzel.steps import EmbeddingStep, QdrantConnectorStep
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.steps.splitter import SimpleSplitterStep
from wurzel.utils import WZ


def etl_pipeline() -> TypedStep:
    extractor = WZ(ManualMarkdownStep)
    transformer = WZ(SimpleSplitterStep)
    loader = WZ(EmbeddingStep)
    storage = WZ(QdrantConnectorStep)
    extractor >> transformer >> loader >> storage
    return storage
```

Same pattern works for document ML pipelines (load → split → embed → store).

## Next Steps

- **[Create Custom Steps](creating-steps.md)** - Learn to build your own processing components
- **[Understand Data Contracts](data-contracts.md)** - Deep dive into type-safe data exchange
- **[Explore Backends](../backends/index.md)** - Deploy your pipelines to different platforms

## Additional Resources

- **[Step Examples](https://github.com/telekom/wurzel/tree/main/examples)** - Real-world step implementations
- **[API Documentation](https://deepwiki.com/telekom/wurzel/)** - Complete API reference
- **[Backend Guides](../backends/index.md)** - Platform-specific deployment instructions
