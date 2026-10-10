# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
"""Example: run a Wurzel step with OtelMiddleware → OTel Collector → Arize Phoenix.

Trace pipeline
--------------
  This script  ──OTLP gRPC──►  OTel Collector (localhost:4317)
                                        │
                                OTLP HTTP /v1/traces
                                        │
                                        ▼
                              Arize Phoenix (localhost:6006)

Prerequisites
-------------
1. Start the Docker stack from this directory::

       docker compose up -d

2. Install wurzel with the otel extra (from the repo root)::

       pip install -e ".[otel]"

   or with uv::

       uv pip install -e ".[otel]"

3. Run this script::

       python run_example.py

4. Open http://localhost:6006 — you should see a project called
   "wurzel-phoenix-example" with a trace containing:

   * Root span  : ``wurzel.step.FetchDocumentStep``  (from OtelMiddleware)
   * Child span : ``GET``                             (auto-instrumented by
                                                       RequestsInstrumentor)

What this demonstrates
----------------------
* OtelMiddleware wraps any step execution in a root span annotated with
  ``wurzel.step.name`` and ``wurzel.run.id``.
* Every outbound ``requests`` call made inside the step is captured as a
  child span automatically — no manual instrumentation needed.
* Traces flow through the OTel Collector before reaching Phoenix, so you
  can add processors (sampling, attribute redaction, etc.) in one place.
"""

import time
from logging import getLogger

import requests

from wurzel.executors.middlewares.otel import OtelMiddleware, OtelMiddlewareSettings

# ─── Fake step class (stands in for a real TypedStep in this demo) ────────────


class FetchDocumentStep:
    """Minimal stub that satisfies the step_cls.__name__ contract."""


# ─── Step logic ───────────────────────────────────────────────────────────────


def execute_step(step_cls, inputs, output_dir):
    """Simulates step work: calls the Phoenix REST API so RequestsInstrumentor fires."""
    log = getLogger(__name__)
    log.info(f"  [{step_cls.__name__}] querying Phoenix REST API …")

    # This call is auto-instrumented — it will appear as a child span in Phoenix
    response = requests.get("http://localhost:6006/v1/projects", timeout=10)
    response.raise_for_status()

    projects = response.json()
    log.info(f"  [{step_cls.__name__}] Phoenix returned {len(projects.get('data', []))} project(s)")
    return []


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    settings = OtelMiddlewareSettings(
        ENDPOINT="localhost:14317",  # OTel Collector gRPC port (host 14317 → container 4317, see docker-compose.yml)
        SERVICE_NAME="wurzel-phoenix-example",
        INSECURE=True,
        ENABLED=True,
        # Routing metadata ─────────────────────────────────────────────────────
        # OTEL__PROJECT_NAME → written as the 'project.name' resource attribute.
        # Phoenix reads this to route the trace into the named project.
        PROJECT_NAME="wurzel-demo",
        # OTEL__TENANT → written as the 'tenant' resource + span attribute.
        # The OTel Collector routing connector fans out by this value.
        TENANT="demo-tenant",
    )

    log = getLogger(__name__)
    log.info("Starting OtelMiddleware …")
    log.info("  Collector  : localhost:14317 (OTLP gRPC)")
    log.info("  Phoenix UI : http://localhost:6006")

    with OtelMiddleware(settings=settings) as middleware:
        log.info("Running FetchDocumentStep …")
        # Pass demo input/output paths to see them captured in traces
        from pathlib import Path

        input_paths = {Path("/data/input1"), Path("/data/input2")}
        output_dir = Path("/data/output")
        middleware(execute_step, FetchDocumentStep, input_paths, output_dir)
        log.info("Step complete.  Flushing spans to collector …")
        # Give the BatchSpanProcessor a moment to export before __exit__ shuts down
        time.sleep(2)

    log.info("Done.  Open http://localhost:6006 to view the trace.")
    log.info('Look for project "wurzel-phoenix-example" → trace "wurzel.step.FetchDocumentStep".')


if __name__ == "__main__":
    main()
