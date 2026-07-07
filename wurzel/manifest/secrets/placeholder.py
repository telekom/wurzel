# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Parse and detect secret placeholder strings.

Placeholders follow the format ``${secret:<provider>:<ref>}`` where
``<provider>`` is the registered provider name (e.g. ``vault``, ``k8s``) and
``<ref>`` is the provider-specific secret reference.

```python
from wurzel.manifest.secrets.placeholder import parse_placeholder, find_placeholder_vars

# Parse a single placeholder
ref = parse_placeholder("${secret:vault:my-secret}")
print(ref.provider)
#> vault
print(ref.ref)
#> my-secret

# Non-placeholder values return None
assert parse_placeholder("plain-value") is None

# Scan a dict of env vars for placeholders
env = {
    "DB_PASSWORD": "${secret:vault:db-pass}",
    "HOST": "localhost",
    "API_KEY": "${secret:k8s:api-secret}",
}
refs = find_placeholder_vars(env)
print(sorted(refs.keys()))
#> ['API_KEY', 'DB_PASSWORD']
print(refs["DB_PASSWORD"].provider)
#> vault
```
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PLACEHOLDER_RE = re.compile(r"^\$\{secret:(?P<provider>[^:}]+):(?P<ref>[^}]+)\}$")


@dataclass(frozen=True)
class SecretRef:
    """Parsed representation of a secret placeholder."""

    provider: str
    ref: str


def parse_placeholder(value: str) -> SecretRef | None:
    """Parse a placeholder string into a SecretRef, or return None if not a placeholder."""
    match = _PLACEHOLDER_RE.match(value)
    if not match:
        return None
    return SecretRef(provider=match.group("provider"), ref=match.group("ref"))


def find_placeholder_vars(env: dict[str, str]) -> dict[str, SecretRef]:
    """Return a mapping of env var name → SecretRef for all vars containing a placeholder."""
    result: dict[str, SecretRef] = {}
    for key, value in env.items():
        ref = parse_placeholder(value)
        if ref is not None:
            result[key] = ref
    return result
