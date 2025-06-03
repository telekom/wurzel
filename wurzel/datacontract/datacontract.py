# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import abc
import hashlib
import json
import types
import typing
from ast import literal_eval
from pathlib import Path
from typing import Self, Union, get_origin

import pandera as pa
import pandera.typing as patyp
import pydantic


class DataModel:
    """interface definition of a Contract model
    Contains method to store and load to a path.
    """

    @classmethod
    @abc.abstractmethod
    def save_to_path(cls, path: Path, obj: Union[Self, list[Self]]) -> Path:
        """Abstract function to save the obj at the given path."""

    @classmethod
    @abc.abstractmethod
    def load_from_path(cls, path: Path, *args) -> Self:
        """Abstract function to load the data from the given Path."""


class PanderaDataFrameModel(pa.DataFrameModel, DataModel):
    """Data Model contract specified with pandera
    Using Panda Dataframe. Mainly for CSV shaped data.
    """

    @classmethod
    def save_to_path(cls, path: Path, obj: Union[Self, list[Self]]) -> Path:
        import pandas as pd  # pylint: disable=import-outside-toplevel

        path = path.with_suffix(".csv")
        if not isinstance(obj, pd.DataFrame):
            raise NotImplementedError(f"Cannot store {type(obj)}")
        obj.to_csv(path, index=False)
        return path

    @classmethod
    def load_from_path(cls, path: Path, *args) -> Self:
        """Switch case to find the matching file ending."""
        import pandas as pd  # pylint: disable=import-outside-toplevel

        read_data = pd.read_csv(path.open(encoding="utf-8"))
        for key, atr in cls.to_schema().columns.items():
            if atr.dtype.type is list:
                read_data[key] = read_data[key].apply(literal_eval)
        return patyp.DataFrame[cls](read_data)


class PydanticModel(pydantic.BaseModel, DataModel):
    """DataModel contract specified with pydantic."""

    @classmethod
    def save_to_path(cls, path: Path, obj: Union[Self, list[Self]]):
        """Wurzel save model.

        Args:
            path (Path): location
            obj (Union[Self, list[Self]]): obj(s) to store

        Raises:
            NotImplementedError

        """
        path = path.with_suffix(".json")
        if isinstance(obj, list):
            with path.open("wt", encoding="UTF-8") as fp:
                json.dump(obj, fp, default=pydantic.BaseModel.model_dump)
        elif isinstance(obj, cls):
            with path.open("wt", encoding="UTF-8") as fp:
                fp.write(obj.model_dump_json())
        else:
            raise NotImplementedError(f"Cannot store {type(obj)}")
        return path

    # pylint: disable=arguments-differ
    @classmethod
    def load_from_path(cls, path: Path, model_type: type[Union[Self, list[Self]]]) -> Union[Self, list[Self]]:
        """Wurzel load model.

        Args:
            path (Path): load model from
            model_type (type[Union[Self, list[Self]]]): expected type

        Raises:
            NotImplementedError

        Returns:
            Union[Self, list[Self]]: dependent on expected type

        """
        # isinstace does not work for union pylint: disable=unidiomatic-typecheck
        if type(model_type) is types.UnionType:
            model_type = [ty for ty in typing.get_args(model_type) if ty][0]
        if get_origin(model_type) is None:
            if issubclass(model_type, pydantic.BaseModel):
                return cls(**json.load(path.open(encoding="utf-8")))
        elif get_origin(model_type) is list:
            data = json.load(path.open(encoding="utf-8"))
            for i, entry in enumerate(data):
                data[i] = cls(**entry)
            return data

        raise NotImplementedError(f"Can not load {model_type}")

    def __hash__(self) -> int:
        # pylint: disable-next=not-an-iterable
        return int(
            hashlib.sha256(
                bytes(
                    "".join([getattr(self, name) for name in sorted(type(self).model_fields)]),
                    encoding="utf-8",
                ),
                usedforsecurity=False,
            ).hexdigest(),
            16,
        )

    def __eq__(self, other: object) -> bool:
        # pylint: disable-next=not-an-iterable
        for field in type(self).model_fields:
            other_value = getattr(other, field, None)
            if isinstance(other, dict):
                other_value = other.get(field, None)
            if getattr(self, field) != other_value:
                return False
        return True

    def __lt__(self, other: object) -> bool:
        return hash(self) < hash(other)
