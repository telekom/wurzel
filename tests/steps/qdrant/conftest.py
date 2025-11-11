# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.utils import HAS_QDRANT

if not HAS_QDRANT:
    pytest.skip("Qdrant is not available", allow_module_level=True)

pytest.importorskip("pymilvus")


@pytest.fixture(scope="function", autouse=True)
def qdrant_url(env):
    old = env.get("URI")
    if old is None:
        env.set("QDRANTCONNECTORSTEP__URI", ":memory:")
        env.set("QDRANTCONNECTORMULTIVECTORSTEP__URI", ":memory:")
    yield env


@pytest.fixture
def dummy_collection(env, autouse=True):
    env.set("QDRANTCONNECTORSTEP__COLLECTION", "dummy")
    env.set("QDRANTCONNECTORMULTIVECTORSTEP__COLLECTION", "dummy")
