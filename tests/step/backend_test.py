from wurzel.backend.backend_argo import ArgoBackend , ArgoBackendSettings, S3ArtifactTemplate
from wurzel.backend.backend_dvc import DvcBackend




def test_argo_settings(env):

    settings = ArgoBackendSettings()
    assert settings.IMAGE == "ghcr.io/telekom/wurzel"
    env.set("ARGOWORKFLOWBACKEND__IMAGE", "test/image:latest")
    settings = ArgoBackendSettings()
    assert settings.IMAGE == "test/image:latest"
    settings = ArgoBackendSettings(IMAGE="test/image:local")
    assert settings.IMAGE == "test/image:local"