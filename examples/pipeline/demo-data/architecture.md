# Wurzel Pipeline Architecture

Understanding the architecture of Wurzel pipelines is essential for building effective RAG systems.

## Core Concepts

### TypedStep

The fundamental building block of Wurzel pipelines. Each TypedStep defines:

- Input data contract (what data it expects)
- Output data contract (what data it produces)
- Processing logic (how it transforms the data)
- Configuration settings (how it can be customized)

### Pipeline Composition

Steps are composed using the `>>` operator:

```python
source >> processor >> sink
```

This creates a directed acyclic graph (DAG) that DVC can execute efficiently.

### Data Contracts

Wurzel uses Pydantic models to define strict data contracts between steps:

- **MarkdownDataContract**: For document content with metadata
- **EmbeddingResult**: For vectorized text chunks
- **QdrantResult**: For vector database storage results

## Built-in Steps

### ManualMarkdownStep

Loads markdown files from a specified directory. Configuration:

- `FOLDER_PATH`: Directory containing markdown files

### EmbeddingStep

Generates vector embeddings for text content. Features:

- Automatic text splitting and chunking
- Configurable embedding models
- Batch processing for efficiency

### QdrantConnectorStep

Stores embeddings in Qdrant vector database. Capabilities:

- Automatic collection management
- Index creation and optimization
- Metadata preservation

## Extension Points

Create custom steps by inheriting from `TypedStep`:

```python
class CustomStep(TypedStep[CustomSettings, InputContract, OutputContract]):
    def run(self, input_data: InputContract) -> OutputContract:
        # Your processing logic here
        return processed_data
```

## Best Practices

- Keep steps focused on single responsibilities
- Use type hints for better IDE support and validation
- Test steps independently before chaining
- Monitor resource usage for large datasets
