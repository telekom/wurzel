# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.executors.middlewares.secret_resolver.providers.vault import VaultSecretProvider


class TestVaultSecretProvider:
    def test_resolve_calls_client(self, mocker):
        mock_client = mocker.MagicMock()
        mock_client.fetch_secret.return_value = "resolved-value"
        provider = VaultSecretProvider(client=mock_client)
        result = provider.resolve("my-secret")
        assert result == "resolved-value"
        mock_client.fetch_secret.assert_called_once_with("my-secret")

    def test_resolve_raises_on_client_error(self, mocker):
        mock_client = mocker.MagicMock()
        mock_client.fetch_secret.side_effect = RuntimeError("vault unreachable")
        provider = VaultSecretProvider(client=mock_client)
        with pytest.raises(RuntimeError, match="vault unreachable"):
            provider.resolve("my-secret")
