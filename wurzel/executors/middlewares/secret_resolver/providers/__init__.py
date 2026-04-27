# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Concrete secret provider implementations."""

from wurzel.executors.middlewares.secret_resolver.providers.k8s import K8sSecretProvider
from wurzel.executors.middlewares.secret_resolver.providers.vault import SupabaseVaultClient, VaultSecretProvider

__all__ = [
    "K8sSecretProvider",
    "SupabaseVaultClient",
    "VaultSecretProvider",
]
