# Step Executor Middlewares

Middlewares wrap step execution to add cross-cutting concerns (metrics, logging, tracing) without modifying step logic. They follow the Chain of Responsibility pattern and are executed in the order configured.

## Enabling middlewares

Pass names (from the built-in registry) or instances to `BaseStepExecutor`:

```python
from wurzel.executors import BaseStepExecutor
from wurzel.executors.middlewares.prometheus import PrometheusMiddleware

# By name (loaded from registry)
with BaseStepExecutor(middlewares=["prometheus"]) as exc:
    exc(PrometheusMiddleware, None, None)  # example only

# By instance
with BaseStepExecutor(middlewares=[PrometheusMiddleware()]) as exc:
    exc(PrometheusMiddleware, None, None)  # example only
```

Or via the `MIDDLEWARES` environment variable:

```bash
export MIDDLEWARES=prometheus
wurzel run ...
```

Or use the CLI to discover available middlewares:

```bash
wurzel middlewares list
wurzel middlewares inspect prometheus
```

## Writing a custom middleware

Subclass `BaseMiddleware` and implement `__call__`. Always call `call_next` to continue the chain.

```python
import logging

from wurzel.executors.middlewares.base import BaseMiddleware

log = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    def __call__(self, call_next, step_cls, inputs, output_dir):
        log.info("Starting %s", step_cls.__name__)
        result = call_next(step_cls, inputs, output_dir)
        log.info("Finished %s", step_cls.__name__)
        return result
```

Register a custom middleware in the global registry:

```python
from wurzel.executors.middlewares import get_registry
from wurzel.executors.middlewares.prometheus import PrometheusMiddleware

registry = get_registry()
registry.register("my_middleware", PrometheusMiddleware)
assert "my_middleware" in registry.list_available()
```

## Prometheus middleware

Pushes step execution metrics to a Prometheus Pushgateway. Settings use the `PROMETHEUS__` prefix.

| Environment Variable | Default | Description |
|---|---|---|
| `MIDDLEWARES` | - | Comma-separated list of middlewares to enable |
| `PROMETHEUS__GATEWAY` | `localhost:9091` | Pushgateway endpoint (`host:port`) |
| `PROMETHEUS__JOB` | `default-job-name` | Job name for metrics |
| `PROMETHEUS__DISABLE_CREATED_METRIC` | `true` | Disable `*_created` metrics |

**Metrics emitted** (labels: `step_name`, `run_id`):

- `steps_started`, `steps_failed`, `step_results`, `step_inputs` — Counters
- `step_hist_load`, `step_hist_execute`, `step_hist_save` — Histograms
- `step_datacontract_metric` — Gauge for data contract metrics

For DVC, set env vars before `dvc repro`. For Argo, add them to `container.env` in your `values.yaml`. See the [Argo backend docs](../backends/argoworkflows.md#middleware-configuration) for a YAML example.
