# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.backend.backend_argo import ArgoBackendSettings


def test_argo_settings(env):
    settings = ArgoBackendSettings()
    assert settings.IMAGE == "ghcr.io/telekom/wurzel"
    env.set("ARGOWORKFLOWBACKEND__IMAGE", "test/image:latest")
    settings = ArgoBackendSettings()
    assert settings.IMAGE == "test/image:latest"
    settings = ArgoBackendSettings(IMAGE="test/image:local")
    assert settings.IMAGE == "test/image:local"
