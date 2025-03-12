# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest
from pydantic import Field
from wurzel.step.settings import SettingsBase , SettingsLeaf

class BSettings(SettingsLeaf):
    """All Settings related to logging"""
    LEVEL: str = "INFO"


class CSettings(SettingsLeaf):
    """Settings related to Uvicorn"""
    WORKERS: int = Field( 1, gt=0, le=2)

@pytest.mark.parametrize("env_dict", [
    {'WORKERS': '1'},
    {str(k): str(v)
     for k, v in CSettings(WORKERS=1).model_dump().items()}
])
def test_env_vars_for_uvicorn(env_dict, env):
    env.update(env_dict)
    s = CSettings()
    assert s.WORKERS == 1

@pytest.mark.parametrize("key,value", [
    ('UVICORN__WORKERS', '1'),
    ('UVICORN', CSettings(WORKERS=1).model_dump_json())
])
def test_setting_flat_env_insertion_into_default_uvicorn(key, value, env):
    env.set(key, value)
    class _Settings(SettingsBase):
        UVICORN: CSettings
    s = _Settings()
    assert s.UVICORN.WORKERS == 1
@pytest.mark.parametrize("env_dict", [
    {'LEVEL': '1'},
    BSettings(LEVEL="1").model_dump(),
])
def test_env_vars_for_logging(env_dict, env):
    env.update(env_dict)
    s = BSettings()
    assert s.LEVEL == "1"

def test_no_override_of_root(env):
    env.set("WORKERS", "2")
    class A(SettingsBase):
        UVICORN: CSettings = CSettings()
    a = A()
    assert a.UVICORN.WORKERS == 1
