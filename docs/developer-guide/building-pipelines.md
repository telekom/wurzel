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

The `WZ()` utility function is your primary tool for instantiating steps:

```python
from wurzel.utils import WZ
from wurzel.steps.manual_markdown import ManualMarkdownStep

# Create a step instance
markdown_step = WZ(ManualMarkdownStep)
```

### Chaining Steps

Connect steps using the `>>` operator to define data flow:

```python
from wurzel.steps import EmbeddingStep, QdrantConnectorStep
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.utils import WZ

# Define individual steps
source = WZ(ManualMarkdownStep)
embedding = WZ(EmbeddingStep)
storage = WZ(QdrantConnectorStep)

# Chain them together
source >> embedding >> storage
```

## Defining a Complete Pipeline

<a id="defining-a-pipeline"></a>
### Basic Example

Here's a complete pipeline that processes markdown documents, generates embeddings, and stores them in a vector database:

```python
from wurzel.steps import (
    EmbeddingStep,
    QdrantConnectorStep,
)
from wurzel.utils import WZ
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.core import TypedStep

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

### Execution Order

Even though the function returns only the last step (`db`), Wurzel automatically resolves and runs all upstream dependencies in the correct order:

1. **ManualMarkdownStep** runs first to provide data
2. **EmbeddingStep** transforms that data into vectors
3. **QdrantConnectorStep** persists the result

## Advanced Pipeline Patterns

### Branching Pipelines

You can create branches in your pipeline where one step feeds into multiple downstream steps:

```python
def branching_pipeline() -> TypedStep:
    """Pipeline with branching data flow."""

    # Source step
    source = WZ(ManualMarkdownStep)

    # Processing steps
    embedding = WZ(EmbeddingStep)
    preprocessor = WZ(TextPreprocessorStep)

    # Branch: source feeds into both embedding and preprocessor
    source >> embedding
    source >> preprocessor

    # Converge: both feed into final storage
    vector_db = WZ(QdrantConnectorStep)
    processed_storage = WZ(ProcessedTextStorageStep)

    embedding >> vector_db
    preprocessor >> processed_storage

    # Return one of the final steps (or create a step that depends on both)
    return vector_db
```

### Multi-Input Steps

Some steps can accept input from multiple upstream steps:

```python
def multi_input_pipeline() -> TypedStep:
    """Pipeline where a step receives multiple inputs."""

    text_source = WZ(TextSourceStep)
    image_source = WZ(ImageSourceStep)

    # Multi-modal step that accepts both text and images
    multimodal_processor = WZ(MultiModalProcessorStep)

    # Both sources feed into the processor
    text_source >> multimodal_processor
    image_source >> multimodal_processor

    storage = WZ(MultiModalStorageStep)
    multimodal_processor >> storage

    return storage
```

### Conditional Processing

Create pipelines with conditional logic using step parameters:

```python
def conditional_pipeline(use_advanced_processing: bool = False) -> TypedStep:
    """Pipeline with conditional processing paths."""

    source = WZ(ManualMarkdownStep)

    if use_advanced_processing:
        processor = WZ(AdvancedEmbeddingStep)
    else:
        processor = WZ(BasicEmbeddingStep)

    storage = WZ(QdrantConnectorStep)

    source >> processor >> storage

    return storage
```

## Pipeline Configuration

### Step Settings

Each step can be configured through environment variables or settings classes. See [Creating Custom Steps](creating-steps.md#step-settings) for details.

### Pipeline-Level Configuration

Configure entire pipelines through environment variables:

```python
import os
from wurzel.steps import EmbeddingStep
from wurzel.utils import WZ

def configurable_pipeline() -> TypedStep:
    """Pipeline that adapts based on environment configuration."""

    source = WZ(ManualMarkdownStep)

    # Configure embedding step based on environment
    embedding_model = os.getenv('EMBEDDING_MODEL', 'default')
    if embedding_model == 'advanced':
        embedding = WZ(AdvancedEmbeddingStep)
    else:
        embedding = WZ(EmbeddingStep)

    storage = WZ(QdrantConnectorStep)

    source >> embedding >> storage
    return storage
