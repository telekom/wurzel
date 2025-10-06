# Wurzel Executor

This section documents the `BaseStepExecutor` — the core execution environment
used by Wurzel to run typed steps. It covers the typical usage patterns,
environment encapsulation, middleware support, and examples.

## Overview

`BaseStepExecutor` is responsible for:

- Loading inputs (from memory or disk) and converting them to the step's input
  models.
- Running the step's `run()` function in a controlled context.
- Saving outputs to disk using the step's output model if an output path is
  provided.
- Optionally wrapping execution with a chain of middlewares that can observe
  or modify execution, inputs, and outputs.

The executor is designed to enforce strong typing and to provide helpful
logging and error reporting when contracts fail.

## Usage

Basic usage as a context manager:

```python
from wurzel.step_executor.base_executor import BaseStepExecutor
from wurzel.step.typed_step import TypedStep

class MyStep(TypedStep):
    ...

with BaseStepExecutor() as exc:
    results = exc(MyStep, set(), Path("output"))
```

Running the executor with middlewares by name:

```python
with BaseStepExecutor(middlewares=["prometheus", "timing"]) as exc:
    results = exc(MyStep, set(), Path("output"))
```

Or provide middleware instances directly:

```python
from wurzel.step_executor.middlewares import SomeMiddleware

with BaseStepExecutor(middlewares=[SomeMiddleware()]) as exc:
    results = exc(MyStep, set(), Path("output"))
```

## Environment encapsulation

When a step defines a settings dataclass (via the step's `settings_class`),
`BaseStepExecutor` can automatically build those settings from environment
variables. The executor provides an encapsulation context manager that will
set the relevant environment variables before running the step and restore the
previous environment afterward.

This encapsulation allows tests and runs to provide step-specific settings via
environment variables without permanently mutating the process environment.

By default, the executor encapsulates settings; pass `dont_encapsulate=True` to
disable this behavior.

## Middleware support

See `executor/middlewares.md` for details on how to enable, write and use
middlewares.

## Error handling and logging

- Contract validation errors raised by Pydantic will be translated into
  `ContractFailedException`.
- Unexpected errors during execution will be wrapped in `StepFailed` with
  additional context.
- The executor integrates with the project's logging helpers to record
  uncaught exceptions.

## Notes and best practices

- The executor will try to sort outputs (for deterministic comparisons) when
  sensible — if sorting is not possible it will log a warning and continue.
- Use the middleware system to add cross-cutting concerns (metrics, timing,
  caching, retries) without modifying step logic.
