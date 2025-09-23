# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wurzel.backend.backend import Backend
    from wurzel.step.typed_step import TypedStep


def main(step: "TypedStep", backend: "type[Backend]") -> str:
    """Generates the yaml for the given backend."""
    # Lazy imports to avoid loading heavy dependencies at import time
    from wurzel.backend.backend import Backend  # pylint: disable=import-outside-toplevel
    from wurzel.step_executor.base_executor import BaseStepExecutor  # pylint: disable=import-outside-toplevel
    from wurzel.utils import create_model  # pylint: disable=import-outside-toplevel

    adapter: Backend = backend()
    # validate the envs of the steps
    create_model(
        list(step.traverse()),
        allow_extra_fields=BaseStepExecutor.is_allow_extra_settings(),
    )()

    return adapter.generate_artifact(step)
