# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Run the Wurzel KaaS Temporal worker.

Usage::

    uv run python -m wurzel.temporal_worker.run_worker

Environment:

- ``TEMPORAL_ADDRESS`` (default ``localhost:7233``)
- ``TEMPORAL_NAMESPACE`` (default ``default``)
- ``WURZEL_TEMPORAL_TASK_QUEUE`` (default ``wurzel-kaas``)
- ``WURZEL_TEMPORAL_ALLOWED_STEPS`` optional allowlist (comma-separated ``step_key`` or ``*``)
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client  # pylint: disable=import-error
from temporalio.worker import Worker  # pylint: disable=import-error

from wurzel.temporal_worker.activities import execute_wurzel_node
from wurzel.temporal_worker.workflows import WurzelPipelineWorkflow

log = logging.getLogger(__name__)


async def _run() -> None:
    addr = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    ns = os.environ.get("TEMPORAL_NAMESPACE", "default")
    queue = os.environ.get("WURZEL_TEMPORAL_TASK_QUEUE", "wurzel-kaas")

    client = await Client.connect(addr, namespace=ns)
    worker = Worker(
        client,
        task_queue=queue,
        workflows=[WurzelPipelineWorkflow],
        activities=[execute_wurzel_node],
        activity_executor=ThreadPoolExecutor(max_workers=int(os.environ.get("WURZEL_TEMPORAL_ACTIVITY_THREADS", "16"))),
    )
    log.info("Wurzel Temporal worker listening on queue %s (%s)", queue, addr)
    await worker.run()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
