# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Any, Generic, TypeVar, get_args

import pandera.typing as patyp
import pydantic
from pydantic_core import PydanticCustomError, core_schema

B = TypeVar(
    "B",
    pydantic.BaseModel,
    None,
    patyp.DataFrame,
    list[pydantic.BaseModel],
    list[patyp.DataFrame],
    list[None],
)


class PathToFolderWithBaseModels(type(Path()), Generic[B]):  # type: ignore[misc]
    """Used to Store both path information
    as well as pydantic.BaseModel info.

    Inherits from Pathlib.Path:
    - Supports all path operations like / etc.


    #### Example:
    ```python
        class Person(pydantic.BaseModel):
            # Could be anything that inherits from BaseModel
            name: str
            age: int
        # Define new class to supply GenericType
        class JFP(PathToBaseModel[Person]): # JsonFilePath
            pass

        path = JFP("./max.json")
        # Load from path
        p_max = path.load_model()
        # Do anything
        p_max.age = p_max.age += 1
        # Store at path
        # Actual path can be modified like pathlib.Path
        path.save_model(p_max)
    ```
    """

    @classmethod
    def _type(cls) -> type["PathToFolderWithBaseModels"]:
        """Get own type (used for pydantic).

        Raises:
            RuntimeError: if own type can't be found

        Returns:
            type: PathToBaseModel

        """
        typ = getattr(cls, "__orig_bases__", [None])[0]
        if typ is None:
            raise RuntimeError(f"Could not get __orig_bases__ from class '{cls}'")
        return typ

    @classmethod
    def model_type(cls) -> type[B]:
        """_summary_.

        Raises:
            RuntimeError: if type can't be found
        Returns:
            type[pydantic.BaseModel]: Type of Generic

        """
        try:
            return get_args(cls._type())[0]
        except Exception as err:
            raise RuntimeError("Model type could not be found") from err

    @classmethod
    def __get_pydantic_core_schema__(cls, _: Any, handler: pydantic.GetCoreSchemaHandler):
        return core_schema.with_info_after_validator_function(cls._validate_path, handler(cls._type()))

    @classmethod
    def _validate_path(cls, path: "PathToFolderWithBaseModels", _: core_schema.ValidationInfo) -> Path:
        if not path.is_dir():
            raise PydanticCustomError("path_not_dir", "Path is not a directory but a file")
        return cls(path)
