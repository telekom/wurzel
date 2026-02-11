# Creating Custom Steps

Learn how to build your own data processing steps in Wurzel, from simple data sources to complex transformation components.

## Step Types Overview

Wurzel provides two main types of steps:

- **Data Source Steps (WurzelTips)**: Entry points that ingest data from external sources
- **Processing Steps (WurzelSteps)**: Transform data from upstream steps

Both types follow the same `TypedStep` interface but serve different roles in your pipeline.

## Step Architecture

### The TypedStep Interface

All steps inherit from `TypedStep` with three type parameters: **TSettings**, **TInput**, **TOutput**. You implement:

- **`__init__`** — setup (connections, resources)
- **`run(inpt)`** — process input and return output
- **`finalize`** — optional cleanup

```python
from typing import Generic, TypeVar

TSettings = TypeVar("TSettings")
TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class TypedStep(Generic[TSettings, TInput, TOutput]):
    def __init__(self) -> None:
        pass

    def run(self, inpt: TInput) -> TOutput:
        raise NotImplementedError

    def finalize(self) -> None:
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
from pathlib import Path

from wurzel.datacontract import MarkdownDataContract
from wurzel.step import Settings, TypedStep


class MySettings(Settings):
    DATA_PATH: Path = Path("./data")
    FILE_PATTERN: str = "*.md"


class MyDatasourceStep(TypedStep[MySettings, None, list[MarkdownDataContract]]):
    def __init__(self):
        super().__init__()
        self.settings = MySettings()

    def run(self, inpt: None) -> list[MarkdownDataContract]:
        documents = []
        for file_path in self.settings.DATA_PATH.glob(self.settings.FILE_PATTERN):
            content = file_path.read_text(encoding="utf-8")
            doc = MarkdownDataContract(
                md=content,
                url=str(file_path),
                keywords=file_path.stem,
                metadata={"file_path": str(file_path)},
            )
            documents.append(doc)
        return documents
```

### Memory-Efficient Data Source (Generator)

When a data source loads many items (large file sets, API responses, database cursors), building the full list in memory can be expensive. You can make `run()` a **generator** that yields batches instead. The executor detects this automatically — no flag or configuration needed.

Each `yield` should produce a **list** (a batch). The executor accumulates items in memory and flushes them to numbered batch files on disk once a threshold is reached (default: 500 items), keeping memory usage bounded.

```python
from pathlib import Path

from wurzel.datacontract import MarkdownDataContract
from wurzel.step import Settings, TypedStep


class MySettings(Settings):
    DATA_PATH: Path = Path("./data")


class MyStreamingSourceStep(TypedStep[MySettings, None, list[MarkdownDataContract]]):
    """Yields one document at a time — memory usage stays constant."""

    def run(self, inpt: None) -> list[MarkdownDataContract]:
        for file_path in self.settings.DATA_PATH.rglob("*.md"):
            content = file_path.read_text(encoding="utf-8")
            yield [
                MarkdownDataContract(
                    md=content,
                    url=str(file_path),
                    keywords=file_path.stem,
                )
            ]
```

