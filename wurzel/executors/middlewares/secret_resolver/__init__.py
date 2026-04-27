# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Secret resolver middleware package."""

from wurzel.executors.middlewares.secret_resolver import providers as _providers  # noqa: F401  # trigger SecretProvider registration
from wurzel.executors.middlewares.secret_resolver.secret_resolver import SecretResolverMiddleware

__all__ = ["SecretResolverMiddleware"]
