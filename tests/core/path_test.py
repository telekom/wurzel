# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pydantic
import pytest

from wurzel import path as kpath


class MyModel(pydantic.BaseModel):
    my: str = "model"


class PathToMyModel(kpath.PathToFolderWithBaseModels[MyModel]):
    pass


def test_get_type():
    assert PathToMyModel._type() == kpath.PathToFolderWithBaseModels[MyModel]


def test_get_model_type():
    assert PathToMyModel.model_type() == MyModel


def test_type_returns_correct_type():
    assert PathToMyModel._type().__origin__ == kpath.PathToFolderWithBaseModels


def test_model_type_returns_generic_type():
    assert PathToMyModel.model_type() is MyModel


def test_validate_path_accepts_directory(tmp_path):
    dir_path = tmp_path
    result = PathToMyModel._validate_path(PathToMyModel(dir_path), None)
    assert isinstance(result, PathToMyModel)
    assert str(result) == str(dir_path)


def test_type_raises_if_no_orig_bases(monkeypatch):
    class Dummy(kpath.PathToFolderWithBaseModels[MyModel]):
        pass

    monkeypatch.setattr(Dummy, "__orig_bases__", [None])
    with pytest.raises(RuntimeError):
        Dummy._type()


def test_model_type_raises_on_invalid_type(monkeypatch):
    class Dummy(kpath.PathToFolderWithBaseModels[MyModel]):
        @classmethod
        def _type(cls):
            raise Exception("fail")

    with pytest.raises(RuntimeError):
        Dummy.model_type()
