---
trigger: always_on
---

# Wurzel Project Rules & Context

## Core Architecture

### TypedStep System (`wurzel/step/`)
- **TypedStep[SETTINGS, INCONTRACT, OUTCONTRACT]**: Base class for all steps
- Chain with `>>` operator (type-safe): `source >> splitter >> embedder`
- Input can be `None` for leaf steps, output always required

### Data Contracts (`wurzel/datacontract/`)
- **PydanticModel**: Structured objects (JSON), **PanderaDataFrameModel**: Tabular data (CSV)
- Both implement `save_to_path()` and `load_from_path()`

### Executors (`wurzel/step_executor/`)
- **BaseStepExecutor**: Core engine with env encapsulation
- **PrometheusStepExecutor**: Adds metrics
- Middleware support via `MiddlewareRegistry`

### Backends (`wurzel/backend/`)
- **DvcBackend**: Generates `dvc.yaml`, **ArgoBackend**: Argo Workflows YAML

### CLI (`wurzel/cli/`)
- `wurzel run/inspect/generate/middlewares`

### Built-in Steps (`wurzel/steps/`)
- ManualMarkdown, SimpleSplitter, Embedding, Qdrant/Milvus connectors, Docling, ScraperAPI

## Development Workflow (CRITICAL - Always Follow)

### After ANY Code Change:
0. **Check and update documentation** (`docs/` - mkdocs format)
1. **Lint**: `make lint` (runs pre-commit: ruff, pylint, reuse)
2. **Test**: `make test` (pytest with 90% coverage requirement)

### Before Committing:
- Ensure all tests pass
- Verify linting passes
- Update relevant documentation in `docs/`
- Follow conventional commit format (feat/fix/docs/refactor/test/chore)
## Tech Stack & Standards

### Core Technologies
- **Pydantic v2**: For data validation and settings
  - Use `pydantic.BaseModel` for data models
  - Use `wurzel.step.Settings` for step settings (NOT `pydantic_settings.BaseSettings`)
  - Custom implementations in `wurzel.datacontract` and `wurzel.step.settings`
- **Pandera**: For DataFrame validation
- **uv**: Package manager (NOT pip directly)
- **mkdocs**: Documentation (with material theme, mermaid, typer integration)
- **DVC**: Pipeline versioning and execution
- **typer**: CLI framework



### Testing
- **Coverage**: Minimum 90% (enforced in Makefile)
- **Location**: `tests/` mirrors `wurzel/` structure
- **Run**: `make test` or `uv run pytest`

### Linting Tools
- **ruff**: Primary linter and formatter (replaces black, isort, flake8)
- **pylint**: Additional checks (max-line-length: 140)
- **pre-commit**: Automated checks on commit
- **reuse**: License compliance (SPDX headers required)

## Environment Variables

```bash
# Step settings: <STEP_NAME_UPPERCASE>__<SETTING_NAME>
export MANUALMARKDOWNSTEP__FOLDER_PATH=/path/to/docs
export ALLOW_EXTRA_SETTINGS=True
export MIDDLEWARES=prometheus
export DVCBACKEND__DATA_DIR=./data
```

## Implementation Patterns

### Step
```python
from wurzel.step import TypedStep, Settings
from wurzel.datacontract import MarkdownDataContract

class MyStepSettings(Settings):
    my_param: str

class MyStep(TypedStep[MyStepSettings, InputType, OutputType]):
    def run(self, inpt: InputType) -> OutputType:
        return result
```

### Pipeline
```python
from wurzel.utils import WZ
source = WZ(SourceStep)
processor = WZ(ProcessStep)
source >> processor
pipeline = processor
```

### Execution
```python
with BaseStepExecutor(middlewares=["prometheus"]) as ex:
    ex(MyStep, {Path("./input")}, Path("./output"))
```

## Documentation Updates
- New step → `docs/developer-guide/creating-steps.md`
- New backend → `docs/backends/index.md`
- New middleware → `docs/executor/middlewares.md`

## Key Notes
- TypedStep enforces type compatibility at definition time
- Steps run in isolated env (settings from env vars with `STEPNAME__` prefix)
- **Settings**: Use `wurzel.step.Settings` (custom wrapper around pydantic_settings)
  - Supports nested settings with `__` delimiter
  - Auto-loads from env vars with step name prefix
  - Use `NoSettings` type alias for steps without settings
- History tracking: `[source].[step1].[step2]...`
- Optional deps: `wurzel[qdrant,milvus,argo]`, check `wurzel.utils.HAS_*`

## Troubleshooting
- Import errors: Use full module path
- Type errors: Check INCONTRACT/OUTCONTRACT compatibility
- Settings errors: Verify `STEPNAME__SETTING` format
- `wurzel inspect module.path.StepName` for details
