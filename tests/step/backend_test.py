# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


import pytest
import yaml
from pydantic import SecretStr

from wurzel.utils import HAS_HERA

if not HAS_HERA:
    pytest.skip("Hera is not available", allow_module_level=True)

from wurzel.backend.backend_argo import ArgoBackend, ArgoBackendSettings, EnvVar
from wurzel.datacontract.common import MarkdownDataContract
from wurzel.step import Settings, TypedStep
from wurzel.utils.meta_settings import WZ


class DummySettings(Settings):
    username: str = "user1"
    password: SecretStr = "topsecret"  # pragma: allowlist secret
    api_key: SecretStr = "apikey123"  # pragma: allowlist secret
    retries: int = 3
    token: SecretStr = "tok"  # pragma: allowlist secret
    non_secret_value: str = "safe_value"


class DummyStep(TypedStep[DummySettings, None, MarkdownDataContract]):
    def run(self, inpt: None) -> MarkdownDataContract:
        return super().run(inpt)


class DummyFollowStep(TypedStep[DummySettings, MarkdownDataContract, MarkdownDataContract]):
    def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
        return super().run(inpt)


@pytest.fixture
def argo_backend():
    settings = ArgoBackendSettings()
    settings.INLINE_STEP_SETTINGS = True
    return ArgoBackend(settings=settings)


def test_create_envs_from_step_settings_filters_sensitive(argo_backend: ArgoBackend):
    step = WZ(DummyStep)

    envs = argo_backend._create_envs_from_step_settings(step)

    assert isinstance(envs, list)
    assert all(isinstance(e, EnvVar) for e in envs)

    prefix = f"{step.__class__.__name__.upper()}__"

    names = [env.name for env in envs]

    # Sensitive keys should not appear
    assert all(not name.endswith("PASSWORD") for name in names)
    assert all(not name.endswith("API_KEY") for name in names)
    assert all(not name.endswith("TOKEN") for name in names)

    # Non-sensitive keys should appear with prefix
    assert prefix + "USERNAME" in names
    assert prefix + "RETRIES" in names

    env_dict = {env.name: env.value for env in envs}
    assert env_dict[prefix + "USERNAME"] == "user1"
    assert env_dict[prefix + "RETRIES"] == "3"


def test_env_vars_in_task_container(argo_backend: ArgoBackend):
    step = WZ(DummyStep)
    follow = WZ(DummyFollowStep)
    step >> follow
    yaml_output = argo_backend.generate_artifact(step)
    parsed = yaml.safe_load(yaml_output)

    # Navigate to the templates where containers are defined
    templates = parsed.get("spec", {}).get("workflowSpec", {}).get("templates", [])
    # The container env vars are inside the steps containers in templates
    # Find the template with the container for DummyStep

    # Check that non-secret settings are present with correct prefix and value
    assert templates[1]["container"]["env"][0]["value"] == "user1"
    assert templates[1]["container"]["env"][0]["name"] == "DUMMYSTEP__USERNAME"
    yaml_output = argo_backend.generate_artifact(follow)
    parsed = yaml.safe_load(yaml_output)

    # Navigate to the templates where containers are defined
    templates = parsed.get("spec", {}).get("workflowSpec", {}).get("templates", [])
    # The container env vars are inside the steps containers in templates
    # Find the template with the container for DummyStep

    # Check that non-secret settings are present with correct prefix and value
    assert templates[1]["container"]["env"][0]["value"] == "user1"
    assert templates[1]["container"]["env"][0]["name"] == "DUMMYSTEP__USERNAME"
    assert len(templates[1]["container"]["env"]) == 3
    assert templates[2]["container"]["env"][0]["value"] == "user1"
    assert templates[2]["container"]["env"][0]["name"] == "DUMMYFOLLOWSTEP__USERNAME"
    assert len(templates[2]["container"]["env"]) == 3


def test_argo_settings(env):
    settings = ArgoBackendSettings()
    assert settings.IMAGE == "ghcr.io/telekom/wurzel"
    env.set("ARGOWORKFLOWBACKEND__IMAGE", "test/image:latest")
    settings = ArgoBackendSettings()
    assert settings.IMAGE == "test/image:latest"
    settings = ArgoBackendSettings(IMAGE="test/image:local")
    assert settings.IMAGE == "test/image:local"
