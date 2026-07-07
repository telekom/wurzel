# Step Executor Middlewares

Middlewares wrap step execution to add cross-cutting concerns (metrics, logging,
tracing) without modifying step logic. They follow the Chain of Responsibility
pattern and execute in the configured order around the core executor.

## Enabling middlewares

You can enable middlewares in two ways:

1. By passing names or instances to `BaseStepExecutor`:

```python
from wurzel.executors.base_executor import BaseStepExecutor

# Using names registered in the middleware registry
with BaseStepExecutor(middlewares=["prometheus"]) as exc:
    pass

# Or provide middleware instances directly
from wurzel.executors.middlewares.base import BaseMiddleware


class NoopMiddleware(BaseMiddleware):
    def __call__(self, call_next, step_cls, inputs, output_dir):
        return call_next(step_cls, inputs, output_dir)


with BaseStepExecutor(middlewares=[NoopMiddleware()]) as exc:
    pass
```

1. By setting the `MIDDLEWARES` environment variable to a comma-separated
  list of middleware names (the executor will load them from the built-in
  registry):

```bash
# Via CLI flag
wurzel run --middlewares prometheus my.module.MyStep

# Via environment variable (comma-separated)
export MIDDLEWARES=prometheus
wurzel run my.module.MyStep
```

Discover available middlewares at any time:

```bash
wurzel middlewares list
wurzel middlewares inspect prometheus
```

## Writing a custom middleware

Subclass `BaseMiddleware` and implement `__call__`. Always forward to `call_next`
to keep the chain intact.

```python
import logging

from wurzel.executors.middlewares.base import BaseMiddleware, MiddlewareChain

log = logging.getLogger(__name__)


class TimingMiddleware(BaseMiddleware):
    """Records wall-clock time around step execution."""

    def __call__(self, call_next, step_cls, inputs, output_dir):
        import time

        start = time.monotonic()
        result = call_next(step_cls, inputs, output_dir)
        log.info("%s took %.3fs", step_cls.__name__, time.monotonic() - start)
        return result


chain = MiddlewareChain([TimingMiddleware()])
print(len(chain.middlewares))
#> 1
```

## Registry

Built-in middlewares are registered by name so they can be referenced by string:

```python
from wurzel.executors.middlewares import get_registry

registry = get_registry()
print("prometheus" in registry.list_available())
#> True
```

Register a custom middleware the same way:

```python
from wurzel.executors.middlewares import get_registry
from wurzel.executors.middlewares.base import BaseMiddleware


class NoopMiddleware(BaseMiddleware):
    """Passes through without modification."""

    def __call__(self, call_next, step_cls, inputs, output_dir):
        return call_next(step_cls, inputs, output_dir)


registry = get_registry()
registry.register("noop", NoopMiddleware)
print("noop" in registry.list_available())
#> True
```

## Prometheus middleware

Pushes step execution metrics to a Prometheus Pushgateway.
Settings use the `PROMETHEUS__` prefix (pydantic-settings applies it automatically):

| Environment Variable | Default | Description |
|---|---|---|
| `MIDDLEWARES` | - | Comma-separated list of middlewares to enable |
| `PROMETHEUS__GATEWAY` | `localhost:9091` | Pushgateway endpoint (`host:port`) |
| `PROMETHEUS__JOB` | `default-job-name` | Job name for metrics |
| `PROMETHEUS__DISABLE_CREATED_METRIC` | `true` | Disable `*_created` metrics |

**Metrics emitted**:

These gauges are intended for dashboards that correlate Wurzel step results with
Argo workflow pods and Kubernetes resource metrics. They all include
`step_name`, `run_id`, and `workflow_name` labels. The Prometheus Pushgateway
supplies the pipeline `job` label. Namespace and pod labels should be added by
the Prometheus scrape or Pushgateway relabeling configuration.

- `wurzel_step_input_items` — Total input items processed by the step.
- `wurzel_step_result_items` — Total result items produced by the step.
- `wurzel_step_duration_seconds` — Step duration by `phase` (`load`, `execute`, `save`, `total`).
- `wurzel_step_status` — Current step status by `status` (`started`, `succeeded`, `failed`).
- `wurzel_step_timestamp_seconds` — Step lifecycle timestamps by `event` (`started`, `completed`, `failed`).
- `wurzel_step_info` — Static value of `1` with the Wurzel runtime context labels.
- `wurzel_step_datacontract_metric` — Data contract metrics by `metric_name`.

The middleware reads backend-neutral Wurzel runtime context only:
`WURZEL_RUN_ID` and `WURZEL_WORKFLOW_NAME`. Backends are responsible for mapping
their own runtime information into these Wurzel-owned variables. The middleware
does not inspect backend-specific environment variables such as Kubernetes pod
metadata. Local runs use `unknown` for unavailable context labels.

For DVC, export the env vars before `dvc repro`. For Argo, add them to
`container.env` in your `values.yaml`. See the
[Argo backend docs](../backends/argoworkflows.md#middleware-configuration) for
a YAML example.
