# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.executors.middlewares.secret_resolver.providers.k8s import K8sSecretProvider


class TestK8sSecretProvider:
    def test_resolve_calls_client(self, mocker):
        mock_client = mocker.MagicMock()
        mock_client.fetch_secret.return_value = "k8s-value"
        provider = K8sSecretProvider(client=mock_client)
        result = provider.resolve("my-secret/my-key")
        assert result == "k8s-value"
        mock_client.fetch_secret.assert_called_once_with("my-secret/my-key")

    def test_resolve_raises_on_not_found(self, mocker):
        mock_client = mocker.MagicMock()
        mock_client.fetch_secret.side_effect = KeyError("secret not found")
        provider = K8sSecretProvider(client=mock_client)
        with pytest.raises(KeyError):
            provider.resolve("missing/key")
