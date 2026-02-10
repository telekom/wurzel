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

Contracts implement `DataModel`: **save_to_path** and **load_from_path** for persistence between steps.

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Self, TypeVar

T = TypeVar("T", bound="DataModel")


class DataModel(ABC):
    @classmethod
    @abstractmethod
    def save_to_path(cls, path: Path, obj: Self | list[Self]) -> Path: ...

    @classmethod
    @abstractmethod
    def load_from_path(cls, path: Path, *args: Any) -> Self: ...
```

This ensures all data types can be:

- **Persisted** to disk between pipeline steps
- **Loaded** automatically by the next step
- **Validated** for type correctness

### Supported Base Data Types

Wurzel provides two concrete implementations of the `DataModel` interface:

#### PydanticModel

For structured objects; inherits JSON save/load from the base. Custom override only if you need different behavior:

```python
import json
from pathlib import Path

from wurzel.datacontract import PydanticModel


class DocumentMetadata(PydanticModel):
    title: str
    author: str
    created_date: str
    tags: list[str] = []

    @classmethod
    def save_to_path(
        cls, path: Path, obj: "DocumentMetadata | list[DocumentMetadata]"
    ) -> Path:
        path = path.with_suffix(".json")
        single = [obj] if isinstance(obj, cls) else obj
        path.write_text(json.dumps([m.model_dump() for m in single], indent=2))
        return path

    @classmethod
    def load_from_path(
        cls, path: Path, model_type: type["DocumentMetadata"]
    ) -> "DocumentMetadata":
        data = json.loads(path.read_text())
        if isinstance(data, list):
            data = data[0]
        return cls(**data)
```

**Features**:

- **Serialization**: JSON format (`.json` files)
- **Use cases**: Individual documents, metadata, configuration objects
- **Validation**: Automatic Pydantic validation

#### DataFrame (Pandera)

For bulk data, use Pandera schema models like `EmbeddingResult`:

```python
import pandas as pd

from wurzel.steps.data import EmbeddingResult

df = pd.DataFrame(
    {
        "text": ["doc1"],
        "url": ["file:///doc1.md"],
        "vector": [[0.1, 0.2]],
        "keywords": [""],
        "embedding_input_text": ["doc1"],
        "metadata": [{}],
    }
)
typed_df = EmbeddingResult(df)
```

**Features**:

- **Serialization**: Parquet format (`.parquet` files)
- **Use cases**: Large datasets, tabular data, bulk processing
- **Performance**: Optimized for high-volume data operations

## Built-in Data Contracts

### MarkdownDataContract

Primary contract for document pipelines. Fields: **md**, **url**, **keywords**, **metadata**.

```python
from wurzel.datacontract import MarkdownDataContract

doc = MarkdownDataContract(
    md="# My Document\n\nThis is the content.",
    url="document.md",
    keywords="documentation, markdown",
    metadata={"author": "John Doe", "created": "2024-01-01", "tags": ["markdown"]},
)
_ = doc.md
_ = doc.url
_ = doc.metadata
```

**Fields**:

- `md`: The actual markdown text
- `url`: Source identifier (file path, URL, etc.)
- `keywords`: Optional keywords
- `metadata`: Flexible dictionary for additional information

**Usage**: Document ingestion, text processing, content management

### EmbeddingResult

DataFrame schema for embedding output (one row per chunk). Columns: **text**, **url**, **vector**, **keywords**, **embedding_input_text**, **metadata**.

```python
import pandas as pd

from wurzel.steps.data import EmbeddingResult

row = {
    "text": "Original text content",
    "url": "source_document.md",
    "vector": [0.1, 0.2, 0.3],
    "keywords": "",
    "embedding_input_text": "Original text content",
    "metadata": {"processed_at": "2024-01-01T10:00:00Z"},
}
df = pd.DataFrame([row])
embedding_df = EmbeddingResult(df)
```

**Fields** (per row):

- `text`: Text that was embedded
- `url`: Source of the content
- `vector`: Vector representation
- `keywords`, `embedding_input_text`, `metadata`: Optional

**Usage**: Vector databases, similarity search, ML pipelines

## Creating Custom Data Contracts

### Simple Custom Contract

Subclass `PydanticModel`, add fields and validators:

```python
from datetime import datetime
from typing import Optional

from pydantic import field_validator

from wurzel.core import NoSettings, TypedStep
from wurzel.datacontract import PydanticModel


class ProductDataContract(PydanticModel):
    product_id: str
    name: str
    price: float
    description: Optional[str] = None
    category: str = "general"
    in_stock: bool = True
    tags: list[str] = []
    attributes: dict[str, str] = {}
    created_at: datetime = datetime.now()

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Price must be positive")
        return v

    @field_validator("product_id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        if not v.startswith("PROD_"):
            raise ValueError("Product ID must start with PROD_")
        return v


class ProductProcessingStep(
    TypedStep[NoSettings, list[ProductDataContract], list[ProductDataContract]]
):
    def run(self, inpt: list[ProductDataContract]) -> list[ProductDataContract]:
        processed = []
        for product in inpt:
            if product.price > 100:
                product.tags.append("premium")
            processed.append(product)
        return processed
```

### Complex Hierarchical Contract

Nested Pydantic models and enums:

```python
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import field_validator

from wurzel.datacontract import PydanticModel


class DocumentType(str, Enum):
    ARTICLE = "article"
    MANUAL = "manual"
    FAQ = "faq"
    TUTORIAL = "tutorial"


class AuthorInfo(PydanticModel):
    name: str
    email: str
    organization: Optional[str] = None


class DocumentSection(PydanticModel):
    title: str
    content: str
    level: int = 1
    subsections: list["DocumentSection"] = []


class RichDocumentContract(PydanticModel):
    title: str
    document_type: DocumentType
    language: str = "en"
    sections: list[DocumentSection]
    author: AuthorInfo
    created_at: datetime
    updated_at: Optional[datetime] = None
    word_count: Optional[int] = None
    reading_time_minutes: Optional[float] = None

    @field_validator("sections")
    @classmethod
    def validate_sections(cls, v: list[DocumentSection]) -> list[DocumentSection]:
        if not v:
            raise ValueError("Document must have at least one section")
        return v
```

### DataFrame-based Contracts

Use Pandera schema types in step signatures:

```python
from pandera.typing import DataFrame

from wurzel.core import NoSettings, TypedStep
from wurzel.steps.data import EmbeddingResult


class EmbeddingPassthroughStep(
    TypedStep[NoSettings, DataFrame[EmbeddingResult], DataFrame[EmbeddingResult]]
):
    def run(self, inpt: DataFrame[EmbeddingResult]) -> DataFrame[EmbeddingResult]:
        return inpt
```

## Data Contract Best Practices

### Design Guidelines

1. **Keep contracts focused** — one clear data structure per contract
2. **Use descriptive names** and **sensible defaults** for optional fields
3. **Add validation** with Pydantic validators and `Field(..., description=...)`

```python
import re
from datetime import datetime
from typing import Optional

from pydantic import Field, field_validator

from wurzel.datacontract import PydanticModel


class WellDesignedContract(PydanticModel):
    document_id: str = Field(..., description="Unique document identifier")
    content: str = Field(..., description="Processed document content")
    language: str = Field("en", description="Document language code")
    processing_version: str = Field("1.0", description="Processing pipeline version")
    quality_score: float = Field(0.0, ge=0.0, le=1.0, description="Quality score (0-1)")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence (0-1)")
    created_at: datetime = Field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, v: str) -> str:
        if not re.match(r"^DOC_\d{8}_\d{6}$", v):
            raise ValueError("Document ID must match format: DOC_YYYYMMDD_HHMMSS")
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

Support multiple contract versions with a migration function and a step that accepts both:

```python
from typing import Union

from wurzel.core import NoSettings, TypedStep
from wurzel.datacontract import PydanticModel


class AuthorInfo(PydanticModel):
    name: str
    email: str = ""
    organization: str | None = None


class DocumentContractV1(PydanticModel):
    title: str
    content: str
    author: str


class DocumentContractV2(PydanticModel):
    title: str
    content: str
    author: AuthorInfo
    version: int = 2


def migrate_document_v1_to_v2(old_doc: DocumentContractV1) -> DocumentContractV2:
    return DocumentContractV2(
        title=old_doc.title,
        content=old_doc.content,
        author=AuthorInfo(
            name=old_doc.author, email="unknown@example.com", organization=None
        ),
    )


class VersionAwareStep(
    TypedStep[
        NoSettings, Union[DocumentContractV1, DocumentContractV2], DocumentContractV2
    ]
):
    def run(
        self, inpt: Union[DocumentContractV1, DocumentContractV2]
    ) -> DocumentContractV2:
        if isinstance(inpt, DocumentContractV1):
            return migrate_document_v1_to_v2(inpt)
        return inpt
```

## Testing Data Contracts

### Unit Testing Contracts

```python
import pytest

from wurzel.datacontract import MarkdownDataContract


def test_markdown_contract_creation():
    doc = MarkdownDataContract(
        md="# Hello",
        url="doc.md",
        keywords="test",
        metadata={"key": "value"},
    )
    assert doc.md == "# Hello"
    assert doc.url == "doc.md"
    assert doc.metadata == {"key": "value"}


def test_markdown_contract_validation():
    with pytest.raises(Exception):
        MarkdownDataContract(md=123, url="u", keywords="k")  # type: ignore[arg-type]
```

### Integration Testing with Steps

```python
from wurzel.core import NoSettings, TypedStep
from wurzel.datacontract import PydanticModel


class ProductDataContract(PydanticModel):
    product_id: str
    name: str
    price: float
    tags: list[str] = []


class ProductProcessingStep(
    TypedStep[NoSettings, list[ProductDataContract], list[ProductDataContract]]
):
    def run(self, inpt: list[ProductDataContract]) -> list[ProductDataContract]:
        out = []
        for p in inpt:
            if p.price > 100:
                p.tags.append("premium")
            out.append(p)
        return out


def test_step_with_custom_contract():
    products = [
        ProductDataContract(product_id="PROD_001", name="Cheap Item", price=5.99),
        ProductDataContract(product_id="PROD_002", name="Expensive Item", price=150.00),
    ]
    step = ProductProcessingStep()
    result = step.run(products)
    assert len(result) == 2
    assert "premium" not in result[0].tags
    assert "premium" in result[1].tags
```

## Next Steps

- **[Create Custom Steps](creating-steps.md)** - Build steps that use your custom contracts
- **[Explore Backend Integration](../backends/index.md)** - Deploy pipelines with custom contracts
- **[Review Examples](https://github.com/telekom/wurzel/tree/main/examples)** - See real-world contract implementations

## Additional Resources

- **[Pydantic Documentation](https://docs.pydantic.dev/)** - Learn more about Pydantic features
- **[Pandas Documentation](https://pandas.pydata.org/docs/)** - DataFrame operations and optimization
- **[API Documentation](https://deepwiki.com/telekom/wurzel/)** - Complete data contract API reference
