# Data Contracts

Understand Wurzel's type-safe data exchange system that ensures data integrity and enables seamless communication between pipeline steps.


## Overview

Wurzel implements a **type-safe pipeline system** where data flows between processing steps through strictly defined **Data Contracts**. These contracts ensure data integrity, enable automatic validation, and provide clear interfaces between pipeline components.

### Key Benefits

- **Type Safety**: Compile-time and runtime validation
- **Modularity**: Interchangeable steps with clear interfaces
- **Persistence**: Automatic serialization between steps
- **Scalability**: Efficient DataFrame-based bulk processing

## Data Contract Fundamentals

### The DataModel Interface

All data contracts in Wurzel implement the abstract `DataModel` interface:

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar('T', bound='DataModel')

class DataModel(ABC):
    """
    Abstract base class for all data models in Wurzel.

    Provides serialization and deserialization capabilities
    for data exchange between pipeline steps.
    """

    @abstractmethod
    def save_to_path(self, path: Path) -> None:
        """Save the data model to the specified path."""
        pass

    @classmethod
    @abstractmethod
    def load_from_path(cls: type[T], path: Path) -> T:
        """Load the data model from the specified path."""
        pass
```

This interface ensures that all data types can be:

- **Persisted** to disk between pipeline steps
- **Loaded** automatically by the next step
- **Validated** for type correctness

### Supported Base Data Types

Wurzel provides two concrete implementations of the `DataModel` interface:

#### PydanticModel

For structured objects and metadata:

```python
from pydantic import BaseModel
from wurzel.datacontract import PydanticModel

