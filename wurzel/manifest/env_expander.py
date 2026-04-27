# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Expand short settings keys to fully-qualified environment variable names.

```python
from wurzel.manifest.env_expander import EnvExpander

# Step settings use STEPCLASSNAME__ prefix
result = EnvExpander.expand_step_settings(
    "ManualMarkdownStep", {"FOLDER_PATH": "./data"}
)
print(result)
#> {'MANUALMARKDOWNSTEP__FOLDER_PATH': './data'}

# Middleware settings use MIDDLEWARENAME__ prefix
result = EnvExpander.expand_middleware_settings("prometheus", {"GATEWAY": "host:9091"})
print(result)
#> {'PROMETHEUS__GATEWAY': 'host:9091'}

# MIDDLEWARES env var from ordered name list
result = EnvExpander.expand_middlewares_list(["secret_resolver", "prometheus"])
print(result)
#> {'MIDDLEWARES': 'secret_resolver,prometheus'}
```
"""


class EnvExpander:
    """Transforms step and middleware setting keys into prefixed env var names."""

    @staticmethod
    def _expand(name: str, settings: dict[str, str]) -> dict[str, str]:
        prefix = f"{name.upper()}__"
        return {f"{prefix}{key}": value for key, value in settings.items()}

    @staticmethod
    def expand_step_settings(class_name: str, settings: dict[str, str]) -> dict[str, str]:
        """Prefix each key with ``{CLASS_NAME_UPPER}__``."""
        return EnvExpander._expand(class_name, settings)

    @staticmethod
    def expand_middleware_settings(middleware_name: str, settings: dict[str, str]) -> dict[str, str]:
        """Prefix each key with ``{MIDDLEWARE_NAME_UPPER}__``."""
        return EnvExpander._expand(middleware_name, settings)

    @staticmethod
    def expand_middlewares_list(ordered_names: list[str]) -> dict[str, str]:
        """Return ``{"MIDDLEWARES": "name1,name2,..."}`` from an ordered list."""
        return {"MIDDLEWARES": ",".join(ordered_names)}
