# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Expand short settings keys to fully-qualified environment variable names."""


class EnvExpander:
    """Transforms step and middleware setting keys into prefixed env var names."""

    @staticmethod
    def _expand(name: str, settings: dict[str, str]) -> dict[str, str]:
        prefix = f"{name.upper()}__"
        return {f"{prefix}{key}": value for key, value in settings.items()}

    @staticmethod
    def expand_step_settings(class_name: str, settings: dict[str, str]) -> dict[str, str]:
        """Prefix each key with ``{CLASS_NAME_UPPER}__``.

        Example::

            EnvExpander.expand_step_settings("ManualMarkdownStep", {"FOLDER_PATH": "./data"})
            # → {"MANUALMARKDOWNSTEP__FOLDER_PATH": "./data"}
        """
        return EnvExpander._expand(class_name, settings)

    @staticmethod
    def expand_middleware_settings(middleware_name: str, settings: dict[str, str]) -> dict[str, str]:
        """Prefix each key with ``{MIDDLEWARE_NAME_UPPER}__``.

        Example::

            EnvExpander.expand_middleware_settings("prometheus", {"GATEWAY": "host:9091"})
            # → {"PROMETHEUS__GATEWAY": "host:9091"}
        """
        return EnvExpander._expand(middleware_name, settings)

    @staticmethod
    def expand_middlewares_list(ordered_names: list[str]) -> dict[str, str]:
        """Return ``{"MIDDLEWARES": "name1,name2,..."}`` from an ordered list.

        Example::

            EnvExpander.expand_middlewares_list(["secret_resolver", "prometheus"])
            # → {"MIDDLEWARES": "secret_resolver,prometheus"}
        """
        return {"MIDDLEWARES": ",".join(ordered_names)}