!!! tip "How it works"
    The executor uses `inspect.isgeneratorfunction()` to detect generators at
    runtime. When detected, each yielded batch is fed to a
    [`BatchWriter`](data-contracts.md#batchwriter) which buffers items and
    flushes them to numbered JSON files (`<StepName>_batch0000.json`,
    `_batch0001.json`, …). The return type annotation stays `list[...]` for
    static type-checking compatibility.

!!! note "Yielding batches vs. single items"
    Each `yield` must produce a **list**, even if it contains only one item
    (`yield [item]`). You can also yield larger batches when it is natural
    to do so — for example, yielding a page of API results at a time.

### Advanced Data Source with Database

Shows a source step with **resource cleanup** in `finalize`:

```python
import sqlite3

from wurzel.datacontract import MarkdownDataContract
from wurzel.step import Settings, TypedStep


class DatabaseSettings(Settings):
    DB_PATH: str = "data.db"
    TABLE_NAME: str = "documents"
    QUERY: str = "SELECT content, source, metadata FROM documents"


class DatabaseSourceStep(TypedStep[DatabaseSettings, None, list[MarkdownDataContract]]):
    def __init__(self):
        super().__init__()
        self.settings = DatabaseSettings()
        self.connection = sqlite3.connect(self.settings.DB_PATH)
        self.connection.row_factory = sqlite3.Row

    def run(self, inpt: None) -> list[MarkdownDataContract]:
        cursor = self.connection.cursor()
        cursor.execute(self.settings.QUERY)
        documents = []
        for row in cursor.fetchall():
            meta = eval(row["metadata"]) if row["metadata"] else {}
            doc = MarkdownDataContract(
                md=row["content"],
                url=row["source"],
                keywords="",
                metadata=meta,
            )
            documents.append(doc)
        return documents

    def finalize(self) -> None:
        if self.connection:
            self.connection.close()
```

## Creating Processing Steps

Processing steps transform data from upstream steps. They can filter, validate, transform, or enrich data.

### Filter Step

```python
from wurzel.datacontract import MarkdownDataContract
from wurzel.step import Settings, TypedStep


class FilterSettings(Settings):
    MIN_LENGTH: int = 100
    MAX_LENGTH: int = 10000
    REQUIRED_KEYWORDS: list[str] = []


class DocumentFilterStep(
    TypedStep[FilterSettings, list[MarkdownDataContract], list[MarkdownDataContract]]
):
    def __init__(self):
        super().__init__()
        self.settings = FilterSettings()

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        filtered_docs = []
        for doc in inpt:
            if (
                len(doc.md) < self.settings.MIN_LENGTH
                or len(doc.md) > self.settings.MAX_LENGTH
            ):
                continue
            if self.settings.REQUIRED_KEYWORDS and not all(
                kw.lower() in doc.md.lower() for kw in self.settings.REQUIRED_KEYWORDS
            ):
                continue
            filtered_docs.append(doc)
        return filtered_docs
```

### Transformation Step

```python
from wurzel.datacontract import MarkdownDataContract
from wurzel.step import Settings, TypedStep


class TransformSettings(Settings):
    PREFIX: str = "[processed] "


class DocumentTransformStep(
    TypedStep[TransformSettings, list[MarkdownDataContract], list[MarkdownDataContract]]
):
    def __init__(self):
        super().__init__()
        self.settings = TransformSettings()

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        return [
            MarkdownDataContract(
                md=self.settings.PREFIX + doc.md,
                url=doc.url,
                keywords=doc.keywords,
                metadata=doc.metadata,
            )
            for doc in inpt
        ]
```

### Validation Step

Uses a helper and raises after too many errors:

```python
from wurzel.datacontract import MarkdownDataContract
from wurzel.step import Settings, TypedStep


class ValidationSettings(Settings):
    CHECK_ENCODING: bool = True
    CHECK_STRUCTURE: bool = True
    MAX_ERRORS: int = 5


class DocumentValidationStep(
    TypedStep[
        ValidationSettings, list[MarkdownDataContract], list[MarkdownDataContract]
    ]
):
    def __init__(self):
        super().__init__()
        self.settings = ValidationSettings()
        self.error_count = 0

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        valid_docs = []
        for doc in inpt:
            if self._validate_document(doc):
                valid_docs.append(doc)
            else:
                self.error_count += 1
                if self.error_count >= self.settings.MAX_ERRORS:
                    raise RuntimeError(
                        f"Too many validation errors: {self.error_count}"
                    )
        return valid_docs

    def _validate_document(self, doc: MarkdownDataContract) -> bool:
        if self.settings.CHECK_ENCODING:
            try:
                doc.md.encode("utf-8")
            except UnicodeEncodeError:
                return False
        if self.settings.CHECK_STRUCTURE and (not doc.md.strip() or len(doc.md) < 10):
            return False
        return True
```

## Advanced Patterns

### Multi-Input Steps

Steps can collect data from multiple upstream runs (simplified: single input list here):

```python
from wurzel.datacontract import MarkdownDataContract
from wurzel.step import Settings, TypedStep


class MergerSettings(Settings):
    MERGE_STRATEGY: str = "concatenate"


class DocumentMergerStep(
    TypedStep[MergerSettings, list[MarkdownDataContract], list[MarkdownDataContract]]
):
    def __init__(self):
        super().__init__()
        self.settings = MergerSettings()
        self.collected_inputs: list[list[MarkdownDataContract]] = []

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        self.collected_inputs.append(inpt)
        if self.settings.MERGE_STRATEGY == "concatenate":
            all_docs: list[MarkdownDataContract] = []
            for doc_list in self.collected_inputs:
                all_docs.extend(doc_list)
            return all_docs
        return inpt
```

### Stateful Processing

State in `__init__` and optional cleanup in `finalize`:

```python
import hashlib
from collections import defaultdict

from wurzel.datacontract import MarkdownDataContract
from wurzel.step import Settings, TypedStep


class DeduplicationSettings(Settings):
    HASH_ALGORITHM: str = "md5"


class DeduplicationStep(
    TypedStep[
        DeduplicationSettings, list[MarkdownDataContract], list[MarkdownDataContract]
    ]
):
    def __init__(self):
        super().__init__()
        self.settings = DeduplicationSettings()
        self.seen_hashes: set[str] = set()
        self.document_index: defaultdict[str, list[str]] = defaultdict(list)

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        unique_docs = []
        for doc in inpt:
            raw = doc.md.encode()
            content_hash = (
                hashlib.md5(raw).hexdigest()
                if self.settings.HASH_ALGORITHM == "md5"
                else hashlib.sha256(raw).hexdigest()
            )
            if content_hash not in self.seen_hashes:
                self.seen_hashes.add(content_hash)
                unique_docs.append(doc)
                self.document_index[content_hash].append(doc.url)
        return unique_docs

    def finalize(self) -> None:
        _ = len(self.seen_hashes)
        _ = sum(len(sources) - 1 for sources in self.document_index.values())
```

## Step Settings and Configuration

<a id="step-settings"></a>

### Environment Variable Integration

Settings fields map to env vars (prefix = step name in UPPERCASE, e.g. `MYSTEP__API_KEY`):

```python
from wurzel.step import Settings


class APISettings(Settings):
    API_KEY: str
    BASE_URL: str = "https://api.example.com"
    TIMEOUT: int = 30
    MAX_RETRIES: int = 3
```

### Nested Configuration

Nested settings use `__` in env var names:

```python
from wurzel.step import Settings


class DatabaseConfig(Settings):
    HOST: str = "localhost"
    PORT: int = 5432
    DATABASE: str = "wurzel"
    USERNAME: str = "user"
    PASSWORD: str = "password"


class ProcessingConfig(Settings):
    BATCH_SIZE: int = 100
    PARALLEL_WORKERS: int = 4


class ComplexStepSettings(Settings):
    database: DatabaseConfig = DatabaseConfig()
    processing: ProcessingConfig = ProcessingConfig()
    DEBUG_MODE: bool = False
```

## Testing Custom Steps

### Unit Testing

```python
from pathlib import Path
from unittest.mock import patch

from wurzel.datacontract import MarkdownDataContract
from wurzel.step import TypedStep
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.utils import WZ


def test_markdown_step_returns_list(tmp_path: Path):
    (tmp_path / "doc.md").write_text("# Hello")
    with patch.dict("os.environ", {"MANUALMARKDOWNSTEP__FOLDER_PATH": str(tmp_path)}):
        step = WZ(ManualMarkdownStep)
        # ManualMarkdownStep is a generator — consume all yielded batches.
        result = [item for batch in step.run(None) for item in batch]
    assert len(result) == 1
    assert all(isinstance(d, MarkdownDataContract) for d in result)


def test_filter_step():
    from wurzel.step import Settings

    class FilterSettings(Settings):
        MIN_LENGTH: int = 10

    class SimpleFilterStep(
        TypedStep[
            FilterSettings, list[MarkdownDataContract], list[MarkdownDataContract]
        ]
    ):
        def __init__(self):
            super().__init__()
            self.settings = FilterSettings()

        def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
            return [d for d in inpt if len(d.md) >= self.settings.MIN_LENGTH]

    docs = [
        MarkdownDataContract(md="Hi", url="u1", keywords="k1"),
        MarkdownDataContract(md="Long enough content here", url="u2", keywords="k2"),
    ]
    step = WZ(SimpleFilterStep)
    result = step.run(docs)
    assert len(result) == 1
    assert result[0].md == "Long enough content here"
```

### Testing Generator Steps

Generator steps return a generator object, not a list. Consume all yielded
batches in your test to collect the results:

```python
from unittest.mock import patch

from wurzel.datacontract import MarkdownDataContract
from wurzel.step import Settings, TypedStep


class StreamSettings(Settings):
    DATA_PATH: str = "./data"


class MyStreamingSourceStep(
    TypedStep[StreamSettings, None, list[MarkdownDataContract]]
):
    def run(self, inpt: None) -> list[MarkdownDataContract]:
        from pathlib import Path

        for fp in Path(self.settings.DATA_PATH).rglob("*.md"):
            yield [
                MarkdownDataContract(md=fp.read_text(), url=str(fp), keywords=fp.stem)
            ]


def test_streaming_source(tmp_path):
    (tmp_path / "a.md").write_text("# A")
    (tmp_path / "b.md").write_text("# B")
    env = {"MYSTREAMINGSOURCESTEP__DATA_PATH": str(tmp_path)}
    with patch.dict("os.environ", env):
        step = MyStreamingSourceStep()
        # Flatten yielded batches into a single list.
        results = [item for batch in step.run(None) for item in batch]
    assert len(results) == 2
```

To test that a generator step raises an exception, force evaluation with `list()`:

```python
import pytest

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed
from wurzel.step import NoSettings, TypedStep


class MyFailingStep(TypedStep[NoSettings, None, list[MarkdownDataContract]]):
    def run(self, inpt: None) -> list[MarkdownDataContract]:
        yield [MarkdownDataContract(md="ok", url="", keywords="")]
        raise StepFailed("boom")


def test_generator_raises_on_error():
    step = MyFailingStep()
    with pytest.raises(StepFailed):
        list(step.run(None))  # forces the generator to run
```

### Integration Testing

```python
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.utils import WZ


def test_pipeline_structure():
    source = WZ(ManualMarkdownStep)
    assert source is not None
    assert hasattr(source, "inputs")
```

## Best Practices

### Error Handling

Catch per-item errors and fail if too many:

```python
from wurzel.datacontract import MarkdownDataContract
from wurzel.step import NoSettings, TypedStep


class RobustProcessingStep(
    TypedStep[NoSettings, list[MarkdownDataContract], list[MarkdownDataContract]]
):
    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        processed_docs = []
        errors = []
        for i, doc in enumerate(inpt):
            try:
                processed_docs.append(doc)
            except Exception as e:
                errors.append(f"Failed to process document {i}: {e!s}")
        if errors and len(errors) > len(inpt) * 0.5:
            raise RuntimeError(f"Too many processing errors: {len(errors)}/{len(inpt)}")
        return processed_docs
```

### Resource Management

Use `finalize()` to release connections and temp files:

```python
import os
from typing import Any

from wurzel.datacontract import MarkdownDataContract
from wurzel.step import NoSettings, TypedStep


class ResourceManagedStep(
    TypedStep[NoSettings, list[MarkdownDataContract], list[MarkdownDataContract]]
):
    def __init__(self):
        super().__init__()
        self.connection: Any = None
        self.temp_files: list[str] = []

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        try:
            return inpt
        except Exception:
            self._cleanup_resources()
            raise

    def finalize(self) -> None:
        self._cleanup_resources()

    def _cleanup_resources(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        for temp_file in self.temp_files:
            try:
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
