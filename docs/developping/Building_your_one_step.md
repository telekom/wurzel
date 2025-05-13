# 📚 How to Build Your Own Step

Wurzel provides a modular pipeline system where each unit of processing is encapsulated in a Step. There are two main types of steps:

- Datasource Steps (WurzelTips): These are entry points to your pipeline, ingesting data from external sources.
- Processing Steps (WurzelSteps): These consume and transform data from earlier steps.

## ⚙️ Initialization Logic

The run method of each step may be executed multiple times—once per upstream dependency. If your step needs to perform setup actions (e.g., creating database tables or opening persistent connections), implement that logic in the constructor (__init__) instead of run.

### 🗃️ Example: Step with Initialization

```python
class MyDatabaseStep(TypedStep[DatabaseSettings, DataFrame[EmbeddingResult], DataFrame[EmbeddingResult]]):

    def __init__(self):
        # Initialize database connections, create tables, etc.
        self.connection = establish_connection()
        self.ensure_tables()

    def run(self, inpt: DataFrame[EmbeddingResult]) -> DataFrame[EmbeddingResult]:
        # Insert data into database or perform other processing
        return inpt
```

## 🛠️ Finalization Logic

Each step also provides a `finalize` method, which is called after the execution in the Executor has finished. This method can be used for cleanup or other post-processing tasks.

### 🗃️ Example: Step with Finalization

```python
class MyDatabaseStep(TypedStep[DatabaseSettings, DataFrame[EmbeddingResult], DataFrame[EmbeddingResult]]):

    def __init__(self):
        # Initialize database connections, create tables, etc.
        self.connection = establish_connection()
        self.ensure_tables()

    def run(self, inpt: DataFrame[EmbeddingResult]) -> DataFrame[EmbeddingResult]:
        # Insert data into database or perform other processing
        return inpt

    def finalize(self) -> None:
        # Cleanup logic, such as retiring collections or closing connections
        self.connection.close()
```

## 🧱 Creating a New WurzelTip (Datasource Step)

A WurzelTip is a step that introduces data into the pipeline. Since it does not rely on any prior step, its InputDataContract is always None.

By convention, we use MarkdownDataContract as the initial data format for document retrieval pipelines, but you are free to define and use your own custom contracts.

### ✅ Requirements

- Settings: Optional configuration schema using Pydantic's BaseModel (via Settings).

- InputDataContract: Always None for data sources.

- OutputDataContract: Required. Typically list[MarkdownDataContract].

### 📦 Example

```python
class MySettings(Settings):
    """Configuration for MyDatasourceStep"""
    YOUR_REQUIRED_ENVIRONMENT: Any


class MyDatasourceStep(TypedStep[MySettings, None, list[MarkdownDataContract]]):
    """Data source step for loading Markdown files from a configurable path."""

    def run(self, inpt: None) -> list[MarkdownDataContract]:
        # Your custom data ingestion logic here
        return result
```

## 🔁 Creating a New WurzelStep (Processing Step)

A WurzelStep consumes the output of a previous step, performs a transformation, and passes its output to the next step in the pipeline. These can include:

- Filters: Narrow down data based on a condition.
- Validators: Check for schema or content correctness.
- Transformers: Change the data structure, such as converting from a list of documents to a DataFrame of embeddings.

### 🧹 Example: Filter Step

```python
class MyFilterStep(TypedStep[MySettings, list[MarkdownDataContract], list[MarkdownDataContract]]):
    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        # Your filtering logic here
        return result
```

## 🔄 Example: Transformation Step

Sometimes a step will change the shape or structure of the data entirely, for example transforming a list of documents into a pandas.DataFrame. This is common in steps that perform embedding or analytics.

```python
class MyEmbeddingStep(TypedStep[EmbeddingSettings, list[MarkdownDataContract], DataFrame[EmbeddingResult]]):
    def run(self, inpt: list[MarkdownDataContract]) -> DataFrame[EmbeddingResult]:
        """Transforms input markdown files into embeddings stored in a DataFrame."""
        # Your embedding logic here
        return df
```
