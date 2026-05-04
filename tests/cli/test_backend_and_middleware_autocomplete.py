# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.cli.cmd_middlewares import middleware_name_autocomplete as cmd_middleware_autocomplete
from wurzel.executors.backend.backend import Backend


def test_middleware_name_autocomplete_cli():
    # Test the function in cmd_middlewares
    class DummyRegistry:
        def list_available(self):
            return ["prometheus", "custom"]

    import wurzel.executors.middlewares

    original = wurzel.executors.middlewares.get_registry
    wurzel.executors.middlewares.get_registry = lambda: DummyRegistry()

    try:
        result = cmd_middleware_autocomplete("pro")
        assert "prometheus" in result

        result2 = cmd_middleware_autocomplete("xyz")
        assert len(result2) == 0
    finally:
        wurzel.executors.middlewares.get_registry = original


def test_backend_base_class():
    # Test the abstract Backend class
    try:
        b = Backend()
        # Should be able to instantiate but method should raise NotImplementedError
        b.generate_artifact(None)
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass
