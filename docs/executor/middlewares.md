# Step Executor Middlewares

Middlewares wrap step execution to add cross-cutting concerns (metrics, logging,
tracing) without modifying step logic. They follow the Chain of Responsibility
pattern and execute in the configured order around the core executor.

## Enabling middlewares

Pass middleware names (looked up in the built-in registry) or instances directly
to `BaseStepExecutor`:

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

**Metrics emitted** (labels: `step_name`, `run_id` from `WURZEL_RUN_ID`):

- `steps_started`, `steps_failed`, `step_results`, `step_inputs` — Counters
- `step_hist_load`, `step_hist_execute`, `step_hist_save` — Histograms
- `step_datacontract_metric` — Gauge for data contract metrics

For DVC, export the env vars before `dvc repro`. For Argo, add them to
`container.env` in your `values.yaml`. See the
[Argo backend docs](../backends/argoworkflows.md#middleware-configuration) for
a YAML example.
