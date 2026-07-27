# OpenTelemetry Step I/O & Metadata Capture

The OtelMiddleware now captures comprehensive execution metadata for every step, including inputs, outputs, and execution metrics. This data flows to Arize Phoenix for visualization and audit trails.

## Captured Metadata

### Span Attributes

Every step execution creates a root span with these attributes:

| Attribute | Type | Example | Purpose |
|-----------|------|---------|---------|
| `wurzel.step.name` | string | `"FetchDocumentStep"` | Step class name |
| `wurzel.run.id` | string | `"run-abc123"` | Pipeline run identifier |
| `wurzel.input.count` | integer | `2` | Number of input paths |
| `wurzel.input.paths` | string | `"/data/input1,/data/input2"` | Comma-separated input paths (first 10) |
| `wurzel.output.dir` | string | `"/data/output"` | Output directory |
| `wurzel.execution.duration_ms` | float | `15.36` | Step execution time in milliseconds |
| `wurzel.execution.result_count` | integer | `5` | Number of result tuples returned |
| `project.name` | string | `"wurzel-demo"` | Phoenix project (from `OTEL__PROJECT_NAME`) |
| `tenant` | string | `"demo-tenant"` | Multi-tenant routing (from `OTEL__TENANT`) |

### Span Events

A `step_completed` event is emitted when execution finishes successfully:

```json
{
  "name": "step_completed",
  "timestamp": "2026-07-27T11:08:34.876063+00:00",
  "attributes": {
    "result_count": 5,
    "duration_ms": 15.359,
    "input_count": 2,
    "output_dir": "/data/output"
  }
}
```

### Log Correlation

The `LoggingInstrumentor` auto-injects `trace_id` and `span_id` into all Python logging records, enabling:
- Correlation between application logs and trace spans in Phoenix
- Full execution history via combined log + trace views

## Usage

### Basic Setup

```python
from pathlib import Path
from pydantic import BaseModel

from wurzel.core.typed_step import TypedStep
from wurzel.executors.middlewares.otel import OtelMiddleware, OtelMiddlewareSettings
from wurzel.core.settings import Settings


class MySettings(Settings):
    """Settings for MyStep."""

    pass


class MyInput(BaseModel):
    """Input schema for MyStep."""

    pass


class MyOutput(BaseModel):
    """Output schema for MyStep."""

    pass


class MyStep(TypedStep[MySettings, MyInput, MyOutput]):
    """Example step."""

    def run(self, inputs: MyInput) -> MyOutput:
        return MyOutput()


def execute_step(step_cls, inputs, output_dir):
    """Stub executor - simplified for documentation."""
    return []


settings = OtelMiddlewareSettings(
    ENDPOINT="localhost:14317",  # OTel Collector
    SERVICE_NAME="my-pipeline",
    PROJECT_NAME="my-project",  # Routed to Phoenix project
    TENANT="team-a",  # Multi-tenant isolation
    ENABLED=True,
)

with OtelMiddleware(settings=settings) as middleware:
    # Step execution with I/O tracking
    inputs = {Path("/data/input1"), Path("/data/input2")}
    output_dir = Path("/data/output")
    result = middleware(
        call_next=execute_step,
        step_cls=MyStep,
        inputs=inputs,
        output_dir=output_dir,
    )
```

### Viewing in Phoenix

1. Open Phoenix UI: `http://localhost:6006`
2. Select project: navigate to your configured `PROJECT_NAME`
3. View trace: open the span named `wurzel.step.<StepName>`
4. Inspect metadata:
   - **Attributes tab** — see input counts, output paths, execution duration
   - **Events tab** — see `step_completed` event with structured metadata
   - **Logs tab** — correlate application logs by trace_id

### Environment Variables

Control I/O metadata capture via settings:

```bash
# Configure endpoint and service
export OTEL__ENDPOINT="localhost:14317"
export OTEL__SERVICE_NAME="my-pipeline"
export OTEL__INSECURE=True
export OTEL__ENABLED=True

# Routing and classification
export OTEL__PROJECT_NAME="my-project"      # Phoenix project
export OTEL__TENANT="team-a"                # Multi-tenant routing
```

## Example: Audit Trail

Given this execution:
```python
from pathlib import Path

input_paths = {Path("/data/docs/2025-01"), Path("/data/docs/2025-02")}
output_dir = Path("/data/processed/2025-q1")
```

Phoenix will display:
- **Span attributes**:
  - `wurzel.input.count: 2`
  - `wurzel.input.paths: "/data/docs/2025-01,/data/docs/2025-02"`
  - `wurzel.output.dir: "/data/processed/2025-q1"`
  - `wurzel.execution.duration_ms: 1234.56`
  - `wurzel.execution.result_count: 150`

- **Timeline**: Execution started/ended timestamps visible in span

- **Correlation**: Any HTTP calls, logs, or child processes appear as child spans with same trace_id

## Architecture

```
Wurzel Step
    │
    ├─ Middleware receives: inputs, output_dir
    │
    ├─ Auto-instruments: requests, urllib3, threading, logging
    │
    ├─ Creates root span: "wurzel.step.<StepName>"
    │
    ├─ Records before execution:
    │   ├─ input count
    │   └─ input paths
    │
    ├─ Records after execution:
    │   ├─ result count
    │   ├─ execution duration
    │   ├─ output directory
    │   └─ step_completed event
    │
    └─ Sends to OTel Collector via gRPC
            │
            ├─ Batch processor (1s timeout, 64-span batch)
            │
            ├─ Routing connector (routes by tenant)
            │
            └─ OTLP HTTP exporter
                    │
                    └─ Arize Phoenix UI
```

## Limitations & Design Decisions

1. **Input paths limited to first 10**: Paths are stored as a comma-separated string to avoid span attribute size limits. If you need all paths, use `span.add_event()` in your step or implement a custom middleware layer.

2. **Result count, not content**: For performance and privacy, we capture only the count of result tuples, not their content. Deep serialization would be slow and potentially expose sensitive data.

3. **Output directory path only**: We track where outputs were written but not which specific files were created. This can be enhanced by adding file listing to the `step_completed` event if needed.

4. **Automatic or always-on**: I/O metadata capture is automatic and always enabled when `ENABLED=True`. No per-step configuration needed.

## Testing

Run tests to verify metadata capture:

```bash
uv run pytest tests/middleware/test_otel_middleware.py -k "input_count or output_dir or result_count or step_completed" -v
```

All 5 new metadata tests are included in the standard test suite.

## Related Configuration

- [OtelMiddleware Settings](../otel/settings.py)
- [OTel Collector Routing](../examples/phoenix/otel-collector-config.yaml)
- [Phoenix Deployment](../examples/phoenix/docker-compose.yml)
