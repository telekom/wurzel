# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""List available middlewares command."""


def main():
    """List all available middlewares."""
    from wurzel.step_executor.middlewares import get_registry  # pylint: disable=import-outside-toplevel

    registry = get_registry()
    available_middlewares = registry.list_available()

    if not available_middlewares:
        print("No middlewares available.")  # noqa: T201
        return

    print("Available middlewares:")  # noqa: T201
    for middleware in sorted(available_middlewares):
        print(f"  - {middleware}")  # noqa: T201
