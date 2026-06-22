# Wurzel

Wurzel is an open-source Python ETL framework for Retrieval-Augmented Generation (RAG) pipelines. It provides typed, validated step graphs with multi-tenancy, cloud-native deployment, and scheduling support. See [README.md](README.md) and [docs/](docs/) for full documentation.

## Environment Setup

```bash
make install   # uv sync --all-extras + pre-commit install
```

Every `make` command runs `make install` automatically.

## Key Commands

| Command | Purpose |
|---|---|
| `make test` | Run pytest with coverage (90% threshold) |
| `make lint` | Run all pre-commit hooks |
| `make build` | Build distribution |
| `make api` | Start FastAPI dev server on 127.0.0.1:8000 |
| `make documentation` | Serve MkDocs locally |

**You are only done when `make lint` and `make test` both pass.**

---

## Architecture

```
Manifest (YAML)
    ↓ ManifestBuilder
Step Graph (dict[name → WZ(TypedStep)])
    ↓ BaseExecutor + Middlewares
Execution (validate contracts → run → save outputs)
```

Key modules under `wurzel/`:
- **`core/`** — `TypedStep`, `Settings`, base abstractions
- **`datacontract/`** — `PydanticModel`, `PanderaDataFrameModel`, `MarkdownDataContract`
- **`steps/`** — Built-in step implementations (source of truth for patterns)
- **`executors/`** — `BaseExecutor` runs step graphs, validates contracts
- **`manifest/`** — YAML pipeline declaration and `ManifestBuilder`
- **`storage/`** — `FileStorage` (local) / `FileStorageS3` (cloud)
- **`api/`** — FastAPI app; routes for pipelines, files, search, auth
- **`cli/`** — CLI commands: validate manifest, inspect step, generate step

---

## Creating a Step

Steps use `TypedStep[SETTINGS, INPUT, OUTPUT]` — all three type arguments are **mandatory**.

```python
# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.core import TypedStep
from wurzel.core.settings import Settings
from wurzel.datacontract import MarkdownDataContract
from pydantic import Field

class MyStepSettings(Settings):
    BATCH_SIZE: int = Field(100, gt=0)          # env: MY_STEP_BATCH_SIZE

class MyStep(TypedStep[MyStepSettings, list[MarkdownDataContract], list[MarkdownDataContract]]):
    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        return [process(item, self.settings.BATCH_SIZE) for item in inpt]
```

- `INPUT = None` → leaf/source step (no upstream dependency)
- `SETTINGS = None` → use `NoSettings` alias; step has no configuration
- Valid I/O types: `PydanticModel`, `PanderaDataFrameModel`, `list[...]` of those, `pandera.typing.DataFrame`
- Missing or wrong type args raise `StaticTypeError` **at class definition time**

See [wurzel/steps/](wurzel/steps/) for real examples.

---

## Settings Pattern

Settings are auto-prefixed by the step class name in SCREAMING_SNAKE_CASE.

| Step class | Env var prefix |
|---|---|
| `SimpleSplitterStep` | `SIMPLE_SPLITTER_STEP_` |
| `MyStep` | `MY_STEP_` |

Rules:
- Always use Pydantic `Settings` — **never** `os.environ.get()` for app config
- Field names must be **UPPERCASE** and match the env var name exactly (case-sensitive)
- Nested settings: subclass `SettingsLeaf`; use `__` as delimiter (`PARENT__CHILD=value`)
- `model_config = SettingsConfigDict(extra="forbid", case_sensitive=True)` is the default

---

## Data Contracts

| Class | Format | Use for |
|---|---|---|
| `PydanticModel` | `.json` | Structured objects |
| `PanderaDataFrameModel` | `.csv` | Tabular/DataFrame data |
| `MarkdownDataContract` | `.md` + YAML frontmatter | Text chunks with metadata |

Contract validation runs inside `BaseExecutor`. Direct `step.run(data)` **skips** validation (useful in tests).

---

## Testing Standards

- **Framework**: pytest only — never `unittest.TestCase`
- **Parametrize**: use `@pytest.mark.parametrize` for multiple similar inputs
- **Fixtures** (from [tests/conftest.py](tests/conftest.py)):
  - `env` — set/clear env vars safely per test
  - `input_output_folder` — `tmp_path` with `input/` + `output/` subdirs
- **Direct step testing**: instantiate the step and call `.run(data)` directly; no executor needed
- Add tests covering success, failure, and edge cases for all new behavior

---

## SPDX License Headers

**Every new `.py` file** must begin with:

```python
# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
```

`make lint` will fail without this header (enforced by `reuse` pre-commit hook).

---

## Optional Dependencies

Many integrations (Qdrant, Milvus, Docling, OpenAI, etc.) are optional extras. Guard imports with the availability flags in `wurzel/utils/__init__.py`:

```python
from wurzel.utils import HAS_QDRANT
if HAS_QDRANT:
    from qdrant_client import QdrantClient
```

Install extras with `uv sync --extra qdrant` (or `--all-extras` for everything).
