# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pydantic

from wurzel import path as kpath


class MyModel(pydantic.BaseModel):
    my: str = "model"


class PathToMyModel(kpath.PathToFolderWithBaseModels[MyModel]):
    pass


def test_get_type():
    assert PathToMyModel._type() == kpath.PathToFolderWithBaseModels[MyModel]


def test_get_model_type():
    assert PathToMyModel.model_type() == MyModel