class DocumentMetadata(PydanticModel):
    """Example of a Pydantic-based data contract."""
    title: str
    author: str
    created_date: str
    tags: list[str] = []

    # Inherited methods for serialization
    def save_to_path(self, path: Path) -> None:
        """Save as JSON file."""
        with open(path, 'w') as f:
            f.write(self.model_dump_json())

    @classmethod
    def load_from_path(cls, path: Path) -> 'DocumentMetadata':
        """Load from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)
        return cls(**data)
```

**Features**:

- **Serialization**: JSON format (`.json` files)
- **Use cases**: Individual documents, metadata, configuration objects
- **Validation**: Automatic Pydantic validation

#### DataFrame

For bulk data processing:

```python
import pandas as pd
from wurzel.datacontract import DataFrame

# Type-safe DataFrame with specific row type
EmbeddingDataFrame = DataFrame[EmbeddingResult]

class EmbeddingResult(PydanticModel):
    """Data contract for embedding results."""
    id: str
    content: str
    source: str
    metadata: dict[str, Any]
    embedding: list[float]
    embedding_model: str
```

**Features**:

- **Serialization**: Parquet format (`.parquet` files)
- **Use cases**: Large datasets, tabular data, bulk processing
- **Performance**: Optimized for high-volume data operations

## Built-in Data Contracts

### MarkdownDataContract

The primary contract for document processing pipelines:

```python
from wurzel.datacontract import MarkdownDataContract

# Create a markdown document
doc = MarkdownDataContract(
    content="# My Document\n\nThis is the content.",
    source="document.md",
    metadata={
        "author": "John Doe",
        "created": "2024-01-01",
        "tags": ["documentation", "markdown"]
    }
)

# Access fields
print(doc.content)    # The markdown content
print(doc.source)     # Source identifier/path
print(doc.metadata)   # Additional metadata dictionary
```

**Fields**:

- `content`: The actual markdown text
- `source`: Source identifier (file path, URL, etc.)
- `metadata`: Flexible dictionary for additional information

**Usage**: Document ingestion, text processing, content management

### EmbeddingResult

For vector embedding data:

```python
from wurzel.datacontract import EmbeddingResult

# Create an embedding result
embedding = EmbeddingResult(
    id="doc_001",
    content="Original text content",
    source="source_document.md",
    metadata={"processed_at": "2024-01-01T10:00:00Z"},
    embedding=[0.1, 0.2, 0.3, ...],  # Vector representation
    embedding_model="sentence-transformers/all-MiniLM-L6-v2"
)
```

**Fields**:

- `id`: Unique identifier for the embedding
- `content`: Original text that was embedded
- `source`: Source of the original content
- `metadata`: Additional context information
- `embedding`: The actual vector representation
- `embedding_model`: Model used to generate the embedding

**Usage**: Vector databases, similarity search, ML pipelines

## Creating Custom Data Contracts

### Simple Custom Contract

```python
from wurzel.datacontract import PydanticModel
from typing import Optional
from datetime import datetime

class ProductDataContract(PydanticModel):
    """Data contract for product information."""

    # Required fields
    product_id: str
    name: str
    price: float

    # Optional fields with defaults
    description: Optional[str] = None
    category: str = "general"
    in_stock: bool = True

    # Complex fields
    tags: list[str] = []
    attributes: dict[str, str] = {}

    # Computed fields
    created_at: datetime = datetime.now()

    # Validation
    @validator('price')
    def validate_price(cls, v):
        if v < 0:
            raise ValueError('Price must be positive')
        return v

    @validator('product_id')
    def validate_id_format(cls, v):
        if not v.startswith('PROD_'):
            raise ValueError('Product ID must start with PROD_')
        return v

# Usage in a step
class ProductProcessingStep(TypedStep[Settings, list[ProductDataContract], list[ProductDataContract]]):
    """Process product data with type safety."""

    def run(self, inpt: list[ProductDataContract]) -> list[ProductDataContract]:
        processed_products = []

        for product in inpt:
            # Type-safe access to fields
            if product.price > 100:
                product.tags.append("premium")

            # Validation happens automatically
            processed_products.append(product)

        return processed_products
```

### Complex Hierarchical Contract

```python
from wurzel.datacontract import PydanticModel
from typing import Union, Literal
from enum import Enum

class DocumentType(str, Enum):
    """Enumeration of document types."""
    ARTICLE = "article"
    MANUAL = "manual"
    FAQ = "faq"
    TUTORIAL = "tutorial"

class AuthorInfo(PydanticModel):
    """Nested contract for author information."""
    name: str
    email: str
    organization: Optional[str] = None

class DocumentSection(PydanticModel):
    """Contract for document sections."""
    title: str
    content: str
    level: int = 1  # Heading level
    subsections: list['DocumentSection'] = []  # Self-referential

class RichDocumentContract(PydanticModel):
    """Complex document contract with hierarchical structure."""

    # Basic information
    title: str
    document_type: DocumentType
    language: str = "en"

    # Content structure
    sections: list[DocumentSection]

    # Metadata
    author: AuthorInfo
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Processing information
    word_count: Optional[int] = None
    reading_time_minutes: Optional[float] = None

    # Computed properties
    @property
    def total_sections(self) -> int:
        """Count total sections including subsections."""
        def count_sections(sections: list[DocumentSection]) -> int:
            count = len(sections)
            for section in sections:
                count += count_sections(section.subsections)
            return count
        return count_sections(self.sections)

    # Custom validation
    @validator('sections')
    def validate_sections(cls, v):
        if not v:
            raise ValueError('Document must have at least one section')
        return v
```

### DataFrame-based Contracts

For high-volume data processing:

```python
import pandas as pd
from wurzel.datacontract import DataFrame, PydanticModel

class LogEntry(PydanticModel):
    """Single log entry contract."""
    timestamp: datetime
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    message: str
    source: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: dict[str, Any] = {}

# Type-safe DataFrame for bulk log processing
LogDataFrame = DataFrame[LogEntry]

class LogProcessingStep(TypedStep[Settings, LogDataFrame, LogDataFrame]):
    """Process log entries in bulk."""

    def run(self, inpt: LogDataFrame) -> LogDataFrame:
        """Filter and enrich log entries."""

        # Convert to pandas DataFrame for processing
        df = inpt.to_pandas()

        # Bulk operations
        df = df[df['level'].isin(['WARNING', 'ERROR'])]  # Filter
        df['processed_at'] = datetime.now()  # Add column

        # Convert back to type-safe DataFrame
        processed_entries = []
        for _, row in df.iterrows():
            entry = LogEntry(
                timestamp=row['timestamp'],
                level=row['level'],
                message=row['message'],
                source=row['source'],
                user_id=row.get('user_id'),
                session_id=row.get('session_id'),
                metadata=row.get('metadata', {})
            )
            processed_entries.append(entry)

        return DataFrame(processed_entries)
```

## Data Contract Best Practices

### Design Guidelines

1. **Keep contracts focused**: Each contract should represent a single, well-defined data structure
2. **Use descriptive names**: Make field names and contract names self-documenting
3. **Provide defaults**: Use sensible defaults for optional fields
4. **Add validation**: Use Pydantic validators for data integrity
5. **Document everything**: Add docstrings and field descriptions

```python
class WellDesignedContract(PydanticModel):
    """
    Example of a well-designed data contract.

    This contract represents a processed document with
    quality metrics and processing metadata.
    """

    # Core data (required)
    document_id: str = Field(..., description="Unique document identifier")
    content: str = Field(..., description="Processed document content")

    # Metadata (optional with defaults)
    language: str = Field("en", description="Document language code")
    processing_version: str = Field("1.0", description="Processing pipeline version")

    # Quality metrics
    quality_score: float = Field(0.0, ge=0.0, le=1.0, description="Document quality score (0-1)")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Processing confidence (0-1)")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None

    @validator('document_id')
    def validate_document_id(cls, v):
        """Ensure document ID follows expected format."""
        if not re.match(r'^DOC_\d{8}_\d{6}$', v):
            raise ValueError('Document ID must match format: DOC_YYYYMMDD_HHMMSS')
        return v
```

### Performance Considerations

1. **Choose the right base type**:
   - Use `PydanticModel` for individual objects
   - Use `DataFrame` for bulk data processing

2. **Minimize serialization overhead**:
   - Keep contracts as simple as possible
   - Avoid deeply nested structures when not necessary

3. **Optimize for your use case**:
   - For analytics: Use DataFrame with efficient column types
   - For individual processing: Use PydanticModel with focused fields

### Migration and Versioning

Handle contract evolution gracefully:

```python
from typing import Union

class DocumentContractV1(PydanticModel):
    """Original document contract."""
    title: str
    content: str
    author: str

class DocumentContractV2(PydanticModel):
    """Enhanced document contract with structured metadata."""
    title: str
    content: str
    author: AuthorInfo  # Now a structured object
    version: int = 2

# Migration function
def migrate_document_v1_to_v2(old_doc: DocumentContractV1) -> DocumentContractV2:
    """Migrate from V1 to V2 contract."""
    return DocumentContractV2(
        title=old_doc.title,
        content=old_doc.content,
        author=AuthorInfo(
            name=old_doc.author,
            email="unknown@example.com",  # Default for missing data
            organization=None
        )
    )

# Version-aware step
class VersionAwareStep(TypedStep[Settings, Union[DocumentContractV1, DocumentContractV2], DocumentContractV2]):
    """Step that handles multiple contract versions."""

    def run(self, inpt: Union[DocumentContractV1, DocumentContractV2]) -> DocumentContractV2:
        if isinstance(inpt, DocumentContractV1):
            return migrate_document_v1_to_v2(inpt)
        return inpt
```

## Testing Data Contracts

### Unit Testing Contracts

```python
import pytest
from datetime import datetime
from your_module import ProductDataContract

def test_product_contract_creation():
    """Test basic contract creation and validation."""
    product = ProductDataContract(
        product_id="PROD_001",
        name="Test Product",
        price=29.99
    )

    assert product.product_id == "PROD_001"
    assert product.name == "Test Product"
    assert product.price == 29.99
    assert product.in_stock is True  # Default value

def test_product_contract_validation():
    """Test contract validation rules."""

    # Test invalid price
    with pytest.raises(ValueError, match="Price must be positive"):
        ProductDataContract(
            product_id="PROD_001",
            name="Test Product",
            price=-10.0
        )

    # Test invalid ID format
    with pytest.raises(ValueError, match="Product ID must start with PROD_"):
        ProductDataContract(
            product_id="INVALID_001",
            name="Test Product",
            price=29.99
        )

def test_product_contract_serialization():
    """Test contract serialization and deserialization."""
    import tempfile
    from pathlib import Path

    # Create test product
    original = ProductDataContract(
        product_id="PROD_001",
        name="Test Product",
        price=29.99,
        tags=["electronics", "gadget"]
    )

    # Test serialization
    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = Path(temp_dir) / "product.json"
        original.save_to_path(file_path)

        # Test deserialization
        loaded = ProductDataContract.load_from_path(file_path)

        assert loaded.product_id == original.product_id
        assert loaded.name == original.name
        assert loaded.price == original.price
        assert loaded.tags == original.tags
```

### Integration Testing with Steps

```python
def test_step_with_custom_contract():
    """Test step using custom data contract."""
    from your_module import ProductProcessingStep, ProductDataContract

    # Create test data
    products = [
        ProductDataContract(product_id="PROD_001", name="Cheap Item", price=5.99),
        ProductDataContract(product_id="PROD_002", name="Expensive Item", price=150.00),
    ]

    # Test step execution
    step = ProductProcessingStep()
    result = step.run(products)

    # Verify processing logic
    assert len(result) == 2
    assert "premium" not in result[0].tags  # Cheap item
    assert "premium" in result[1].tags      # Expensive item
```

## Next Steps

- **[Create Custom Steps](creating-steps.md)** - Build steps that use your custom contracts
- **[Explore Backend Integration](../backends/introduction.md)** - Deploy pipelines with custom contracts
- **[Review Examples](../examples/)** - See real-world contract implementations

## Additional Resources

- **[Pydantic Documentation](https://docs.pydantic.dev/)** - Learn more about Pydantic features
- **[Pandas Documentation](https://pandas.pydata.org/docs/)** - DataFrame operations and optimization
- **[API Documentation](https://deepwiki.com/telekom/wurzel/)** - Complete data contract API reference
