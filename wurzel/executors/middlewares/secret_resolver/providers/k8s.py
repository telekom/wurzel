# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Kubernetes secret provider."""

from __future__ import annotations

from wurzel.manifest.secrets.base import SecretProvider, _SecretClient


class K8sSecretProvider(SecretProvider, provider_name="k8s"):
    """Resolves secrets from Kubernetes Secrets."""

    def __init__(self, client: _SecretClient) -> None:
        self._client = client

    @classmethod
    def build(cls) -> K8sSecretProvider | None:
        """Auto-instantiate from in-cluster service account or kubeconfig.

        Override this method to add automatic K8s client detection.
        Returns ``None`` until a K8s client implementation is configured.
        """
        return None

    def resolve(self, ref: str) -> str:
        return self._client.fetch_secret(ref)
