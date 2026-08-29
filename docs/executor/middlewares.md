# Step Executor Middlewares

Middlewares wrap step execution to add cross-cutting concerns (metrics, logging,
tracing) without modifying step logic. They follow the Chain of Responsibility
pattern and execute in the configured order around the core executor.

## Enabling middlewares

You can enable middlewares in two ways:

from wurzel.step_executor import BaseStepExecutor

# Option 1: Via constructor
with BaseStepExecutor(middlewares=['prometheus']) as exc:
    exc(MyStep, set(inputs), output)

# Option 2: Via environment variable
# export MIDDLEWARES=prometheus
with BaseStepExecutor() as exc:
    exc(MyStep, set(inputs), output)
```

## Using Middlewares

### Via Constructor

```python
from wurzel.step_executor import BaseStepExecutor

# Single middleware
with BaseStepExecutor(middlewares=['prometheus']) as exc:
    exc(MyStep, set(inputs), output)

# Multiple middlewares (executed in order)
with BaseStepExecutor(middlewares=['prometheus', 'custom']) as exc:
    exc(MyStep, set(inputs), output)
```

### Via Environment Variable

```bash
# Enable single middleware
export MIDDLEWARES=prometheus
python -m wurzel run MyStep

# Enable multiple middlewares (comma-separated)
export MIDDLEWARES=prometheus,otel,custom
python -m wurzel run MyStep
```

### Via CLI

```bash
# New --middlewares flag
wurzel run MyStep --middlewares prometheus

# Multiple middlewares
wurzel run MyStep --middlewares prometheus,custom
```

## Built-in Middlewares

### Discovering Available Middlewares

To see all available middlewares in your installation:

```bash
wurzel list-middlewares
```

This will output something like:

```text
Available middlewares:
  - prometheus
```

### Prometheus Middleware

Collects metrics about step execution:
- Steps started/failed counters
- Input/output counts
- Load/execute/save time histograms

**Configuration (via environment variables):**
```bash
export PROMETHEUS_GATEWAY=localhost:9091
export PROMETHEUS_JOB=my-job-name
export PROMETHEUS_DISABLE_CREATED_METRIC=True
```

**Usage:**
```python
with BaseStepExecutor(middlewares=['prometheus']) as exc:
    exc(MyStep, set(inputs), output)
```

## Creating Custom Middlewares

### 1. Create Middleware Class

```python
from wurzel.step_executor.middlewares import BaseMiddleware

class MyCustomMiddleware(BaseMiddleware):
    """Custom middleware example."""

    def __init__(self, my_setting: str = "default"):
        super().__init__()
        self.my_setting = my_setting

    def execute(self, next_call, step_cls, inputs, output_dir):
        """Execute with custom logic."""
        # Pre-processing
        print(f"Starting {step_cls.__name__}")

        try:
            # Call next middleware or executor
            result = next_call(step_cls, inputs, output_dir)

            # Post-processing
            print(f"Completed {step_cls.__name__}")
            return result
        except Exception as e:
            # Error handling
            print(f"Failed {step_cls.__name__}: {e}")
            raise

    def __enter__(self):
        """Setup resources."""
        print("Middleware initialized")
        return self

    def __exit__(self, *exc_details):
        """Cleanup resources."""
        print("Middleware cleanup")
```

### 2. Register Middleware

```python
from wurzel.step_executor.middlewares import get_registry

# Register your middleware
registry = get_registry()
registry.register("custom", MyCustomMiddleware)
```

### 3. Use Middleware

```python
# Now you can use it like built-in middlewares
with BaseStepExecutor(middlewares=['custom']) as exc:
    exc(MyStep, set(inputs), output)
```

## Middleware Configuration

### Per-Middleware Settings

Each middleware can have its own settings class:

```python
from wurzel.step.settings import Settings
from pydantic import Field

class MyMiddlewareSettings(Settings):
    """Settings for my middleware."""

    MY_SETTING: str = Field("default", description="My setting")
    MY_NUMBER: int = Field(42, description="A number")

class MyMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self.settings = MyMiddlewareSettings()
```

Settings are loaded from environment variables:
```bash
export MY_SETTING=custom_value
export MY_NUMBER=100
```

## Advanced Usage

### Programmatic Middleware Chain

```python
from wurzel.step_executor.middlewares import MiddlewareChain, PrometheusMiddleware

# Build custom chain
chain = MiddlewareChain()
chain.add(PrometheusMiddleware())
chain.add(MyCustomMiddleware())

# Use with executor
executor = BaseStepExecutor(middlewares=[])  # Empty, we'll set manually
executor._BaseStepExecutor__middleware_chain = chain

with executor as exc:
    exc(MyStep, set(inputs), output)
```

### Conditional Middleware Loading

```python
import os

middlewares = []
if os.environ.get("ENABLE_METRICS") == "true":
    middlewares.append("prometheus")
if os.environ.get("ENABLE_TRACING") == "true":
    middlewares.append("otel")

with BaseStepExecutor(middlewares=middlewares) as exc:
    exc(MyStep, set(inputs), output)
```

## Testing Middlewares

```python
import pytest
from wurzel.step_executor import BaseStepExecutor
from wurzel.step_executor.middlewares import get_registry

def test_custom_middleware():
    """Test custom middleware."""
    # Register middleware
    registry = get_registry()
    registry.register("test", MyCustomMiddleware)

    # Use middleware
    with BaseStepExecutor(middlewares=['test']) as exc:
        result = exc(MyStep, set(), output_path)
        assert result
```

## Backward Compatibility

The old `PrometheusStepExecutor` is still available but deprecated. It will be removed in a future version. Please migrate to the new middleware pattern.

```python
# This still works but shows a deprecation warning
from wurzel.step_executor import PrometheusStepExecutor

with PrometheusStepExecutor() as exc:  # DeprecationWarning
    exc(MyStep, set(inputs), output)
```
