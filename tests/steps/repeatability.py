# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest 
from typing import Type, get_args
from pathlib import Path
import hashlib
from wurzel.step import TypedStep
from wurzel.steps import (
    ManualMarkdownStep
)
EXCLUDE_FROM_LEAF_TESTS: list[Type[TypedStep]] = []

def get_dvc_step_leafs() -> list[TypedStep]:
    return [ManualMarkdownStep]

@pytest.mark.repeatability_test
@pytest.mark.parametrize("step_cls", get_dvc_step_leafs())
def test_repeatability(step_cls: Type[TypedStep], tmp_path: Path):
    pytest.skip("TEST DISABLED")
    step = step_cls()
    if not step.is_leaf():
        pytest.skip("step is not a leaf; test does not apply")
    REPETITIONS = 2
    hashes: list[str] = []

    for i in range(REPETITIONS):
        out_path = tmp_path /f"output_{step_cls.__name__}_{i}"
        step.execute([], out_path)
        file_hash = hashlib.md5(out_path.read_bytes())
        hashes.append(file_hash.hexdigest())
    assert all(res_hash == hashes[0] for res_hash in hashes[1:]), "hashes do not match"
