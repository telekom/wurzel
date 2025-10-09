# Creating Custom Steps

Learn how to build your own data processing steps in Wurzel, from simple data sources to complex transformation components.

## Step Types Overview

Wurzel provides two main types of steps:

- **Data Source Steps (WurzelTips)**: Entry points that ingest data from external sources
- **Processing Steps (WurzelSteps)**: Transform data from upstream steps

Both types follow the same `TypedStep` interface but serve different roles in your pipeline.

## Step Architecture

### The TypedStep Interface

All steps inherit from `TypedStep`, which provides:

```python
class TypedStep[TSettings, TInput, TOutput]:
    """
    Base class for all pipeline steps.

    Type parameters:
    - TSettings: Configuration schema (Pydantic BaseModel)
    - TInput: Input data type (or None for data sources)
    - TOutput: Output data type
    """

    def __init__(self) -> None:
        """Initialize the step (setup logic goes here)."""
        pass

    def run(self, inpt: TInput) -> TOutput:
        """Process input data and return output."""
        raise NotImplementedError

    def finalize(self) -> None:
        """Cleanup logic called after pipeline execution."""
        pass
```

### Step Lifecycle

1. **Initialization** (`__init__`): Setup connections, create resources
2. **Execution** (`run`): Process data (may be called multiple times)
3. **Finalization** (`finalize`): Cleanup resources, close connections

> ⚠️ **Important**: The `run` method may be executed multiple times for different upstream dependencies. Put setup logic in `__init__`, not `run`.

## Creating Data Source Steps

Data source steps introduce data into your pipeline. They have `None` as their input type since they don't depend on previous steps.

### Basic Data Source

```python
from typing import Any
from wurzel.core import TypedStep
from wurzel.datacontract import MarkdownDataContract
from wurzel.meta.settings import Settings

class MySettings(Settings):
    """Configuration for MyDatasourceStep."""
    data_path: str = "./data"
    file_pattern: str = "*.md"

class MyDatasourceStep(TypedStep[MySettings, None, list[MarkdownDataContract]]):
    """Data source step for loading Markdown files from a configurable path."""

    def __init__(self):
        """Initialize the data source."""
        self.settings = MySettings()
        # Setup logic here (validate paths, check permissions, etc.)

    def run(self, inpt: None) -> list[MarkdownDataContract]:
        """Load and return markdown documents."""
        import glob
        import os

        pattern = os.path.join(self.settings.data_path, self.settings.file_pattern)
        files = glob.glob(pattern)

        documents = []
        for file_path in files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            doc = MarkdownDataContract(
                content=content,
                source=file_path,
                metadata={"file_path": file_path}
            )
            documents.append(doc)

        return documents
```

### Advanced Data Source with Database

```python
import sqlite3
from wurzel.core import TypedStep
from wurzel.datacontract import MarkdownDataContract
from wurzel.meta.settings import Settings

class DatabaseSettings(Settings):
    """Database connection settings."""
    db_path: str = "data.db"
    table_name: str = "documents"
    query: str = "SELECT content, source, metadata FROM documents"

class DatabaseSourceStep(TypedStep[DatabaseSettings, None, list[MarkdownDataContract]]):
    """Load documents from a SQLite database."""

    def __init__(self):
        """Initialize database connection."""
        self.settings = DatabaseSettings()
        self.connection = sqlite3.connect(self.settings.db_path)
        self.connection.row_factory = sqlite3.Row  # Enable column access by name

    def run(self, inpt: None) -> list[MarkdownDataContract]:
        """Query database and return documents."""
        cursor = self.connection.cursor()
        cursor.execute(self.settings.query)

        documents = []
        for row in cursor.fetchall():
            doc = MarkdownDataContract(
                content=row['content'],
                source=row['source'],
                metadata=eval(row['metadata']) if row['metadata'] else {}
            )
            documents.append(doc)

        return documents

    def finalize(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
```

## Creating Processing Steps

Processing steps transform data from upstream steps. They can filter, validate, transform, or enrich data.

### Filter Step