```

## Testing Pipelines

### Unit Testing Individual Steps

Test steps in isolation:

```python
import pytest
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.utils import WZ

def test_markdown_step():
    """Test the markdown step in isolation."""
    step = WZ(ManualMarkdownStep)
    result = step.run(None)

    assert result is not None
    assert len(result) > 0
```

### Integration Testing

Test complete pipeline flows:

```python
def test_complete_pipeline():
    """Test the entire pipeline execution."""
    pipeline_result = pipeline()

    # Execute the pipeline (this would typically be done by a backend)
    # result = execute_pipeline(pipeline_result)

    # Assert pipeline structure
    assert pipeline_result is not None
    # Add more specific assertions based on your pipeline
```

## Pipeline Optimization

### Parallel Execution

Wurzel can automatically parallelize steps that don't depend on each other:

```python
def parallel_pipeline() -> TypedStep:
    """Pipeline optimized for parallel execution."""

    source = WZ(ManualMarkdownStep)

    # These can run in parallel since they're independent
    embedding_a = WZ(EmbeddingStepA)
    embedding_b = WZ(EmbeddingStepB)

    source >> embedding_a
    source >> embedding_b

    # This step waits for both embeddings
    combiner = WZ(EmbeddingCombinerStep)
    embedding_a >> combiner
    embedding_b >> combiner

    storage = WZ(QdrantConnectorStep)
    combiner >> storage

    return storage
```

### Caching and Persistence

Steps automatically cache their outputs based on input changes. This is handled transparently by the backend execution engines.

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

### Code Organization

```python
# Good: Organized and readable
def document_processing_pipeline() -> TypedStep:
    """
    Processes documents through embedding and storage.

    Pipeline flow:
    1. Load markdown documents
    2. Generate embeddings
    3. Store in vector database
    """
    # Data ingestion
    documents = WZ(ManualMarkdownStep)

    # Processing
    embeddings = WZ(EmbeddingStep)

    # Storage
    storage = WZ(QdrantConnectorStep)

    # Pipeline definition
    documents >> embeddings >> storage

    return storage
```

## Common Patterns

### ETL Pipeline

```python
def etl_pipeline() -> TypedStep:
    """Extract, Transform, Load pipeline."""

    # Extract
    extractor = WZ(DataExtractionStep)

    # Transform
    transformer = WZ(DataTransformationStep)
    validator = WZ(DataValidationStep)

    # Load
    loader = WZ(DataLoadingStep)

    # Chain
    extractor >> transformer >> validator >> loader

    return loader
```

### ML Pipeline

```python
def ml_pipeline() -> TypedStep:
    """Machine learning pipeline with training and inference."""

    # Data preparation
    data_loader = WZ(MLDataLoaderStep)
    preprocessor = WZ(DataPreprocessorStep)

    # Model training
    trainer = WZ(ModelTrainingStep)

    # Model evaluation
    evaluator = WZ(ModelEvaluationStep)

    # Pipeline
    data_loader >> preprocessor >> trainer >> evaluator

    return evaluator
```

## Next Steps

- **[Create Custom Steps](creating-steps.md)** - Learn to build your own processing components
- **[Understand Data Contracts](data-contracts.md)** - Deep dive into type-safe data exchange
- **[Explore Backends](../backends/index.md)** - Deploy your pipelines to different platforms

## Additional Resources

- **[Step Examples](https://github.com/telekom/wurzel/tree/main/examples)** - Real-world step implementations
- **[API Documentation](https://deepwiki.com/telekom/wurzel/)** - Complete API reference
- **[Backend Guides](../backends/index.md)** - Platform-specific deployment instructions
