# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.executors.middlewares.secret_resolver.providers.k8s import K8sSecretProvider
from wurzel.executors.middlewares.secret_resolver.providers.vault import VaultSecretProvider
from wurzel.manifest.secrets.base import SecretProvider


class TestSecretProviderABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            SecretProvider()  # type: ignore[abstract]

    def test_vault_provider_name(self):
        assert VaultSecretProvider.provider_name == "vault"

    def test_k8s_provider_name(self):
        assert K8sSecretProvider.provider_name == "k8s"

    def test_build_returns_none_by_default(self):
        """Base build() classmethod returns None when provider has no env override."""
        assert K8sSecretProvider.build() is None