```python
from wurzel.core import TypedStep
from wurzel.datacontract import MarkdownDataContract
from wurzel.meta.settings import Settings

class FilterSettings(Settings):
    """Settings for document filtering."""
    min_length: int = 100
    max_length: int = 10000
    required_keywords: list[str] = []

class DocumentFilterStep(TypedStep[FilterSettings, list[MarkdownDataContract], list[MarkdownDataContract]]):
    """Filter documents based on length and keyword criteria."""

    def __init__(self):
        """Initialize the filter."""
        self.settings = FilterSettings()

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Filter documents based on criteria."""
        filtered_docs = []

        for doc in inpt:
            # Length filter
            content_length = len(doc.content)
            if content_length < self.settings.min_length or content_length > self.settings.max_length:
                continue

            # Keyword filter
            if self.settings.required_keywords:
                content_lower = doc.content.lower()
                if not all(keyword.lower() in content_lower for keyword in self.settings.required_keywords):
                    continue

            filtered_docs.append(doc)

        return filtered_docs
```

### Transformation Step

```python
import pandas as pd
from wurzel.core import TypedStep
from wurzel.datacontract import MarkdownDataContract, EmbeddingResult
from wurzel.meta.settings import Settings

class EmbeddingSettings(Settings):
    """Settings for embedding generation."""
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    batch_size: int = 32

class CustomEmbeddingStep(TypedStep[EmbeddingSettings, list[MarkdownDataContract], pd.DataFrame[EmbeddingResult]]):
    """Transform documents into embeddings stored in a DataFrame."""

    def __init__(self):
        """Initialize the embedding model."""
        self.settings = EmbeddingSettings()

        # Import and initialize model
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(self.settings.model_name)

    def run(self, inpt: list[MarkdownDataContract]) -> pd.DataFrame[EmbeddingResult]:
        """Generate embeddings for input documents."""

        # Extract texts for embedding
        texts = [doc.content for doc in inpt]

        # Generate embeddings in batches
        embeddings = self.model.encode(
            texts,
            batch_size=self.settings.batch_size,
            show_progress_bar=True
        )

        # Create result objects
        results = []
        for i, (doc, embedding) in enumerate(zip(inpt, embeddings)):
            result = EmbeddingResult(
                id=f"doc_{i}",
                content=doc.content,
                source=doc.source,
                metadata=doc.metadata,
                embedding=embedding.tolist(),
                embedding_model=self.settings.model_name
            )
            results.append(result)

        # Convert to DataFrame
        return pd.DataFrame(results)
```

### Validation Step

```python
from wurzel.core import TypedStep
from wurzel.datacontract import MarkdownDataContract
from wurzel.meta.settings import Settings

class ValidationSettings(Settings):
    """Settings for document validation."""
    check_encoding: bool = True
    check_structure: bool = True
    max_errors: int = 5

class DocumentValidationStep(TypedStep[ValidationSettings, list[MarkdownDataContract], list[MarkdownDataContract]]):
    """Validate documents and filter out invalid ones."""

    def __init__(self):
        """Initialize validator."""
        self.settings = ValidationSettings()
        self.error_count = 0

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Validate and filter documents."""
        valid_docs = []

        for doc in inpt:
            if self._validate_document(doc):
                valid_docs.append(doc)
            else:
                self.error_count += 1
                if self.error_count >= self.settings.max_errors:
                    raise RuntimeError(f"Too many validation errors: {self.error_count}")

        return valid_docs

    def _validate_document(self, doc: MarkdownDataContract) -> bool:
        """Validate a single document."""

        # Check encoding
        if self.settings.check_encoding:
            try:
                doc.content.encode('utf-8')
            except UnicodeEncodeError:
                return False

        # Check structure
        if self.settings.check_structure:
            if not doc.content.strip():
                return False

            if len(doc.content) < 10:  # Minimum content length
                return False

        return True
```

## Advanced Patterns

### Multi-Input Steps

Some steps need to combine data from multiple sources:

