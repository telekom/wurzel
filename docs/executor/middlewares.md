# Step Executor Middleware System

## Overview

The step executor now supports a **middleware pattern** for adding cross-cutting concerns like metrics, logging, and tracing to step execution. This replaces the old inheritance-based approach (like `PrometheusStepExecutor`) with a more flexible and composable system.

## Key Benefits

1. **Composability**: Multiple middlewares can be combined without inheritance
2. **Flexibility**: Middlewares can be enabled/disabled via configuration
3. **Extensibility**: Easy to create custom middlewares
4. **Cleaner Architecture**: Separation of concerns

Middlewares provide a flexible way to extend and observe the execution of
steps without modifying step logic. They are executed as a chain around the
executor's core behavior and can inspect or modify inputs, outputs, and the
execution flow.

## Concepts

- A middleware implements the `BaseMiddleware` interface and participates in a
  `MiddlewareChain`.
- Middlewares run in the order they are configured; the chain wraps the core
  executor logic so that each middleware gets a chance to run code before and
  after the inner chain.
- Middlewares are useful for cross-cutting concerns such as metrics, timing,
  caching, retries, logging, or tracing.

## Enabling middlewares

You can enable middlewares in two ways:

1. By passing names or instances to `BaseStepExecutor`:

```python
from wurzel.executors.base_executor import BaseStepExecutor

# Using names registered in the middleware registry
with BaseStepExecutor(middlewares=["timing", "custom"]) as exc:
    exc(MyStep, set(), Path("output"))

# Or provide middleware instances directly
from wurzel.executors.middlewares import TimingMiddleware
with BaseStepExecutor(middlewares=[TimingMiddleware()]) as exc:
    exc(MyStep, set(), Path("output"))
```

1. By setting the `MIDDLEWARES` environment variable to a comma-separated
  list of middleware names (the executor will load them from the built-in
  registry):

```bash
export MIDDLEWARES=timing,custom
wurzel run ...
```

Or use the `middlewares` command group in the CLI to list and inspect
available middlewares:

```bash
wurzel middlewares list
wurzel middlewares inspect <name>
```

## Middleware interface

A middleware typically subclasses `BaseMiddleware` and implements a
`__call__()` method. The middleware should accept a `call_next` callable (the inner
chain) and call it to continue execution. It may inspect or modify arguments
and return values.

Minimal example:

```python
from wurzel.executors.middlewares.base import BaseMiddleware

class LoggingMiddleware(BaseMiddleware):
    def __call__(self, call_next, step_cls, inputs, output_path):
        print(f"Starting {step_cls.__name__}")
        result = call_next(step_cls, inputs, output_path)
        print(f"Finished {step_cls.__name__}")
        return result
```

## Writing robust middlewares

- Always call the inner `call_next` to ensure the chain continues unless you
  intentionally short-circuit execution.
- Preserve and return the inner chain's return value unless a middleware
  transforms it intentionally.
- Keep middleware logic focused and small — combine concerns in different
  middlewares rather than creating large, multipurpose middlewares.

## Testing middlewares

- Use unit tests to verify middleware behavior in isolation by constructing a
  small chain and asserting that the middleware sees the expected inputs/outputs.
- Use integration tests that run `BaseStepExecutor` with the middleware enabled
  to confirm correct runtime behavior.

## Registry and discovery

The project provides a registry of available middlewares that the executor
uses to build the chain when names are provided. To add a middleware to the
registry, follow the project's conventions for step executor extensions.

## Examples

Registering and using a custom middleware:

```python
from wurzel.executors.middlewares import get_registry

registry = get_registry()
registry.register("custom", MyCustomMiddleware)

with BaseStepExecutor(middlewares=["custom"]) as exc:
    exc(MyStep, set(), Path("output"))
```

Conditional loading example:

```python
import os

middlewares = []
if os.environ.get("ENABLE_TIMING") == "true":
    middlewares.append("timing")
if os.environ.get("ENABLE_TRACING") == "true":
    middlewares.append("otel")

with BaseStepExecutor(middlewares=middlewares) as exc:
    exc(MyStep, set(), Path("output"))
```

## Using Middlewares with Backends

### DVC Backend

For DVC pipelines, set middleware environment variables before running:

```bash
export MIDDLEWARES=prometheus
export PROMETHEUS__PROMETHEUS_GATEWAY=localhost:9091
dvc repro
```

### Argo Workflows Backend

For Argo Workflows, configure middlewares in your `values.yaml` file under `container.env`:

```yaml
workflows:
  pipelinedemo:
    container:
      env:
        # Enable Prometheus middleware
        MIDDLEWARES: "prometheus"
        PROMETHEUS__PROMETHEUS_GATEWAY: "prometheus-pushgateway.monitoring.svc.cluster.local:9091"
        PROMETHEUS__PROMETHEUS_JOB: "wurzel-pipeline"
```

Then generate the workflow:

```bash
wurzel generate --backend ArgoBackend --values values.yaml examples.pipeline.pipelinedemo:pipeline
```

The middleware configuration will be embedded in the generated CronWorkflow YAML as environment variables.

## Prometheus Middleware

The Prometheus middleware pushes metrics to a Prometheus Pushgateway for monitoring pipeline execution.

!!! note "Environment Variable Prefix"
    The Prometheus middleware uses the `PROMETHEUS__` prefix for all environment variables. This is configured via `model_config = SettingsConfigDict(env_prefix="PROMETHEUS__")` in the settings class. The field names in the settings class are `GATEWAY`, `JOB`, and `DISABLE_CREATED_METRIC` (without the `PROMETHEUS_` prefix), and pydantic-settings automatically adds the prefix when reading from environment variables.

**Configuration:**

```bash
# Required
export MIDDLEWARES=prometheus
export PROMETHEUS__PROMETHEUS_GATEWAY=pushgateway:9091

# Optional
export PROMETHEUS__PROMETHEUS_JOB=my-pipeline
export PROMETHEUS__PROMETHEUS_DISABLE_CREATED_METRIC=false
```

**Metrics:**

- `step_duration_seconds{step_name, run_id}` - Histogram of execution duration
- `step_executions_total{step_name, run_id}` - Counter of executions

**Labels:**

- `step_name` - Name of the step being executed
- `run_id` - Unique run identifier (from `WURZEL_RUN_ID`)

## Best practices

1. Order matters: middlewares execute in the order specified.
2. Fail gracefully: middlewares should handle errors and avoid breaking step execution.
3. Keep lightweight: middlewares should add minimal runtime overhead.
4. Use settings: store configuration in Settings classes loaded from environment variables.
5. For production deployments, always configure middleware settings in your values.yaml file.
