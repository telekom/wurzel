# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import abc
from ast import literal_eval
from pathlib import Path
from typing import Union, Self, get_origin, Type
import json
import pydantic
import pandas as pd
import pandera as pa
import pandera.typing as patyp


class DataModel:
    """interface definition of a Contract model
    Contains method to store and load to a path
    """

    @classmethod
    @abc.abstractmethod
    def save_to_path(cls, path: Path, obj: Union[Self, list[Self]]) -> Path:
        """abstract function to save the obj at the given path"""

    @classmethod
    @abc.abstractmethod
    def load_from_path(cls, path: Path, *args) -> Self:
        """abstract function to load the data from the given Path"""


class PanderaDataFrameModel(pa.DataFrameModel, DataModel):
    """Data Model contract specified with pandera
    Using Panda Dataframe. Mainly for CSV shaped data"""

    @classmethod
    def save_to_path(cls, path: Path, obj: Union[Self, list[Self]]) -> Path:
        path = path.with_suffix(".csv")
        if not isinstance(obj, pd.DataFrame):
            raise NotImplementedError(f"Cannot store {type(obj)}")
        obj.to_csv(path, index=False)
        return path

    @classmethod
    def load_from_path(cls, path: Path, *args) -> Self:
        """switch case to find the matching file ending"""
        read_data = pd.read_csv(path.open(encoding="utf-8"))
        for key, atr in cls.to_schema().columns.items():
            if atr.dtype.type == list:
                read_data[key] = read_data[key].apply(literal_eval)
        return patyp.DataFrame[cls](read_data)


class PydanticModel(pydantic.BaseModel, DataModel):
    """DataModel contract specified with pydantic"""

    @classmethod
    def save_to_path(cls, path: Path, obj: Union[Self, list[Self]]):
        """Wurzel save model

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
    def load_from_path(
        cls, path: Path, model_type: Type[Union[Self, list[Self]]]
    ) -> Union[Self, list[Self]]:
        """Wurzel load model

        Args:
            path (Path): load model from
            model_type (Type[Union[Self, list[Self]]]): expected type

        Raises:
            NotImplementedError

        Returns:
            Union[Self, list[Self]]: dependent on expected type
        """
        if get_origin(model_type) is None:
            if issubclass(model_type, pydantic.BaseModel):
                return cls(**json.load(path.open(encoding="utf-8")))
        elif get_origin(model_type) == list:
            data = json.load(path.open(encoding="utf-8"))
            for i, entry in enumerate(data):
                data[i] = cls(**entry)
            return data

        raise NotImplementedError(f"Can not load {model_type}")