```python
from typing import Union
from wurzel.core import TypedStep
from wurzel.datacontract import MarkdownDataContract
from wurzel.meta.settings import Settings

class MergerSettings(Settings):
    """Settings for document merging."""
    merge_strategy: str = "concatenate"  # or "interleave"

class DocumentMergerStep(TypedStep[MergerSettings, Union[list[MarkdownDataContract], list[MarkdownDataContract]], list[MarkdownDataContract]]):
    """Merge documents from multiple sources."""

    def __init__(self):
        """Initialize merger."""
        self.settings = MergerSettings()
        self.collected_inputs = []

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Collect inputs and merge when all are available."""
        self.collected_inputs.append(inpt)

        # In a real implementation, you'd need logic to determine
        # when all inputs have been received
        if len(self.collected_inputs) >= 2:  # Expecting 2 sources
            return self._merge_documents()

        return []  # Return empty until all inputs received

    def _merge_documents(self) -> list[MarkdownDataContract]:
        """Merge collected documents."""
        if self.settings.merge_strategy == "concatenate":
            # Simply concatenate all documents
            all_docs = []
            for doc_list in self.collected_inputs:
                all_docs.extend(doc_list)
            return all_docs

        elif self.settings.merge_strategy == "interleave":
            # Interleave documents from different sources
            # Implementation depends on your specific needs
            pass

        return []
```

### Stateful Processing

For steps that need to maintain state across executions:

```python
from collections import defaultdict
from wurzel.core import TypedStep
from wurzel.datacontract import MarkdownDataContract
from wurzel.meta.settings import Settings

class DeduplicationSettings(Settings):
    """Settings for deduplication."""
    similarity_threshold: float = 0.9
    hash_algorithm: str = "md5"

class DeduplicationStep(TypedStep[DeduplicationSettings, list[MarkdownDataContract], list[MarkdownDataContract]]):
    """Remove duplicate documents based on content similarity."""

    def __init__(self):
        """Initialize deduplication."""
        self.settings = DeduplicationSettings()
        self.seen_hashes = set()
        self.document_index = defaultdict(list)

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Remove duplicates from input documents."""
        import hashlib

        unique_docs = []

        for doc in inpt:
            # Generate content hash
            if self.settings.hash_algorithm == "md5":
                content_hash = hashlib.md5(doc.content.encode()).hexdigest()
            else:
                content_hash = hashlib.sha256(doc.content.encode()).hexdigest()

            # Check if we've seen this content before
            if content_hash not in self.seen_hashes:
                self.seen_hashes.add(content_hash)
                unique_docs.append(doc)
                self.document_index[content_hash].append(doc.source)

        return unique_docs

    def finalize(self) -> None:
        """Log deduplication statistics."""
        total_seen = len(self.seen_hashes)
        duplicates = sum(len(sources) - 1 for sources in self.document_index.values())
        print(f"Deduplication complete: {total_seen} unique documents, {duplicates} duplicates removed")
```

## Step Settings and Configuration

<a id="step-settings"></a>

### Environment Variable Integration

Wurzel automatically maps environment variables to step settings:

```python
class APISettings(Settings):
    """Settings for API-based data source."""
    api_key: str  # Maps to API_KEY environment variable
    base_url: str = "https://api.example.com"  # Default value
    timeout: int = 30
    max_retries: int = 3

# Environment variables:
# API_KEY=your_secret_key
# BASE_URL=https://custom.api.com  (optional override)
# TIMEOUT=60  (optional override)
```

### Nested Configuration

For complex configuration structures:

```python
class DatabaseConfig(Settings):
    """Database connection configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "wurzel"
    username: str = "user"
    password: str = "password"

class ProcessingConfig(Settings):
    """Processing configuration."""
    batch_size: int = 100
    parallel_workers: int = 4

class ComplexStepSettings(Settings):
    """Complex step configuration."""
    database: DatabaseConfig = DatabaseConfig()
    processing: ProcessingConfig = ProcessingConfig()
    debug_mode: bool = False

# Environment variables:
# DATABASE__HOST=production-db.example.com
# DATABASE__PORT=5433
# PROCESSING__BATCH_SIZE=200
# DEBUG_MODE=true
```

## Testing Custom Steps

### Unit Testing

```python
import pytest
from unittest.mock import Mock, patch
from your_module import MyDatasourceStep, MySettings

def test_datasource_step():
    """Test the data source step."""

    # Create test settings
    settings = MySettings(data_path="./test_data", file_pattern="*.md")

    # Mock file system
    with patch('glob.glob') as mock_glob, \
         patch('builtins.open', create=True) as mock_open:

        mock_glob.return_value = ["test1.md", "test2.md"]
        mock_open.return_value.__enter__.return_value.read.return_value = "# Test Content"

        # Test step execution
        step = MyDatasourceStep()
        step.settings = settings
        result = step.run(None)

        assert len(result) == 2
        assert result[0].content == "# Test Content"

def test_filter_step():
    """Test the document filter step."""
    from your_module import DocumentFilterStep, FilterSettings
    from wurzel.datacontract import MarkdownDataContract

    # Create test data
    docs = [
        MarkdownDataContract(content="Short", source="test1"),
        MarkdownDataContract(content="This is a longer document with enough content", source="test2"),
        MarkdownDataContract(content="A" * 200, source="test3"),  # Long enough
    ]

    # Test filtering
    step = DocumentFilterStep()
    step.settings = FilterSettings(min_length=50)
    result = step.run(docs)

    assert len(result) == 2  # Short document filtered out
    assert result[0].content == "This is a longer document with enough content"
```

### Integration Testing

```python
def test_pipeline_with_custom_steps():
    """Test a complete pipeline using custom steps."""
    from wurzel.utils import WZ

    # Create pipeline
    source = WZ(MyDatasourceStep)
    filter_step = WZ(DocumentFilterStep)
    embedding = WZ(CustomEmbeddingStep)

    source >> filter_step >> embedding

    # Test pipeline structure
    assert filter_step.inputs == [source]
    assert embedding.inputs == [filter_step]
```

## Best Practices

### Error Handling

```python
class RobustProcessingStep(TypedStep[Settings, list[MarkdownDataContract], list[MarkdownDataContract]]):
    """Example of robust error handling in steps."""

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Process documents with error handling."""
        processed_docs = []
        errors = []

        for i, doc in enumerate(inpt):
            try:
                processed_doc = self._process_document(doc)
                processed_docs.append(processed_doc)
            except Exception as e:
                error_msg = f"Failed to process document {i}: {str(e)}"
                errors.append(error_msg)
                # Log error but continue processing
                print(f"Warning: {error_msg}")

        if errors and len(errors) > len(inpt) * 0.5:  # More than 50% failed
            raise RuntimeError(f"Too many processing errors: {len(errors)}/{len(inpt)}")

        return processed_docs
```

### Resource Management

```python
class ResourceManagedStep(TypedStep[Settings, list[MarkdownDataContract], list[MarkdownDataContract]]):
    """Example of proper resource management."""

    def __init__(self):
        """Initialize with resource management."""
        self.connection = None
        self.temp_files = []

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Process with proper resource handling."""
        try:
            # Your processing logic here
            return self._process_documents(inpt)
        except Exception:
            # Clean up on error
            self._cleanup_resources()
            raise

    def finalize(self) -> None:
        """Ensure cleanup happens."""
        self._cleanup_resources()

    def _cleanup_resources(self):
        """Clean up allocated resources."""
        if self.connection:
            self.connection.close()
            self.connection = None

        for temp_file in self.temp_files:
            try:
                import os
                os.unlink(temp_file)
            except OSError:
                pass
        self.temp_files.clear()
```

## Next Steps

- **[Understand Data Contracts](data-contracts.md)** - Learn about type-safe data exchange
- **[Explore Backend Integration](../backends/index.md)** - Deploy your custom steps

## Additional Resources

- **[API Documentation](https://deepwiki.com/telekom/wurzel/)** - Complete TypedStep API reference
- **[Built-in Steps](https://deepwiki.com/telekom/wurzel/steps/)** - Examples of existing step implementations
- **[Testing Guidelines](getting-started.md#running-tests)** - Best practices for testing steps
